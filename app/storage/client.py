import json

import boto3

from app.core.config import get_settings


class ObjectStorage:
    def __init__(self) -> None:
        settings = get_settings()
        self.bucket = settings.s3_bucket
        self.public_url = settings.s3_public_url.rstrip("/")
        self.manage_public_read_policy = settings.s3_manage_public_read_policy
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )

    def public_object_url(self, key: str) -> str:
        return f"{self.public_url}/{key.lstrip('/')}"

    def ensure_bucket(self) -> None:
        buckets = self.client.list_buckets().get("Buckets", [])
        if not any(bucket["Name"] == self.bucket for bucket in buckets):
            self.client.create_bucket(Bucket=self.bucket)
        if self.manage_public_read_policy:
            try:
                self._ensure_public_read_policy()
            except Exception:
                pass

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
