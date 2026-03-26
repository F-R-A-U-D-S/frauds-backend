import io
import logging
import secrets
from datetime import datetime, timedelta, timezone

import boto3
import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.local_storage import load_decrypted, write_encrypted_output
from app.db.models import ExportToken
from app.db.session import SessionLocal
from app.services.email_service import send_export_email
from app.services.report_service import convert_csv_to_pdf

logger = logging.getLogger(__name__)


def _boto3_kwargs():
    kw = {"region_name": settings.AWS_REGION}

    if getattr(settings, "AWS_ACCESS_KEY_ID", None) and getattr(settings, "AWS_SECRET_ACCESS_KEY", None):
        kw["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        kw["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY

    return kw


def _s3():
    return boto3.client("s3", **_boto3_kwargs())


def _get_latest_flagged_key() -> str | None:
    s3 = _s3()
    response = s3.list_objects_v2(Bucket=settings.S3_BUCKET, Prefix="flagged/")
    contents = response.get("Contents", [])

    bin_files = [obj for obj in contents if obj["Key"].endswith(".bin")]
    bin_files.sort(key=lambda x: x["LastModified"], reverse=True)

    if not bin_files:
        return None

    return bin_files[0]["Key"]


def _get_report_dataframe() -> pd.DataFrame:
    try:
        latest_key = _get_latest_flagged_key()

        if not latest_key:
            logger.warning("No flagged reports found in S3. Using fallback data.")
            return pd.DataFrame([{"Message": "No fraud analysis reports found in system."}])

        logger.info(f"Exporting latest report from key: {latest_key}")
        csv_bytes = load_decrypted(latest_key)
        return pd.read_csv(io.BytesIO(csv_bytes))

    except Exception as e:
        logger.exception(f"Failed to fetch latest flagged report: {e}")
        return pd.DataFrame([{"Error": f"Could not retrieve report data: {str(e)}"}])


def _build_csv_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue()


def _build_pdf_bytes(df: pd.DataFrame) -> bytes:
    csv_bytes = _build_csv_bytes(df)
    return convert_csv_to_pdf(csv_bytes)


def generate_fraud_report(export_format: str) -> str:
    """
    Generates the latest fraud report, stores it encrypted in S3, and returns the encrypted S3 key.
    """
    export_format = export_format.lower()
    df = _get_report_dataframe()

    if export_format == "csv":
        output_bytes = _build_csv_bytes(df)
        return write_encrypted_output(
            output_bytes=output_bytes,
            prefix="exports",
            extension="csv"
        )

    if export_format == "pdf":
        output_bytes = _build_pdf_bytes(df)
        return write_encrypted_output(
            output_bytes=output_bytes,
            prefix="exports",
            extension="pdf"
        )

    raise ValueError("Unsupported format")


def create_export_token(db: Session, user_id: str) -> str:
    """
    Creates a secure export token and saves it to the database.
    """
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

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


def process_export_request(user_id: str, user_email: str, export_format: str):
    """
    Background task to generate report, store it in encrypted S3 storage,
    and email the user a secure download link.
    """
    db = SessionLocal()

    try:
        token = create_export_token(db, user_id)
        s3_key = generate_fraud_report(export_format)

        token_record = db.query(ExportToken).filter(ExportToken.token == token).first()
        if not token_record:
            raise ValueError("Export token record not found")

        token_record.file_path = s3_key
        db.commit()

        download_link = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/download/secure?token={token}"
        send_export_email(user_email, download_link, export_format)

        logger.info(f"Export created for user {user_id} at key {s3_key}")

    except Exception as e:
        logger.exception(f"Error processing export request: {e}")
    finally:
        db.close()


def validate_and_consume_token(token: str, db: Session) -> str:
    """
    Validates the token and returns the encrypted S3 key.
    Token is valid for 30 minutes and can be reused during that period.
    """
    token_record = db.query(ExportToken).filter(ExportToken.token == token).first()

    if not token_record:
        raise ValueError("Invalid token")

    expires_at = token_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < datetime.now(timezone.utc):
        raise ValueError("Token expired")

    if not token_record.file_path:
        raise ValueError("Export file is not ready")

    return token_record.file_path

def infer_export_type_from_key(s3_key: str) -> tuple[str, str]:
    """
    Infers media type and filename from encrypted export key.

    Examples:
    - exports/abc123.csv.bin -> ("text/csv", "fraud_analysis.csv")
    - exports/xyz789.pdf.bin -> ("application/pdf", "fraud_analysis.pdf")
    """
    if s3_key.endswith(".csv.bin"):
        return "text/csv", "fraud_analysis.csv"

    if s3_key.endswith(".pdf.bin"):
        return "application/pdf", "fraud_analysis.pdf"

    raise ValueError("Unknown export file type")