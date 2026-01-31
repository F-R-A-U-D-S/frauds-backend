import csv
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy.orm import Session
from app.db.models import ExportToken, User
from app.core.config import settings
from app.services.email_service import send_export_email
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import logging
import boto3
import io
import pandas as pd
from app.core.local_storage import load_decrypted
from app.services.report_service import convert_csv_to_pdf
from sqlalchemy.orm import Session
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

EXPORT_DIR = Path("storage/exports")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

def generate_fraud_report(format: str, user_email: str) -> str:
    """
    Fetches the latest fraud analysis report from S3 (flagged/ prefix),
    decrypts it, and saves it locally for export.
    Returns the absolute path to the generated file.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"fraud_analysis_{timestamp}.{format}"
    file_path = EXPORT_DIR / filename
    
    # 1. Connect to S3 to find latest file
    try:
        s3 = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        
        # List objects in 'flagged/'
        response = s3.list_objects_v2(Bucket=settings.S3_BUCKET, Prefix="flagged/")
        contents = response.get("Contents", [])
        
        # Filter for .bin files (ignore .key) and sort by LastModified descending
        bin_files = [obj for obj in contents if obj["Key"].endswith(".bin")]
        bin_files.sort(key=lambda x: x["LastModified"], reverse=True)
        
        if not bin_files:
            logger.warning("No flagged reports found in S3. Using empty data.")
            df = pd.DataFrame(columns=["Message"])
            df.loc[0] = ["No fraud analysis reports found in system."]
        else:
            latest_key = bin_files[0]["Key"]
            logger.info(f"Exporting latest report: {latest_key}")
            
            # 2. Decrypt the file content
            csv_bytes = load_decrypted(latest_key)
            
            # Read into DataFrame for easy format conversion
            df = pd.read_csv(io.BytesIO(csv_bytes))
            
    except Exception as e:
        logger.error(f"Failed to fetch data from S3: {e}")
        # Fallback to error report
        df = pd.DataFrame(columns=["Error"])
        df.loc[0] = [f"Could not retrieve report data: {str(e)}"]

    # 3. Save to requested format
    if format.lower() == "csv":
        df.to_csv(file_path, index=False)
    elif format.lower() == "pdf":
        # Convert DF back to CSV bytes for the PDF converter (reusing existing service)
        csv_buffer = io.BytesIO()
        df.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue()
        
        pdf_bytes = convert_csv_to_pdf(csv_data)
        with open(file_path, "wb") as f:
            f.write(pdf_bytes)
    else:
        raise ValueError("Unsupported format")

    return str(file_path)


def create_export_token(db: Session, user_id: str) -> str:
    """
    Creates a secure export token and saves it to the database.
    """
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=30)
    
    db_token = ExportToken(
        token=token,
        user_id=user_id,
        expires_at=expires_at,
        is_used=False
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    
    return token

def process_export_request(user_id: str, user_email: str, format: str):
    """
    Background task to generate report and send email.
    Creates its own DB session to avoid threading/locking issues with SQLite.
    """
    db = SessionLocal()
    try:
        # Create token
        token = create_export_token(db, user_id)
        
        # Generator File (Real Data)
        file_path = generate_fraud_report(format, user_email)
        
        # Update token with file path
        token_record = db.query(ExportToken).filter(ExportToken.token == token).first()
        if token_record:
            token_record.file_path = file_path
            db.commit()
            
            # Send Email
            
            # User email might be None if not set (but we added it), check logic
            valid_email = user_email or "tauheed@example.com" # Fallback for demo
            
            # Assuming backend URL is configurable or hardcoded for now
            base_url = "http://localhost:8000" # Should come from config
            download_link = f"{base_url}/export/download?token={token}"
            
            send_export_email(valid_email, download_link, format)
            
    except Exception as e:
        logger.error(f"Error processing export request: {e}")
    finally:
        db.close()

def validate_and_consume_token(token: str, db: Session) -> str:
    """
    Validates the token and returns the file path.
    Token is valid for 30 minutes and can be used multiple times.
    """
    token_record = db.query(ExportToken).filter(ExportToken.token == token).first()
    
    if not token_record:
        raise ValueError("Invalid token")
        
    # REMOVED is_used check for multi-use within time limit
    # if token_record.is_used:
    #    raise ValueError("Token already used")
        
    if token_record.expires_at < datetime.utcnow():
        raise ValueError("Token expired")
        
    # Removed burning of token
    # token_record.is_used = True
    # db.commit()
    
    return token_record.file_path
