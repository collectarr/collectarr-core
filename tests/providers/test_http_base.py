import httpx
import pytest

from app.core.errors import ApiHTTPException
from app.providers.http_base import BaseHttpProvider


class _Provider(BaseHttpProvider):
    def __init__(self, handler):
        self._handler = handler

    def _new_client(self, *, timeout, headers):
        return httpx.AsyncClient(
            transport=httpx.MockTransport(self._handler),
            timeout=timeout,
            headers=headers,
        )


def test_slug_normalizes_non_alphanumeric():
    provider = BaseHttpProvider()
    assert provider._slug(" The Matrix! ") == "the-matrix"
    assert provider._slug("Zelda") == "zelda"


@pytest.mark.asyncio
async def test_request_json_returns_payload():
    provider = _Provider(lambda request: httpx.Response(200, json={"ok": True}))
    payload = await provider._request_json("demo", "https://example.test/x")
    assert payload == {"ok": True}


@pytest.mark.asyncio
async def test_request_json_maps_404():
    provider = _Provider(lambda request: httpx.Response(404, json={}))
    with pytest.raises(ApiHTTPException) as exc:
        await provider._request_json("demo", "https://example.test/x")
    assert exc.value.code == "demo_item_not_found"


@pytest.mark.asyncio
async def test_request_json_maps_server_error():
    provider = _Provider(lambda request: httpx.Response(503, json={}))
    with pytest.raises(ApiHTTPException) as exc:
        await provider._request_json("demo", "https://example.test/x")
    assert exc.value.code == "demo_http_error"


@pytest.mark.asyncio
async def test_request_json_rejects_non_dict():
    provider = _Provider(lambda request: httpx.Response(200, json=[1, 2, 3]))
    with pytest.raises(ApiHTTPException) as exc:
        await provider._request_json("demo", "https://example.test/x")
    assert exc.value.code == "demo_invalid_response"


@pytest.mark.asyncio
async def test_request_json_retries_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, json={})
        return httpx.Response(200, json={"ok": True})

    provider = _Provider(handler)
    payload = await provider._request_json(
        "demo", "https://example.test/x", retries=1, backoff_base_seconds=0
    )
    assert payload == {"ok": True}
    assert calls["n"] == 2
