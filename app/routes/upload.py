# file uploads + S3 storage

from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services import model_service
from app.services import data_service
import pandas as pd
import io
router = APIRouter(prefix="/upload", tags=["upload"])
service = data_service
@router.post("/file/")
async def upload_file(file: UploadFile = File(...)):
    # Validate file extension
    service.validate_file_extension(file.filename)

    # Read file content
    content = await file.read()

    # Validate file size
    service.validate_file_size(len(content))

     # Reject empty file
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Try reading as CSV
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception:
        raise HTTPException(status_code=400, detail="Unable to parse CSV file.")

    # Validate Required Columns
    service.validate_required_columns(df)

    # # Full DF validation
    # service.validate_uploaded_df(df)
    
    return {
        "filename": file.filename,
        "filesize": f"{len(content) / (1024*1024):.2f} MB",
        "Inferred Columns": service.validate_required_columns(df),
        "message": "File uploaded successfully."
        }