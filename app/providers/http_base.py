"""Shared base for HTTP-backed metadata providers.

Providers historically re-implemented the same slug helper and bespoke
``httpx`` request/error-mapping boilerplate. ``BaseHttpProvider`` centralizes
the pieces that are genuinely identical:

* ``_slug`` — stable identifier slug used in stub ids and cache keys.
* ``_request_json`` — a JSON GET with consistent ``ApiHTTPException`` mapping
  and optional retry/backoff, parameterized by a provider ``code_prefix`` so
  each provider keeps its own stable error codes.

Providers with non-JSON transports (GraphQL POST, XML) still inherit ``_slug``
and may opt into ``_request_json`` where it fits.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from fastapi import status

from app.core.errors import ApiHTTPException


class BaseHttpProvider:
    def _slug(self, value: str) -> str:
        return "-".join(
            "".join(char.lower() if char.isalnum() else " " for char in value).split()
        )

    def _new_client(self, *, timeout: float, headers: dict[str, str]) -> httpx.AsyncClient:
        # Seam for tests to inject a mock transport.
        return httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True)

    async def _request_json(
        self,
        code_prefix: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 20.0,
        retries: int = 0,
        backoff_base_seconds: float = 0.0,
    ) -> dict[str, Any]:
        attempts = max(1, retries + 1)
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                async with self._new_client(timeout=timeout, headers=headers or {}) as client:
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    payload = response.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == status.HTTP_404_NOT_FOUND:
                    raise ApiHTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        code=f"{code_prefix}_item_not_found",
                        detail=f"{code_prefix} item not found",
                    ) from exc
                if exc.response.status_code < 500 or attempt == attempts - 1:
                    raise ApiHTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        code=f"{code_prefix}_http_error",
                        detail=f"{code_prefix} returned HTTP {exc.response.status_code}",
                    ) from exc
                last_exc = exc
            except (httpx.HTTPError, ValueError) as exc:
                if attempt == attempts - 1:
                    raise ApiHTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        code=f"{code_prefix}_request_failed",
                        detail=f"{code_prefix} request failed",
                    ) from exc
                last_exc = exc
            else:
                if not isinstance(payload, dict):
                    raise ApiHTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        code=f"{code_prefix}_invalid_response",
                        detail=f"Invalid {code_prefix} response",
                    )
                return payload

            if backoff_base_seconds > 0:
                await asyncio.sleep(backoff_base_seconds * (2**attempt))

        # Unreachable: the final attempt always raises above.
        raise ApiHTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code=f"{code_prefix}_request_failed",
            detail=f"{code_prefix} request failed",
        ) from last_exc
