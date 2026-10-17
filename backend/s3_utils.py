"""
S3 presigned URL utility.

Parses an s3://bucket/key URI and returns a time-limited HTTPS presigned URL.
The raw s3:// URI is never forwarded to callers — only the presigned URL leaves
this module.

Env vars (must be set in production):
  AWS_ACCESS_KEY_ID
  AWS_SECRET_ACCESS_KEY
  AWS_REGION          (default: ap-south-2)
  S3_PRESIGN_EXPIRY   seconds the link stays valid (default: 3600)
"""

import os
import logging
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError
from saraswati_tenant import current_school, s3_path_validator

logger = logging.getLogger(__name__)

_AWS_REGION = os.getenv("AWS_REGION", "ap-south-2")
_PRESIGN_EXPIRY = int(os.getenv("S3_PRESIGN_EXPIRY", "3600"))


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    """Return (bucket, key) from an s3://bucket/key URI."""
    parsed = urlparse(uri)
    if parsed.scheme != "s3":
        raise ValueError(f"Not an S3 URI: {uri!r}")
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    if not bucket or not key:
        raise ValueError(f"Malformed S3 URI: {uri!r}")
    return bucket, key


def generate_presigned_url(s3_uri: str, expiry: int = _PRESIGN_EXPIRY) -> str:
    """
    Return a presigned HTTPS URL for the given s3:// URI.

    Raises ValueError for a malformed URI.
    Raises RuntimeError if AWS credentials are missing or the S3 call fails.
    """
    bucket, key = _parse_s3_uri(s3_uri)
    s3_path_validator(key, current_school().tenant_id)
    try:
        client = boto3.client(
            "s3",
            region_name=_AWS_REGION,
            endpoint_url=f"https://s3.{_AWS_REGION}.amazonaws.com",
            config=Config(
                s3={"addressing_style": "virtual"},
                signature_version="s3v4",
            ),
        )
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiry,
        )
        return url
    except NoCredentialsError:
        logger.error("AWS credentials not configured")
        raise RuntimeError("S3 credentials not configured.")
    except ClientError as exc:
        logger.error("S3 presign failed for %s: %s", s3_uri, exc)
        raise RuntimeError(f"Could not generate file link: {exc}")
