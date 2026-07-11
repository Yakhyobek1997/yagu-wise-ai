"""Tests for MCP HTTP-transport bearer auth (ADR-0016).

Offline by default: the key-resolution + middleware gate are unit-tested with a
trivial Starlette app (no MCP SDK needed). The middleware itself is SDK-agnostic.
"""

from __future__ import annotations

import pytest
from auralynq.mcp_server.auth import MCPAuthMiddleware, resolve_mcp_api_key
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient


def _app(api_key: str) -> TestClient:
    async def ok(_request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/mcp", ok), Route("/mcp", ok, methods=["POST"])])
    app.add_middleware(MCPAuthMiddleware, api_key=api_key)
    return TestClient(app)


def test_open_when_no_key():
    c = _app("")  # empty key => open (local/demo)
    assert c.get("/mcp").status_code == 200


def test_rejects_without_token_when_key_set():
    c = _app("s3cret")
    r = c.get("/mcp")
    assert r.status_code == 401
    assert r.json()["error"] == "unauthorized"
    assert r.headers.get("WWW-Authenticate") == "Bearer"


def test_rejects_wrong_token():
    c = _app("s3cret")
    assert c.get("/mcp", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_accepts_valid_token():
    c = _app("s3cret")
    r = c.get("/mcp", headers={"Authorization": "Bearer s3cret"})
    assert r.status_code == 200
    assert r.text == "ok"


def test_options_preflight_bypasses_auth():
    c = _app("s3cret")
    # CORS preflight must not be blocked
    assert c.options("/mcp").status_code in (200, 405)


@pytest.mark.parametrize(
    "env,expected",
    [
        ({"AURALYNQ_MCP_API_KEY": "mcpkey", "AURALYNQ_SERVE__API_KEY": "apikey"}, "mcpkey"),
        ({"AURALYNQ_MCP_API_KEY": "", "AURALYNQ_SERVE__API_KEY": "apikey"}, "apikey"),
        ({"AURALYNQ_MCP_API_KEY": "", "AURALYNQ_SERVE__API_KEY": ""}, ""),
    ],
)
def test_key_resolution_precedence(monkeypatch, env, expected):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert resolve_mcp_api_key() == expected
