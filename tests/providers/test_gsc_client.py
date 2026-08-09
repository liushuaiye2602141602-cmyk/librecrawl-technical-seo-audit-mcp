"""Contract tests for the shared Google Search Console REST client."""

import json

import httpx
import pytest


def _client(handler):
    from audit_rules.providers.gsc_client import GSCClient

    return GSCClient(
        access_token="secret-token",
        site_url="sc-domain:example.com",
        transport=httpx.MockTransport(handler),
    )


def test_search_analytics_encodes_property_and_paginates():
    requests = []

    def handler(request):
        requests.append(request)
        body = json.loads(request.content)
        start = body["startRow"]
        rows = [
            {"keys": [f"https://example.com/{start + i}"], "clicks": 1}
            for i in range(2)
        ] if start == 0 else []
        return httpx.Response(200, json={"rows": rows})

    result = _client(handler).query_search_analytics(
        "2026-07-01", "2026-07-31", dimensions=["page"], row_limit=2,
    )

    assert len(result["rows"]) == 2
    assert len(requests) == 2
    assert requests[0].url.raw_path == (
        b"/webmasters/v3/sites/sc-domain%3Aexample.com/searchAnalytics/query"
    )
    assert requests[0].headers["Authorization"] == "Bearer secret-token"
    assert json.loads(requests[1].content)["startRow"] == 2


def test_search_analytics_bounds_page_size():
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"rows": []})

    _client(handler).query_search_analytics(
        "2026-07-01", "2026-07-31", dimensions=["query"], row_limit=99999,
    )
    assert bodies == [{
        "startDate": "2026-07-01",
        "endDate": "2026-07-31",
        "dimensions": ["query"],
        "type": "web",
        "dataState": "final",
        "rowLimit": 25000,
        "startRow": 0,
    }]


def test_identical_search_query_uses_cache():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"rows": []})

    client = _client(handler)
    for _ in range(2):
        client.query_search_analytics(
            "2026-07-01", "2026-07-31", dimensions=["page"]
        )
    assert calls == 1


def test_inspect_and_sitemaps_request_shapes():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("index:inspect"):
            return httpx.Response(200, json={"inspectionResult": {"indexStatusResult": {}}})
        return httpx.Response(200, json={"sitemap": [{"path": "https://example.com/sitemap.xml"}]})

    client = _client(handler)
    client.inspect_url("https://example.com/a", language_code="en-US")
    result = client.list_sitemaps()

    assert requests[0].url.path == "/v1/urlInspection/index:inspect"
    assert json.loads(requests[0].content) == {
        "inspectionUrl": "https://example.com/a",
        "siteUrl": "sc-domain:example.com",
        "languageCode": "en-US",
    }
    assert requests[1].method == "GET"
    assert result["sitemap"][0]["path"].endswith("sitemap.xml")


@pytest.mark.parametrize(
    ("status", "expected"),
    [(401, "authentication"), (403, "authorization"), (429, "quota"), (503, "server")],
)
def test_http_errors_are_typed_and_do_not_leak_credentials(status, expected):
    from audit_rules.providers.gsc_client import GSCAPIError

    def handler(request):
        return httpx.Response(status, text="secret-token sensitive-response-body")

    with pytest.raises(GSCAPIError) as caught:
        _client(handler).list_sitemaps()

    message = str(caught.value)
    assert expected in message.lower()
    assert "secret-token" not in message
    assert "sensitive-response-body" not in message


def test_timeout_and_invalid_json_are_sanitized():
    from audit_rules.providers.gsc_client import GSCAPIError

    def timeout_handler(request):
        raise httpx.ReadTimeout("secret-token", request=request)

    with pytest.raises(GSCAPIError, match="timed out"):
        _client(timeout_handler).list_sitemaps()

    def invalid_handler(request):
        return httpx.Response(200, content=b"not-json")

    with pytest.raises(GSCAPIError, match="invalid JSON"):
        _client(invalid_handler).list_sitemaps()
