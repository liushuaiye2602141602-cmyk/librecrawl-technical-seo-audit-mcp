"""Mocked contract tests for the single canonical PSI HTTP client."""

from __future__ import annotations

import httpx


def _response(status: int, *, text: str = "", json_data=None) -> httpx.Response:
    request = httpx.Request("GET", "https://www.googleapis.com/test")
    if json_data is not None:
        return httpx.Response(status, request=request, json=json_data)
    return httpx.Response(status, request=request, text=text)


def test_missing_key_returns_error_without_http(monkeypatch):
    from audit_rules.providers import psi_client

    monkeypatch.delenv("PAGESPEED_API_KEY", raising=False)
    called = []
    monkeypatch.setattr(psi_client.httpx, "get", lambda *a, **k: called.append(True))

    assert psi_client.fetch_pagespeed("https://example.com") == {
        "error": "PAGESPEED_API_KEY not set."
    }
    assert called == []


def test_invalid_strategy_returns_error_without_http(monkeypatch):
    from audit_rules.providers import psi_client

    called = []
    monkeypatch.setattr(psi_client.httpx, "get", lambda *a, **k: called.append(True))

    result = psi_client.fetch_pagespeed(
        "https://example.com", strategy="tablet", api_key="secret"
    )

    assert result == {"error": "Invalid PSI strategy: tablet"}
    assert called == []


def test_http_400_does_not_reflect_api_key(monkeypatch):
    from audit_rules.providers import psi_client

    secret = "secret-value-that-must-not-leak"
    response = _response(400, text=f"request rejected for key={secret}")
    monkeypatch.setattr(psi_client.httpx, "get", lambda *a, **k: response)

    result = psi_client.fetch_pagespeed(
        "https://example.com", api_key=secret
    )

    assert "error" in result
    assert secret not in result["error"]
    assert result["error"] == "PSI bad request (HTTP 400)"


def test_rate_limit_server_error_and_timeout_are_normalized(monkeypatch):
    from audit_rules.providers import psi_client

    for status, expected in [
        (429, "PSI rate limit exceeded (HTTP 429)"),
        (503, "PSI server error (HTTP 503)"),
    ]:
        monkeypatch.setattr(
            psi_client.httpx, "get", lambda *a, _status=status, **k: _response(_status)
        )
        assert psi_client.fetch_pagespeed(
            "https://example.com", api_key="secret"
        ) == {"error": expected}

    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(psi_client.httpx, "get", timeout)
    assert psi_client.fetch_pagespeed(
        "https://example.com", api_key="secret", timeout=7
    ) == {"error": "PSI request timed out after 7s"}


def test_malformed_json_shape_is_provider_error(monkeypatch):
    from audit_rules.providers import psi_client

    response = _response(200, json_data=["unexpected"])
    monkeypatch.setattr(psi_client.httpx, "get", lambda *a, **k: response)

    result = psi_client.fetch_pagespeed("https://example.com", api_key="secret")

    assert result == {"error": "PSI returned an invalid JSON object"}


def test_minimal_success_response_normalizes_scores(monkeypatch):
    from audit_rules.providers import psi_client

    response = _response(
        200,
        json_data={
            "lighthouseResult": {
                "requestedUrl": "https://example.com",
                "finalUrl": "https://example.com/",
                "lighthouseVersion": "13.4.1",
                "categories": {"performance": {"score": 0.91}},
                "audits": {},
            }
        },
    )
    monkeypatch.setattr(psi_client.httpx, "get", lambda *a, **k: response)

    result = psi_client.fetch_pagespeed("https://example.com", api_key="secret")

    assert result["scores"]["performance"] == 91
    assert result["final_url"] == "https://example.com/"
    assert result["lighthouse_version"] == "13.4.1"
