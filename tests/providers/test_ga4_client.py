"""GA4 Admin and Data REST client contract tests."""

import json

import httpx
import pytest


def _client(handler):
    from audit_rules.providers.ga4_client import GA4Client
    return GA4Client("token-secret", "12345", transport=httpx.MockTransport(handler))


def test_property_lookup_normalizes_id_and_uses_oauth_header():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"name": "properties/12345", "displayName": "Site"})

    result = _client(handler).get_property()
    assert requests[0].url.path == "/v1beta/properties/12345"
    assert requests[0].headers["Authorization"] == "Bearer token-secret"
    assert result["displayName"] == "Site"


def test_key_events_paginates_with_maximum_page_size():
    requests = []
    def handler(request):
        requests.append(request)
        if request.url.params.get("pageToken"):
            return httpx.Response(200, json={"keyEvents": [{"eventName": "purchase"}]})
        return httpx.Response(200, json={"keyEvents": [{"eventName": "generate_lead"}],
                                         "nextPageToken": "next"})

    events = _client(handler).list_key_events()
    assert [event["eventName"] for event in events] == ["generate_lead", "purchase"]
    assert requests[0].url.params["pageSize"] == "200"
    assert requests[1].url.params["pageToken"] == "next"


def test_run_report_builds_data_api_request_and_is_cached():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"rows": []})

    client = _client(handler)
    for _ in range(2):
        client.run_report("2026-07-01", "2026-07-28",
                          dimensions=["eventName"], metrics=["eventCount"])
    assert len(requests) == 1
    assert requests[0].url.path == "/v1beta/properties/12345:runReport"
    assert json.loads(requests[0].content) == {
        "dateRanges": [{"startDate": "2026-07-01", "endDate": "2026-07-28"}],
        "dimensions": [{"name": "eventName"}],
        "metrics": [{"name": "eventCount"}],
        "limit": "100000",
    }


@pytest.mark.parametrize(
    ("status", "label"),
    [(401, "authentication"), (403, "authorization"), (429, "quota"), (503, "server")],
)
def test_errors_are_sanitized(status, label):
    from audit_rules.providers.ga4_client import GA4APIError
    def handler(request):
        return httpx.Response(status, text="token-secret private-property")

    with pytest.raises(GA4APIError) as caught:
        _client(handler).get_property()
    assert label in str(caught.value).lower()
    assert "token-secret" not in str(caught.value)
    assert "private-property" not in str(caught.value)


def test_invalid_json_object_is_rejected():
    from audit_rules.providers.ga4_client import GA4APIError
    def handler(request):
        return httpx.Response(200, content=b"not-json")
    with pytest.raises(GA4APIError, match="invalid JSON"):
        _client(handler).get_property()
