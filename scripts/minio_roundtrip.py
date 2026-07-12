"""Exercise a MinIO upload, read, and deletion round trip."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
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
    from work_frontier.contracts.evidence_record import Artifact, Result
    from work_frontier.contracts.evidence_writer import write_evidence

    start_time = datetime.now(UTC)
    repo_root = Path(__file__).parent.parent

    results: list[Result] = []
    error_detail = None
    exit_code = 0
    bucket_name = None

    try:
        client: S3Client = Session().client(
            "s3",
            aws_access_key_id=required_environment(ACCESS_KEY_ENVIRONMENT),
            aws_secret_access_key=required_environment(SECRET_KEY_ENVIRONMENT),
            endpoint_url=required_environment(ENDPOINT_ENVIRONMENT),
            region_name="us-east-1",
        )

        bucket = f"{BUCKET_PREFIX}-{uuid4().hex}"
        bucket_name = bucket

        _ = client.create_bucket(Bucket=bucket)
        results.append(
            Result(
                kind="create_bucket", passed=True, detail=f"Created bucket: {bucket}"
            )
        )

        _ = client.put_object(Bucket=bucket, Key=OBJECT_KEY, Body=PAYLOAD)
        results.append(
            Result(
                kind="put_object", passed=True, detail=f"Uploaded object: {OBJECT_KEY}"
            )
        )

        response = client.get_object(Bucket=bucket, Key=OBJECT_KEY)
        received = response["Body"].read()
        results.append(
            Result(
                kind="get_object", passed=True, detail=f"Retrieved object: {OBJECT_KEY}"
            )
        )

        if received != PAYLOAD:
            raise StorageSmokeError(PAYLOAD_MISMATCH)
        results.append(
            Result(
                kind="verify_payload", passed=True, detail="Payload matches expected"
            )
        )

        _ = client.delete_object(Bucket=bucket, Key=OBJECT_KEY)
        results.append(
            Result(
                kind="delete_object",
                passed=True,
                detail=f"Deleted object: {OBJECT_KEY}",
            )
        )

        _ = client.delete_bucket(Bucket=bucket)
        results.append(
            Result(
                kind="delete_bucket", passed=True, detail=f"Deleted bucket: {bucket}"
            )
        )

    except StorageSmokeError as e:
        error_detail = str(e)
        exit_code = 1
        results.append(Result(kind="storage_error", passed=False, detail=error_detail))
    except Exception as e:
        error_detail = f"{type(e).__name__}: {e}"
        exit_code = 1
        results.append(
            Result(kind="unexpected_error", passed=False, detail=error_detail)
        )

    end_time = datetime.now(UTC)

    artifacts = [
        Artifact(
            path=f"s3://{bucket_name}/{OBJECT_KEY}" if bucket_name else "s3://[bucket]"
        )
    ]

    _ = write_evidence(
        harness_id="WF-HAR-SMOKE-02",
        status="fail" if exit_code != 0 else "pass",
        command="python minio_roundtrip.py",
        exit_code=exit_code,
        working_directory=str(repo_root),
        start_time=start_time,
        end_time=end_time,
        tool_name="minio_roundtrip",
        artifacts=artifacts,
        results=results,
        property_bag={
            "minio_roundtrip": {
                "endpoint_configured": ENDPOINT_ENVIRONMENT in os.environ,
                "bucket_name": bucket_name,
                "object_key": OBJECT_KEY,
                "error": error_detail,
            }
        },
        output_filename="minio-roundtrip.json",
        repo_root=repo_root,
    )

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
