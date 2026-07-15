"""Regression tests for local API smoke-test cleanup."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import httpx
import pytest


def _load_e2e_smoke_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "e2e_smoke.py"
    spec = importlib.util.spec_from_file_location("e2e_smoke_test_module", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Response:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if not self.is_success:
            request = httpx.Request("POST", "http://testserver/courses")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("smoke request failed", request=request, response=response)


class _FailingClient:
    def __init__(self) -> None:
        self.delete_requests: list[tuple[str, dict | None]] = []

    async def __aenter__(self) -> "_FailingClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get(self, url: str, **_: object) -> _Response:
        assert url == "/health"
        return _Response(200)

    async def post(self, url: str, **_: object) -> _Response:
        if url == "/auth/register":
            return _Response(201)
        if url == "/auth/login":
            return _Response(200, {"access_token": "smoke-token"})
        assert url == "/courses"
        return _Response(500)

    async def delete(self, url: str, **kwargs: object) -> _Response:
        self.delete_requests.append((url, kwargs.get("headers")))
        return _Response(204)


@pytest.mark.asyncio
async def test_e2e_smoke_cleans_up_account_after_midflow_failure(monkeypatch) -> None:
    """An API failure after registration still removes the synthetic account."""
    module = _load_e2e_smoke_module()
    client = _FailingClient()
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **_: client)

    with pytest.raises(httpx.HTTPStatusError):
        await module.main()

    assert client.delete_requests == [
        ("/auth/me", {"Authorization": "Bearer smoke-token"})
    ]
