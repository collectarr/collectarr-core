"""Run with RUN_SEAWEEDFS_TESTS=1; creates isolated Docker storage per case."""

import asyncio
import io
import json
import os
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import boto3
import pytest
from botocore.exceptions import ClientError
from PIL import Image

from app.services.health import HealthService
from app.storage.client import ObjectStorage

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_SEAWEEDFS_TESTS") != "1",
        reason="Set RUN_SEAWEEDFS_TESTS=1 to run isolated Docker storage tests",
    ),
]
ROOT = Path(__file__).resolve().parents[2]


def docker(*args: str) -> str:
    return subprocess.check_output(["docker", *args], text=True, timeout=180)


@pytest.fixture
def storage_service(tmp_path, monkeypatch):
    # Resolve the shipped service without reading a local production env file.
    env = tmp_path / "test.env"
    env.write_text(
        (ROOT / ".env.example").read_text()
        + "S3_ACCESS_KEY_ID=storage-test\nS3_SECRET_ACCESS_KEY=storage-test-secret\n"
    )
    config = json.loads(
        docker(
            "compose", "--project-directory", str(ROOT), "--env-file", str(env),
            "-f", str(ROOT / "docker-compose.yml"), "config", "--no-env-resolution",
            "--format", "json",
        )
    )
    service = config["services"]["seaweedfs"]
    # Keep the real image, command, credentials and healthcheck. Replace only
    # storage, network and published ports so no deployment resources are used.
    service.pop("networks", None)
    service["restart"] = "no"
    service["ports"] = ["127.0.0.1::9000", "127.0.0.1::23646"]
    service["volumes"] = ["test_data:/data"]
    compose_file = tmp_path / "compose.json"
    compose_file.write_text(json.dumps({
        "services": {"seaweedfs": service}, "volumes": {"test_data": {}},
    }))
    project = f"collectarr-storage-test-{uuid.uuid4().hex}"
    compose = ["compose", "-p", project, "-f", str(compose_file)]
    try:
        docker(*compose, "up", "-d", "--wait", "--wait-timeout", "120")
        port = docker(*compose, "port", "seaweedfs", "9000").strip().rsplit(":", 1)[1]
        admin_port = docker(*compose, "port", "seaweedfs", "23646").strip().rsplit(":", 1)[1]
        settings = SimpleNamespace(
            s3_endpoint_url=f"http://127.0.0.1:{port}",
            s3_bucket="collectarr-images",
            s3_public_url=f"http://127.0.0.1:{port}/collectarr-images",
            s3_access_key_id="storage-test",
            s3_secret_access_key="storage-test-secret",
            s3_manage_public_read_policy=True,
        )
        monkeypatch.setattr("app.storage.client.get_settings", lambda: settings)
        ObjectStorage._ensured_buckets.clear()
        yield ObjectStorage(), compose, f"http://127.0.0.1:{admin_port}", settings
    finally:
        ObjectStorage._ensured_buckets.clear()
        docker(*compose, "down", "-v", "--remove-orphans")


def test_catalog_storage_roundtrip_and_restart(storage_service):
    storage, compose, admin_url, settings = storage_service
    image = io.BytesIO()
    Image.new("RGB", (8, 8), "blue").save(image, format="WEBP")
    body = image.getvalue()
    key = "covers/music/test/cover.webp"
    url = storage.put_object(key, body, "image/webp")
    assert storage.get_object(key) == (body, "image/webp")
    assert storage.bucket in [b["Name"] for b in storage.client.list_buckets()["Buckets"]]
    policy = json.loads(storage.client.get_bucket_policy(Bucket=storage.bucket)["Policy"])
    assert "s3:GetObject" in policy["Statement"][0]["Action"]
    with urlopen(url, timeout=10) as response:
        assert response.read() == body
        assert response.headers["Content-Type"] == "image/webp"
        assert response.headers["Cache-Control"] == "public, max-age=31536000, immutable"

    # Public access permits reading covers, never bucket listing or writes.
    for req in [
        Request(storage.endpoint_url),
        Request(storage.public_url + "/", method="GET"),
        Request(url, data=b"unauthorized", method="PUT"),
        Request(url, method="DELETE"),
    ]:
        with pytest.raises(HTTPError) as error:
            urlopen(req, timeout=10)
        assert error.value.code == 403
    with urlopen(admin_url, timeout=10) as response:
        assert "/login" in response.url
    bad_client = boto3.client(
        "s3", endpoint_url=storage.endpoint_url,
        aws_access_key_id="invalid", aws_secret_access_key="invalid",
    )
    with pytest.raises(ClientError):
        bad_client.list_buckets()

    assert asyncio.run(HealthService.__new__(HealthService)._s3()) == {"ok": True}
    docker(*compose, "restart", "seaweedfs")
    docker(*compose, "up", "-d", "--wait", "--wait-timeout", "120")
    # Docker can allocate a new ephemeral host port on restart.
    port = docker(*compose, "port", "seaweedfs", "9000").strip().rsplit(":", 1)[1]
    settings.s3_endpoint_url = f"http://127.0.0.1:{port}"
    settings.s3_public_url = f"http://127.0.0.1:{port}/collectarr-images"
    storage = ObjectStorage()
    url = storage.public_object_url(key)
    # Verify objects, metadata, credentials and public policy survive restart
    # before Core has a chance to recreate the bucket policy.
    with urlopen(url, timeout=10) as response:
        assert response.read() == body
        assert response.headers["Cache-Control"] == "public, max-age=31536000, immutable"
    assert storage.get_object(key) == (body, "image/webp")
    assert asyncio.run(HealthService.__new__(HealthService)._s3()) == {"ok": True}

    storage.put_object("batch/a.webp", body, "image/webp")
    storage.put_object("batch/b.webp", body, "image/webp")
    storage.delete_objects(["batch/a.webp", "batch/b.webp"])
    storage.delete_object(key)
    assert storage.client.list_objects_v2(Bucket=storage.bucket).get("KeyCount", 0) == 0
    with pytest.raises(HTTPError) as error:
        urlopen(url, timeout=10)
    assert error.value.code == 404
