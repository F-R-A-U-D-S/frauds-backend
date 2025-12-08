import os
import pandas as pd
from fastapi import HTTPException
from app.services.schema_service import load_schema


def validate_file_extension(filename: str):
    """
    Validate uploaded file extension.
    Raise HTTPException if invalid.
    """
    allowed_extensions = [".csv",".xls",".xlsx"]
    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file extension '{ext}'. Please Upload a {allowed_extensions} File"
        )
    return 'File Extension Valid. Uploaded Successfully.'

from fastapi import HTTPException

def validate_file_size(file_size: int, max_size_mb: int = 5):
    """
    Validates the uploaded file size against a configurable limit.

    Args:
        file_size (int): Size of the uploaded file in bytes.
        max_size_mb (int): Maximum allowed file size in MB (default: 5MB).

    Raises:
        HTTPException: If the file exceeds the allowed size limit.

    Returns:
        str: Success message if validation passes.
    """

    max_size_bytes = max_size_mb * 1024 * 1024

    if file_size > max_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds the allowed limit of {max_size_mb} MB."
        )

    return "File size is valid."


def validate_schema_columns(df: pd.DataFrame, bank_name: str):
    schema = load_schema(bank_name)
    if not schema:
        raise HTTPException(
            status_code=400,
            detail=f"No schema found for bank: {bank_name}. Please configure schema first."
        )
    
    required_bank_columns = list(schema.values())

    missing = [col for col in required_bank_columns if col not in df.columns]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns for {bank_name}: {missing}"
        )
    
    normalized_df = df.rename(columns={schema[key]: key for key in schema})

    return normalized_df





