import boto3
from botocore.config import Config

from .config import settings


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.AWS_ENDPOINT_URL_S3 or None,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        region_name=settings.AWS_REGION,
        config=Config(s3={"addressing_style": "path"}),
    )


def upload_file(key: str, data: bytes, content_type: str):
    get_s3_client().put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def download_file(key: str, destination: str):
    get_s3_client().download_file(
        settings.S3_BUCKET_NAME, key, destination
    )


def delete_file(key: str):
    get_s3_client().delete_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=key,
    )
