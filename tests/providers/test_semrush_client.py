"""Semrush Backlinks API v4 client contract tests."""

import httpx
import pytest


def _client(handler):
    from audit_rules.providers.semrush_client import SemrushClient

    return SemrushClient("secret-key", transport=httpx.MockTransport(handler))


def test_overview_uses_v4_auth_and_expected_parameters():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"meta": {"success": True}, "data": {
            "backlinks_count": 20, "domains_count": 5, "score": 42}})

    result = _client(handler).backlinks_overview("example.com")

    request = requests[0]
    assert request.url.path == "/apis/v4/backlinks/v1/overview"
    assert request.headers["Authorization"] == "Apikey secret-key"
    assert request.url.params["url"] == "example.com"
    assert request.url.params["scope"] == "ROOT_DOMAIN"
    assert result["domains_count"] == 5


def test_lost_links_are_bounded_and_request_explicit_fields():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={
            "meta": {"success": True, "total": 200},
            "data": [{"source_url": "https://ref.example/a", "is_lost": True}],
        })

    result = _client(handler).lost_backlinks("example.com", limit=9999)

    params = requests[0].url.params
    assert requests[0].url.path == "/apis/v4/backlinks/v1/links"
    assert params["filter"] == "is_lost = true"
    assert params["order_by"] == "domain_score"
    assert params["direction"] == "DESC"
    assert params["limit"] == "500"
    assert "target_url" in params["fields"]
    assert result["truncated"] is False
    assert result["total"] == 200


def test_lost_links_marks_result_truncated():
    def handler(request):
        return httpx.Response(200, json={
            "meta": {"success": True, "total": 501}, "data": []})

    assert _client(handler).lost_backlinks("example.com", limit=500)["truncated"] is True


def test_referring_domains_use_v4_and_are_bounded():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={
            "meta": {"success": True, "total": 700},
            "data": [{"domain": "ref.example", "domain_score": 60,
                      "backlinks_count": 5}],
        })

    result = _client(handler).referring_domains("example.com", limit=900)

    assert requests[0].url.path == "/apis/v4/backlinks/v1/ref-domains"
    assert requests[0].url.params["limit"] == "500"
    assert result["domains"][0]["domain"] == "ref.example"
    assert result["truncated"] is True


def test_identical_requests_are_cached():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"meta": {"success": True}, "data": {}})

    client = _client(handler)
    client.backlinks_overview("example.com")
    client.backlinks_overview("example.com")
    assert calls == 1


def test_domain_keywords_are_bounded_and_normalized_from_analytics_csv():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, text=(
            "Keyword;Position;Previous Position;Position Difference;Search Volume;Url;Traffic\n"
            "seo audit;4;7;3;1900;https://example.com/a;12.5\n"))

    rows = _client(handler).domain_keywords("example.com", database="us", limit=9999)

    request = requests[0]
    assert request.url.path == "/"
    assert request.url.params["type"] == "domain_organic"
    assert request.url.params["key"] == "secret-key"
    assert request.url.params["display_limit"] == "500"
    assert rows == [{
        "keyword": "seo audit", "position": 4, "previous_position": 7,
        "position_change": 3, "search_volume": 1900,
        "url": "https://example.com/a", "traffic_pct": 12.5,
    }]


def test_organic_competitors_are_bounded_and_normalized():
    def handler(request):
        return httpx.Response(200, text=(
            "Domain;Competition Level;Common Keywords;Organic Keywords;Organic Traffic\n"
            "competitor.example;0.42;25;800;1200\n"))

    rows = _client(handler).organic_competitors(
        "example.com", database="uk", limit=10)

    assert rows == [{
        "domain": "competitor.example", "competition_level": 0.42,
        "common_keywords": 25, "organic_keywords": 800,
        "organic_traffic": 1200,
    }]


@pytest.mark.parametrize(
    ("status", "label"),
    [(401, "authentication"), (403, "authorization"), (429, "quota"), (500, "server")],
)
def test_http_errors_are_sanitized(status, label):
    from audit_rules.providers.semrush_client import SemrushAPIError

    def handler(request):
        return httpx.Response(status, text="secret-key paid-account-detail")

    with pytest.raises(SemrushAPIError) as caught:
        _client(handler).backlinks_overview("example.com")
    assert label in str(caught.value).lower()
    assert "secret-key" not in str(caught.value)
    assert "paid-account-detail" not in str(caught.value)


def test_api_level_error_and_invalid_payload_are_rejected():
    from audit_rules.providers.semrush_client import SemrushAPIError

    def api_error(request):
        return httpx.Response(200, json={
            "meta": {"success": False}, "message": "secret-key invalid"})

    with pytest.raises(SemrushAPIError, match="unsuccessful response"):
        _client(api_error).backlinks_overview("example.com")

    def bad_data(request):
        return httpx.Response(200, json={"meta": {"success": True}, "data": "bad"})

    with pytest.raises(SemrushAPIError, match="invalid data"):
        _client(bad_data).backlinks_overview("example.com")
