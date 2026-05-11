import boto3

from app.core.config import get_settings


class ObjectStorage:
    def __init__(self) -> None:
        settings = get_settings()
        self.bucket = settings.s3_bucket
        self.public_url = settings.s3_public_url.rstrip("/")
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

