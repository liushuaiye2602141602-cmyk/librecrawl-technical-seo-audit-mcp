"""Credential hygiene and safe response-header evidence contracts."""

import gzip

import pytest


def test_replay_keeps_audit_headers_and_removes_credential_headers(tmp_path):
    """Replacing the header allowlist with pass-through must expose SECRET."""
    from audit_rules.replay import build_replay_document, write_replay_artifact

    headers = {
        "Authorization": "Bearer SECRET",
        "Proxy-Authorization": "Basic SECRET",
        "Cookie": "session=SECRET",
        "Set-Cookie": "session=SECRET",
        "WWW-Authenticate": "Bearer realm=SECRET",
        "X-API-Key": "SECRET",
        "X-Session-Token": "SECRET",
        "X-Robots-Tag": "noindex",
        "Cache-Control": "public, max-age=3600",
        "Strict-Transport-Security": "max-age=31536000",
        "Content-Security-Policy": "default-src 'self'",
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Content-Type": "text/html; charset=utf-8",
    }
    document = build_replay_document(
        source_url="https://example.com/",
        git_head="b" * 40,
        generated_at="2026-08-09T06:00:00Z",
        crawl_metadata={"crawl_parameters": {}, "truncation_status": "NOT_TRUNCATED"},
        pages=[{
            "url": "https://example.com/",
            "status_code": 200,
            "response_headers": headers,
        }],
        links=[],
        site_data={},
        sitemap_reconciliation={},
        crawl_completeness={"pages_crawled": 1, "audit_complete": True},
        provider_evidence={},
    )
    target = tmp_path / "example.audit-replay-v1.json.gz"

    write_replay_artifact(document, target, expected_completed_pages=1)

    with gzip.open(target, "rt", encoding="utf-8") as stream:
        payload = stream.read()
    lowered = payload.lower()
    assert "secret" not in lowered
    for forbidden in (
        "authorization", "proxy-authorization", "cookie", "set-cookie",
        "www-authenticate", "x-api-key", "x-session-token",
    ):
        assert forbidden not in lowered
    for allowed in (
        "x-robots-tag", "cache-control", "strict-transport-security",
        "content-security-policy", "x-frame-options",
        "x-content-type-options", "referrer-policy", "content-type",
    ):
        assert allowed in lowered


@pytest.mark.parametrize("contamination", [
    {"auth": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.signature"},
    {"credential": "ghp_abcdefghijklmnopqrstuvwxyz0123456789"},
    {"callback": "https://user:password@example.com/result"},
    {"callback": "https://example.com/result?access_token=real-token"},
    {"callback": "https://example.com/result?api_key=AIza-real-key"},
    {"callback": "/callback?access_token=real-token"},
    {"callback": "https://example.com/result?sid=real-session"},
    {"callback": "https://example.com/cb#access_token=real-token"},
    {"callback": "/cb#access_token=real-token"},
    {"callback": "https://s3.example/x?X-Amz-Credential=AKIA123&X-Amz-Signature=abc"},
    {"callback": "https://example.com/x?sig=abc&expires=1"},
])
def test_validator_rejects_realistic_credential_shapes(contamination):
    from audit_rules.replay import ReplayValidationError, validate_replay_document
    from tests.phase12.test_replay_integrity import _valid_document

    document = _valid_document()
    document["provider_evidence"] = contamination

    with pytest.raises(ReplayValidationError, match="credential"):
        validate_replay_document(document)


def test_link_header_sanitizer_drops_wrapped_credential_url():
    from audit_rules.replay import sanitize_response_headers

    headers = sanitize_response_headers({
        "Link": '<https://example.com/next?access_token=real-token>; rel="next"',
        "Cache-Control": "public, max-age=60",
    })

    assert "link" not in headers
    assert headers["cache-control"] == "public, max-age=60"
