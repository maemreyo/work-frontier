"""Exercise a MinIO upload, read, and deletion round trip."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Final
from uuid import uuid4

from boto3.session import Session

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client

ACCESS_KEY_ENVIRONMENT: Final = "MINIO_ROOT_USER"
BUCKET_PREFIX: Final = "work-frontier-smoke"
ENDPOINT_ENVIRONMENT: Final = "MINIO_ENDPOINT_URL"
OBJECT_KEY: Final = "smoke/hello.txt"
PAYLOAD: Final = b"work-frontier"
SECRET_KEY_ENVIRONMENT: Final = "MINIO_ROOT_PASSWORD"
PAYLOAD_MISMATCH: Final = "MinIO payload mismatch"


class StorageSmokeError(RuntimeError):
    """Signal a failed MinIO smoke assertion."""


def required_environment(name: str) -> str:
    """Return a required MinIO environment value."""
    value = os.environ.get(name)
    if value is None:
        raise StorageSmokeError(name)
    return value


def main() -> int:
    """Verify an object storage write, read, and deletion cycle."""
    client: S3Client = Session().client(
        "s3",
        aws_access_key_id=required_environment(ACCESS_KEY_ENVIRONMENT),
        aws_secret_access_key=required_environment(SECRET_KEY_ENVIRONMENT),
        endpoint_url=required_environment(ENDPOINT_ENVIRONMENT),
        region_name="us-east-1",
    )
    bucket = f"{BUCKET_PREFIX}-{uuid4().hex}"
    _ = client.create_bucket(Bucket=bucket)
    _ = client.put_object(Bucket=bucket, Key=OBJECT_KEY, Body=PAYLOAD)
    response = client.get_object(Bucket=bucket, Key=OBJECT_KEY)
    received = response["Body"].read()
    if received != PAYLOAD:
        raise StorageSmokeError(PAYLOAD_MISMATCH)
    _ = client.delete_object(Bucket=bucket, Key=OBJECT_KEY)
    _ = client.delete_bucket(Bucket=bucket)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
