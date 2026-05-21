import json
import logging
from typing import ClassVar

import boto3

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class ObjectStorage:
    _ensured_buckets: set[tuple[str, str, bool]] = set()
    _shared: ClassVar["ObjectStorage | None"] = None

    def __init__(self) -> None:
        settings = get_settings()
        self.endpoint_url = settings.s3_endpoint_url
        self.bucket = settings.s3_bucket
        self.public_url = settings.s3_public_url.rstrip("/")
        self.manage_public_read_policy = settings.s3_manage_public_read_policy
        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )

    def public_object_url(self, key: str) -> str:
        return f"{self.public_url}/{key.lstrip('/')}"

    def ensure_bucket(self) -> None:
        cache_key = (self.endpoint_url, self.bucket, self.manage_public_read_policy)
        if cache_key in self._ensured_buckets:
            return

        buckets = self.client.list_buckets().get("Buckets", [])
        if not any(bucket["Name"] == self.bucket for bucket in buckets):
            self.client.create_bucket(Bucket=self.bucket)
        if self.manage_public_read_policy:
            try:
                self._ensure_public_read_policy()
            except Exception:
                logger.warning(
                    "Failed to apply public read policy to S3 bucket %s",
                    self.bucket,
                    exc_info=True,
                )
        self._ensured_buckets.add(cache_key)

    def put_object(self, key: str, body: bytes, content_type: str) -> str:
        self.ensure_bucket()
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )
        return self.public_object_url(key)

    def get_object(self, key: str) -> tuple[bytes, str]:
        """Read an object from S3.  Returns ``(body, content_type)``."""
        self.ensure_bucket()
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        body = response["Body"].read()
        content_type = response.get("ContentType", "application/octet-stream")
        return body, content_type

    def delete_object(self, key: str) -> None:
        self.ensure_bucket()
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def delete_objects(self, keys: list[str]) -> None:
        if not keys:
            return
        self.ensure_bucket()
        for start in range(0, len(keys), 1000):
            chunk = keys[start : start + 1000]
            response = self.client.delete_objects(
                Bucket=self.bucket,
                Delete={
                    "Objects": [{"Key": key} for key in chunk],
                    "Quiet": True,
                },
            )
            errors = response.get("Errors", [])
            if errors:
                raise RuntimeError(f"Failed to delete {len(errors)} cached image objects")

    @classmethod
    def shared(cls) -> "ObjectStorage":
        if cls._shared is None:
            cls._shared = cls()
        return cls._shared

    def _ensure_public_read_policy(self) -> None:
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{self.bucket}/*"],
                }
            ],
        }
        self.client.put_bucket_policy(Bucket=self.bucket, Policy=json.dumps(policy))
