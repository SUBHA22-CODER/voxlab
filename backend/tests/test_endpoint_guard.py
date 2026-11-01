"""Tests for the SSRF endpoint guard."""

import pytest

from app.core.config import get_settings
from app.services.endpoint_guard import EndpointValidationError, validate_endpoint


class TestEndpointGuard:
    def test_accepts_public_http_url(self):
        assert validate_endpoint("https://api.example.com/agent") == "https://api.example.com/agent"

    def test_rejects_non_http_schemes(self):
        with pytest.raises(EndpointValidationError, match="http"):
            validate_endpoint("ftp://example.com/agent")
        with pytest.raises(EndpointValidationError, match="http"):
            validate_endpoint("file:///etc/passwd")

    def test_rejects_missing_hostname(self):
        with pytest.raises(EndpointValidationError, match="hostname"):
            validate_endpoint("http:///no-host")

    def test_allows_localhost_by_default(self):
        # Dev default: local demo agents are allowed.
        assert get_settings().allow_local_endpoints is True
        assert validate_endpoint("http://localhost:8100/conversation").startswith("http://localhost")

    def test_blocks_localhost_when_disabled(self, monkeypatch):
        settings = get_settings()
        monkeypatch.setattr(settings, "allow_local_endpoints", False)
        with pytest.raises(EndpointValidationError, match="Private/loopback"):
            validate_endpoint("http://127.0.0.1:8100/conversation")

    def test_blocks_private_ranges_when_disabled(self, monkeypatch):
        settings = get_settings()
        monkeypatch.setattr(settings, "allow_local_endpoints", False)
        with pytest.raises(EndpointValidationError):
            validate_endpoint("http://10.0.0.5/agent")
