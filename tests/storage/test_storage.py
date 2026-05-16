from app.storage.client import ObjectStorage


class FakeS3Client:
    def __init__(self) -> None:
        self.buckets: list[dict[str, str]] = []
        self.create_bucket_calls = 0
        self.policy_calls = 0
        self.deleted_objects: list[dict[str, str]] = []
        self.deleted_batches: list[dict] = []

    def list_buckets(self) -> dict[str, list[dict[str, str]]]:
        return {"Buckets": self.buckets}

    def create_bucket(self, Bucket: str) -> None:
        self.create_bucket_calls += 1
        self.buckets.append({"Name": Bucket})

    def put_bucket_policy(self, Bucket: str, Policy: str) -> None:
        self.policy_calls += 1

    def delete_object(self, Bucket: str, Key: str) -> None:
        self.deleted_objects.append({"Bucket": Bucket, "Key": Key})

    def delete_objects(self, Bucket: str, Delete: dict) -> dict:
        self.deleted_batches.append({"Bucket": Bucket, "Delete": Delete})
        return {"Deleted": Delete["Objects"]}


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


def test_object_storage_deletes_object(monkeypatch):
    fake_client = FakeS3Client()

    def fake_boto_client(*args, **kwargs):
        return fake_client

    ObjectStorage._ensured_buckets.clear()
    monkeypatch.setattr("app.storage.client.boto3.client", fake_boto_client)

    storage = ObjectStorage()
    storage.delete_object("covers/comicvine/4000-12345/cover.webp")

    assert fake_client.deleted_objects == [
        {
            "Bucket": "collectarr-images",
            "Key": "covers/comicvine/4000-12345/cover.webp",
        }
    ]


def test_object_storage_deletes_objects_in_batches(monkeypatch):
    fake_client = FakeS3Client()

    def fake_boto_client(*args, **kwargs):
        return fake_client

    ObjectStorage._ensured_buckets.clear()
    monkeypatch.setattr("app.storage.client.boto3.client", fake_boto_client)

    storage = ObjectStorage()
    storage.delete_objects(["covers/one.webp", "covers/two.webp"])

    assert fake_client.deleted_batches == [
        {
            "Bucket": "collectarr-images",
            "Delete": {
                "Objects": [
                    {"Key": "covers/one.webp"},
                    {"Key": "covers/two.webp"},
                ],
                "Quiet": True,
            },
        }
    ]
