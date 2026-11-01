"""Tests for the HTTP adapter: contract mapping and failure normalization."""

import httpx
import pytest

from app.adapters.http_adapter import HTTPAgentAdapter


def make_adapter(handler) -> HTTPAgentAdapter:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return HTTPAgentAdapter(
        {"endpoint": "http://fake.agent/conversation", "session_id": "vx-test"},
        {"type": "bearer", "token": "tok-123"},
        client=client,
    )


class TestHTTPAdapter:
    async def test_success_maps_full_contract(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/conversation"
            assert request.headers["Authorization"] == "Bearer tok-123"
            body = json_loads(request.content)
            assert body["session_id"] == "vx-test"
            assert body["message"] == "hello"
            return httpx.Response(
                200,
                json={
                    "reply": "Hi there!",
                    "tool_calls": [{"name": "check_order", "args": {}, "status": "success", "duration_ms": 12}],
                    "state": {"turns": 1},
                    "timings": {"llm_ms": 100, "tool_ms": 12, "total_ms": 150},
                },
            )

        adapter = make_adapter(handler)
        result = await adapter.send_message("hello")
        assert result.reply == "Hi there!"
        assert result.tool_calls[0]["name"] == "check_order"
        assert result.state == {"turns": 1}
        assert result.timings["total_ms"] == 150
        assert result.error is None

    async def test_http_500_becomes_error_result(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="boom")

        result = await make_adapter(handler).send_message("hi")
        assert result.error == "http_500"
        assert result.reply == ""

    async def test_timeout_becomes_error_result(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("timed out", request=request)

        result = await make_adapter(handler).send_message("hi")
        assert result.error == "timeout"

    async def test_non_json_response_becomes_error_result(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html>not json</html>")

        result = await make_adapter(handler).send_message("hi")
        assert result.error == "invalid_json_response"

    async def test_missing_fields_default_cleanly(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={})

        result = await make_adapter(handler).send_message("hi")
        assert result.reply == ""
        assert result.tool_calls == []
        assert result.state == {}

    async def test_auth_headers_include_custom(self):
        adapter = HTTPAgentAdapter(
            {"endpoint": "http://x", "session_id": "s"},
            {"headers": {"X-Custom": "yes"}},
        )
        assert adapter.auth_headers() == {"X-Custom": "yes"}


def json_loads(raw: bytes) -> dict:
    import json

    return json.loads(raw)
