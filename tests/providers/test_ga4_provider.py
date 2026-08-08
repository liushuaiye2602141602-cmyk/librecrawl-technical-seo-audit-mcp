"""GA4 provider configuration and normalization tests."""

from datetime import date

from audit_rules.context import SiteContext


class StubClient:
    def __init__(self, fail=()):
        self.fail = set(fail)
        self.report_calls = []

    def get_property(self):
        from audit_rules.providers.ga4_client import GA4APIError
        if "property" in self.fail:
            raise GA4APIError("GA4 authorization failed (HTTP 403)")
        return {"name": "properties/123", "displayName": "Example",
                "propertyType": "PROPERTY_TYPE_ORDINARY", "deleteTime": ""}

    def list_key_events(self):
        from audit_rules.providers.ga4_client import GA4APIError
        if "key_events" in self.fail:
            raise GA4APIError("GA4 authorization failed (HTTP 403)")
        return [{"eventName": "generate_lead", "countingMethod": "ONCE_PER_EVENT"}]

    def run_report(self, start, end, *, dimensions, metrics):
        from audit_rules.providers.ga4_client import GA4APIError
        family = "daily_activity" if dimensions == ["date"] else "event_counts"
        self.report_calls.append((family, start, end, dimensions, metrics))
        if family in self.fail:
            raise GA4APIError("GA4 quota exceeded (HTTP 429)")
        if family == "daily_activity":
            return {"rows": [{"dimensionValues": [{"value": "20260806"}],
                               "metricValues": [{"value": "12"}, {"value": "8"}]}]}
        return {"rows": [{"dimensionValues": [{"value": "generate_lead"}],
                           "metricValues": [{"value": "3"}]}]}


def test_configuration_gate(monkeypatch):
    from audit_rules.providers.ga4_provider import GA4DataProvider
    monkeypatch.setenv("MASTER_AUDIT_V3_ENABLED", "true")
    monkeypatch.setenv("MASTER_AUDIT_GA4_ENABLED", "true")
    monkeypatch.delenv("GA4_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("GA4_PROPERTY_ID", "123")
    assert GA4DataProvider().name == "GA4 API"
    assert GA4DataProvider().is_available() is False


def test_collects_property_key_events_activity_and_event_counts():
    from audit_rules.providers.ga4_provider import GA4DataProvider
    client = StubClient()
    provider = GA4DataProvider(
        access_token="token", property_id="properties/123", client=client,
        today=date(2026, 8, 9))
    shared = {}

    assert provider.collect(SiteContext(), [], shared)
    assert client.report_calls[0][1:3] == ("2026-07-09", "2026-08-05")
    assert shared["ga4"]["daily_activity"] == [
        {"date": "20260806", "sessions": 12, "totalUsers": 8}]
    assert shared["ga4"]["event_counts"] == {"generate_lead": 3}
    assert shared["ga4"]["key_events"][0]["eventName"] == "generate_lead"


def test_partial_and_all_error_semantics_are_sanitized():
    from audit_rules.providers.ga4_provider import GA4DataProvider
    shared = {}
    provider = GA4DataProvider(
        access_token="token", property_id="123",
        client=StubClient(fail={"event_counts"}), today=date(2026, 8, 9))
    assert provider.collect(SiteContext(), [], shared)
    assert shared["ga4"]["errors"] == ["event_counts:GA4APIError"]

    shared = {}
    provider = GA4DataProvider(
        access_token="token", property_id="123",
        client=StubClient(fail={"property", "key_events", "daily_activity", "event_counts"}),
        today=date(2026, 8, 9))
    assert provider.collect(SiteContext(), [], shared) is False
    assert provider.runtime_available is False


def test_integration_registers_ga4_provider(monkeypatch):
    from audit_rules import integration
    from audit_rules.providers.ga4_provider import GA4DataProvider
    monkeypatch.delenv("GA4_ACCESS_TOKEN", raising=False)
    integration.reset_runner_cache()
    runner = integration._get_runner()
    assert isinstance(runner.providers["GA4 API"], GA4DataProvider)
    assert runner.providers["GA4 API"].is_available() is False
