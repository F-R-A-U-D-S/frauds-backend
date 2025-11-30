# file uploads + S3 storage

from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services import model_service
router = APIRouter(prefix="/upload", tags=["upload"])
service = model_service
@router.post("/file/")
def upload_file(file: UploadFile = File(...)):
    # Validate file extension
    service.validate_file_extension(file.filename)
    return {"filename": file.filename, "message": "File uploaded successfully."}