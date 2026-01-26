import boto3
from app.core.config import settings

def _boto3_kwargs():
    kw = {"region_name": settings.AWS_REGION}
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        kw["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        kw["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
    if settings.AWS_SESSION_TOKEN:
        kw["aws_session_token"] = settings.AWS_SESSION_TOKEN
    return kw

s3_client = boto3.client("s3", **_boto3_kwargs())
kms_client = boto3.client("kms", **_boto3_kwargs())

def upload_encrypted_file(file_path: str, key: str):
    s3_client.upload_file(
        file_path,
        settings.S3_BUCKET,
        key,
        ExtraArgs={
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": settings.KMS_KEY_ID,
        },
    )

def download_file(key: str, dest_path: str):
    s3_client.download_file(settings.S3_BUCKET, key, dest_path)

def delete_file(key: str):
    s3_client.delete_object(Bucket=settings.S3_BUCKET, Key=key)
