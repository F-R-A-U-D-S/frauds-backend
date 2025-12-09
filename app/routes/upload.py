# file uploads + S3 storage

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from app.services import upload_service
from app.services import preprocess_service
from app.core.local_storage import store_encrypted
import pandas as pd
import io
from app.core.security import get_current_user



router = APIRouter(prefix="/upload", tags=["upload"])

validate = upload_service
clean = preprocess_service

@router.post("/file/")
async def upload_file(bank_name: str = Form(...), file: UploadFile = File(...), user=Depends(get_current_user)):


    # Validate file extension
    validate.validate_file_extension(file.filename)

    # Read file content
    content = await file.read()

    # Validate file size
    validate.validate_file_size(len(content))

     # Reject empty file
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Try reading as CSV
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception:
        raise HTTPException(status_code=400, detail="Unable to parse CSV file.")
    
    # Validate columns against schema if exists
    normalized_df = validate.validate_schema_columns(df, bank_name)

    #Preprocess / Clean Data
    cleaned_df, log = clean.preprocess_dataframe(normalized_df)

    # Convert cleaned DataFrame to CSV bytes
    csv_bytes = io.BytesIO()
    cleaned_df.to_csv(csv_bytes, index=False)
    csv_bytes.seek(0)

    # Store cleaned file encrypted
    result_key = store_encrypted(csv_bytes, prefix="incoming")

    
    
    return {
        "filename": file.filename,
        "filesize": f"{len(content) / (1024*1024):.2f} MB",
        "message": "File uploaded successfully.",
        "result_key": result_key,
        "normalized_columns": list(normalized_df.columns),
        "cleaned_rows": len(cleaned_df) ,
        "Cleaned Data Sample": cleaned_df.head(5).to_dict(orient="records"),
        "log": log
        }