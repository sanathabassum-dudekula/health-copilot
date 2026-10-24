import os
import boto3
from botocore.config import Config

def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["AWS_ENDPOINT_URL_S3"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        config=Config(s3={"addressing_style": "path"}),
    )

def upload_file(key: str, data: bytes, content_type: str):
    get_s3_client().put_object(
        Bucket=os.environ["S3_BUCKET_NAME"],
        Key=key,
        Body=data,
        ContentType=content_type,
    )

def download_file(key: str, destination: str):
    get_s3_client().download_file(
        os.environ["S3_BUCKET_NAME"], key, destination
    )

def delete_file(key: str):
    get_s3_client().delete_object(
        Bucket=os.environ["S3_BUCKET_NAME"],
        Key=key,
    )
