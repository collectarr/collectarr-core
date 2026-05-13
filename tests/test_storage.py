from app.storage.client import ObjectStorage


class FakeS3Client:
    def __init__(self) -> None:
        self.buckets: list[dict[str, str]] = []
        self.create_bucket_calls = 0
        self.policy_calls = 0

    def list_buckets(self) -> dict[str, list[dict[str, str]]]:
        return {"Buckets": self.buckets}

    def create_bucket(self, Bucket: str) -> None:
        self.create_bucket_calls += 1
        self.buckets.append({"Name": Bucket})

    def put_bucket_policy(self, Bucket: str, Policy: str) -> None:
        self.policy_calls += 1


def test_object_storage_ensures_bucket_once_per_process(monkeypatch):
    fake_client = FakeS3Client()

    def fake_boto_client(*args, **kwargs):
        return fake_client

    ObjectStorage._ensured_buckets.clear()
    monkeypatch.setattr("app.storage.client.boto3.client", fake_boto_client)

    storage = ObjectStorage()
    storage.ensure_bucket()
    storage.ensure_bucket()

    assert fake_client.create_bucket_calls == 1
    assert fake_client.policy_calls == 1

    second_storage = ObjectStorage()
    second_storage.ensure_bucket()

    assert fake_client.create_bucket_calls == 1
    assert fake_client.policy_calls == 1
