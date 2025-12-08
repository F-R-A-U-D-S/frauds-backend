import os
import io
import boto3
from cryptography.fernet import Fernet
from app.core.config import settings

s3 = boto3.client("s3", region_name=settings.AWS_REGION)

# Fernet
def generate_fernet_key():
    return Fernet.generate_key()

def get_fernet(key: bytes):
    return Fernet(key)



# Upload (Fernet encrypted to S3 SSE-KMS)
def store_encrypted(file_bytes_io, prefix="incoming"):
    """
    Encrypt file with Fernet in memory.
    Upload encrypted payload to S3 with SSE-KMS.
    Upload Fernet key separately (also SSE-KMS).
    """

    # Generate Fernet key
    key = generate_fernet_key()
    f = get_fernet(key)

    # Encrypt uploaded content in memory
    encrypted_bytes = f.encrypt(file_bytes_io.getvalue())

    # Random filename
    s3_key = f"{prefix}/{os.urandom(16).hex()}.bin"
    key_s3_key = f"{s3_key}.key"

    # Upload encrypted bytes to S3 using SSE-KMS
    s3.upload_fileobj(
        Fileobj=io.BytesIO(encrypted_bytes),
        Bucket=settings.S3_BUCKET,
        Key=s3_key,
        ExtraArgs={
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": settings.KMS_KEY_ID
        }
    )

    # Upload Fernet key separately (also SSE-KMS)
    s3.upload_fileobj(
        Fileobj=io.BytesIO(key),
        Bucket=settings.S3_BUCKET,
        Key=key_s3_key,
        ExtraArgs={
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": settings.KMS_KEY_ID
        }
    )

    return s3_key

# Download (S3 encrypted → Fernet decrypt in memory)
def load_decrypted(s3_key: str) -> bytes:
    """
    Downloads encrypted bytes + Fernet key from S3.
    SSE-KMS decrypts automatically on download.
    Fernet decrypts locally in memory.
    """

    # Download encrypted file body
    encrypted_buf = io.BytesIO()
    s3.download_fileobj(
        Bucket=settings.S3_BUCKET,
        Key=s3_key,
        Fileobj=encrypted_buf
    )
    encrypted_buf.seek(0)
    encrypted_bytes = encrypted_buf.read()

    # Download its Fernet key
    key_buf = io.BytesIO()
    s3.download_fileobj(
        Bucket=settings.S3_BUCKET,
        Key=f"{s3_key}.key",
        Fileobj=key_buf
    )
    key_buf.seek(0)
    fernet_key = key_buf.read()

    # Local decrypt
    f = get_fernet(fernet_key)
    return f.decrypt(encrypted_bytes)

# Write encrypted output to S3 (same as incoming)
def write_encrypted_output(output_bytes: bytes, prefix="flagged") -> str:
    key = generate_fernet_key()
    f = get_fernet(key)

    encrypted_bytes = f.encrypt(output_bytes)

    s3_key = f"{prefix}/{os.urandom(16).hex()}.bin"
    key_s3_key = f"{s3_key}.key"

    # Upload encrypted output with SSE-KMS
    s3.upload_fileobj(
        Fileobj=io.BytesIO(encrypted_bytes),
        Bucket=settings.S3_BUCKET,
        Key=s3_key,
        ExtraArgs={
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": settings.KMS_KEY_ID
        }
    )

    # Upload encryption key with SSE-KMS
    s3.upload_fileobj(
        Fileobj=io.BytesIO(key),
        Bucket=settings.S3_BUCKET,
        Key=key_s3_key,
        ExtraArgs={
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": settings.KMS_KEY_ID
        }
    )

    return s3_key

# Cleanup
def delete_key(s3_key: str):
    s3.delete_object(Bucket=settings.S3_BUCKET, Key=s3_key)
    s3.delete_object(Bucket=settings.S3_BUCKET, Key=f"{s3_key}.key")
