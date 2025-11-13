import boto3
import os
from app.core.config import settings

# S3 + KMS Clients
s3_client = boto3.client("s3", region_name=settings.AWS_REGION)
kms_client = boto3.client("kms", region_name=settings.AWS_REGION)

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
