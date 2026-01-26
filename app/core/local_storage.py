import os
import io
import boto3
from cryptography.fernet import Fernet
from app.core.config import settings


def _boto3_kwargs():
    kw = {"region_name": settings.AWS_REGION}

    # If creds exist in Settings, pass them to boto3 explicitly
    if getattr(settings, "AWS_ACCESS_KEY_ID", None) and getattr(settings, "AWS_SECRET_ACCESS_KEY", None):
        kw["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        kw["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY

    return kw

def _s3():
    return boto3.client("s3", **_boto3_kwargs())


# Fernet
def generate_fernet_key():
    return Fernet.generate_key()

def get_fernet(key: bytes):
    return Fernet(key)


# Upload (Fernet encrypted to S3 SSE-KMS)
def store_encrypted(file_bytes_io, prefix="incoming"):
    s3 = _s3()

    key = generate_fernet_key()
    f = get_fernet(key)

    encrypted_bytes = f.encrypt(file_bytes_io.getvalue())

    s3_key = f"{prefix}/{os.urandom(16).hex()}.bin"
    key_s3_key = f"{s3_key}.key"

    s3.upload_fileobj(
        Fileobj=io.BytesIO(encrypted_bytes),
        Bucket=settings.S3_BUCKET,
        Key=s3_key,
        ExtraArgs={
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": settings.KMS_KEY_ID,
        },
    )

    s3.upload_fileobj(
        Fileobj=io.BytesIO(key),
        Bucket=settings.S3_BUCKET,
        Key=key_s3_key,
        ExtraArgs={
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": settings.KMS_KEY_ID,
        },
    )

    return s3_key


def load_decrypted(s3_key: str) -> bytes:
    s3 = _s3()

    encrypted_buf = io.BytesIO()
    s3.download_fileobj(Bucket=settings.S3_BUCKET, Key=s3_key, Fileobj=encrypted_buf)
    encrypted_buf.seek(0)
    encrypted_bytes = encrypted_buf.read()

    key_buf = io.BytesIO()
    s3.download_fileobj(Bucket=settings.S3_BUCKET, Key=f"{s3_key}.key", Fileobj=key_buf)
    key_buf.seek(0)
    fernet_key = key_buf.read()

    f = get_fernet(fernet_key)
    return f.decrypt(encrypted_bytes)


def write_encrypted_output(output_bytes: bytes, prefix="flagged") -> str:
    s3 = _s3()

    key = generate_fernet_key()
    f = get_fernet(key)

    encrypted_bytes = f.encrypt(output_bytes)

    s3_key = f"{prefix}/{os.urandom(16).hex()}.bin"
    key_s3_key = f"{s3_key}.key"

    s3.upload_fileobj(
        Fileobj=io.BytesIO(encrypted_bytes),
        Bucket=settings.S3_BUCKET,
        Key=s3_key,
        ExtraArgs={
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": settings.KMS_KEY_ID,
        },
    )

    s3.upload_fileobj(
        Fileobj=io.BytesIO(key),
        Bucket=settings.S3_BUCKET,
        Key=key_s3_key,
        ExtraArgs={
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": settings.KMS_KEY_ID,
        },
    )

    return s3_key


def delete_key(s3_key: str):
    s3 = _s3()
    s3.delete_object(Bucket=settings.S3_BUCKET, Key=s3_key)
    s3.delete_object(Bucket=settings.S3_BUCKET, Key=f"{s3_key}.key")
