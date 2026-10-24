from pathlib import Path

import boto3
from botocore.config import Config

from .config import settings


def _uses_s3() -> bool:
    return bool(
        settings.AWS_ENDPOINT_URL_S3
        or settings.AWS_ACCESS_KEY_ID
        or settings.AWS_SECRET_ACCESS_KEY
    )


def _local_path(key: str) -> Path:
    path = (Path(settings.STORAGE_DIR) / key).resolve()
    root = Path(settings.STORAGE_DIR).resolve()
    if path != root and root not in path.parents:
        raise ValueError("Storage key resolves outside the configured storage directory")
    return path


def get_s3_client():
    if bool(settings.AWS_ACCESS_KEY_ID) != bool(settings.AWS_SECRET_ACCESS_KEY):
        raise ValueError("Both S3 access key and secret access key must be configured")

    return boto3.client(
        "s3",
        endpoint_url=settings.AWS_ENDPOINT_URL_S3 or None,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        region_name=settings.AWS_REGION,
        config=Config(s3={"addressing_style": "path"}),
    )


def upload_file(key: str, data: bytes, content_type: str) -> None:
    if _uses_s3():
        get_s3_client().put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return

    path = _local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def download_file(key: str, destination: str) -> None:
    if _uses_s3():
        get_s3_client().download_file(
            settings.S3_BUCKET_NAME, key, destination
        )
        return

    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_bytes(_local_path(key).read_bytes())


def delete_file(key: str) -> None:
    if _uses_s3():
        get_s3_client().delete_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=key,
        )
        return

    _local_path(key).unlink(missing_ok=True)
