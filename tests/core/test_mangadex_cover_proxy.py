from types import SimpleNamespace

import httpx
import pytest

import app.api.routes.metadata as metadata_routes
from app.core.errors import ApiHTTPException


class _FakeResponse:
    def __init__(self, *, content_type: str, chunks: list[bytes]) -> None:
        self.headers = {"content-type": content_type}
        self._chunks = chunks

    def raise_for_status(self) -> None:
        return None

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class _FakeStream:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeResponse:
        return self._response

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeAsyncClient:
    instances: list["_FakeAsyncClient"] = []
    next_response: _FakeResponse | None = None

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.requests: list[tuple[str, str, dict[str, str] | None]] = []
        self.response = type(self).next_response or _FakeResponse(content_type="image/png", chunks=[b"ok"])
        _FakeAsyncClient.instances.append(self)

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    def stream(self, method: str, url: str, headers: dict[str, str] | None = None) -> _FakeStream:
        self.requests.append((method, url, headers))
        return _FakeStream(self.response)


@pytest.mark.asyncio
async def test_download_mangadex_cover_normalizes_content_type_and_uses_timeout(monkeypatch):
    _FakeAsyncClient.instances.clear()
    monkeypatch.setattr(
        metadata_routes,
        "get_settings",
        lambda: SimpleNamespace(
            image_download_timeout_seconds=7.5,
            mangadex_user_agent="Collectarr-Test",
            max_image_bytes=1024,
        ),
    )
    _FakeAsyncClient.instances.clear()
    _FakeAsyncClient.next_response = _FakeResponse(content_type="image/png; charset=utf-8", chunks=[b"abc"])
    monkeypatch.setattr(metadata_routes.httpx, "AsyncClient", _FakeAsyncClient)

    media_type, body = await metadata_routes._download_mangadex_cover("https://example.test/cover.png")

    assert media_type == "image/png"
    assert body == b"abc"
    client = _FakeAsyncClient.instances[0]
    assert client.kwargs["timeout"] == 7.5
    assert client.requests[0][0] == "GET"
    assert client.requests[0][2]["Accept"] == "image/*"


@pytest.mark.asyncio
async def test_download_mangadex_cover_rejects_non_image_content_type(monkeypatch):
    monkeypatch.setattr(
        metadata_routes,
        "get_settings",
        lambda: SimpleNamespace(
            image_download_timeout_seconds=7.5,
            mangadex_user_agent="Collectarr-Test",
            max_image_bytes=1024,
        ),
    )
    _FakeAsyncClient.instances.clear()
    _FakeAsyncClient.next_response = _FakeResponse(content_type="text/html", chunks=[b"<html></html>"])
    monkeypatch.setattr(metadata_routes.httpx, "AsyncClient", _FakeAsyncClient)

    with pytest.raises(ApiHTTPException) as exc_info:
        await metadata_routes._download_mangadex_cover("https://example.test/cover.html")

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "mangadex_cover_unavailable"


@pytest.mark.asyncio
async def test_download_mangadex_cover_enforces_max_bytes(monkeypatch):
    monkeypatch.setattr(
        metadata_routes,
        "get_settings",
        lambda: SimpleNamespace(
            image_download_timeout_seconds=7.5,
            mangadex_user_agent="Collectarr-Test",
            max_image_bytes=3,
        ),
    )
    _FakeAsyncClient.instances.clear()
    _FakeAsyncClient.next_response = _FakeResponse(content_type="image/jpeg", chunks=[b"ab", b"cd"])
    monkeypatch.setattr(metadata_routes.httpx, "AsyncClient", _FakeAsyncClient)

    with pytest.raises(ApiHTTPException) as exc_info:
        await metadata_routes._download_mangadex_cover("https://example.test/cover.jpg")

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "mangadex_cover_unavailable"
