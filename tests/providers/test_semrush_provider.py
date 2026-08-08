"""Semrush provider configuration and runner tests."""

from audit_rules.context import SiteContext


class StubClient:
    def __init__(self, fail=()):
        self.fail = set(fail)
        self.calls = []

    def backlinks_overview(self, target):
        from audit_rules.providers.semrush_client import SemrushAPIError
        self.calls.append(("overview", target))
        if "overview" in self.fail:
            raise SemrushAPIError("Semrush quota exceeded (HTTP 429)")
        return {"backlinks_count": 100, "domains_count": 20, "score": 55,
                "lost_count": 2, "new_count": 4}

    def lost_backlinks(self, target, *, limit):
        from audit_rules.providers.semrush_client import SemrushAPIError
        self.calls.append(("lost", target, limit))
        if "lost" in self.fail:
            raise SemrushAPIError("Semrush quota exceeded (HTTP 429)")
        return {"links": [{"source_url": "https://ref.example/a",
                            "target_url": "https://example.com/a",
                            "domain_score": 60, "is_lost": True}],
                "total": 1, "limit": limit, "truncated": False}


def test_configuration_gate(monkeypatch):
    from audit_rules.providers.semrush_provider import SemrushDataProvider

    monkeypatch.setenv("MASTER_AUDIT_V3_ENABLED", "true")
    monkeypatch.setenv("MASTER_AUDIT_SEMRUSH_ENABLED", "true")
    monkeypatch.delenv("SEMRUSH_API_KEY", raising=False)
    assert SemrushDataProvider().name == "Semrush API"
    assert SemrushDataProvider().is_available() is False


def test_collect_uses_configured_target_and_preserves_payload():
    from audit_rules.providers.semrush_provider import SemrushDataProvider

    client = StubClient()
    provider = SemrushDataProvider(
        api_key="key", target="configured.example", client=client, lost_link_limit=25)
    shared = {}

    assert provider.collect(SiteContext(base_url="https://ignored.example"), [], shared)
    assert client.calls == [
        ("overview", "configured.example"), ("lost", "configured.example", 25)]
    assert shared["semrush"]["overview"]["domains_count"] == 20
    assert shared["semrush"]["lost_links"][0]["domain_score"] == 60


def test_collect_derives_target_from_site_and_marks_partial_failure():
    from audit_rules.providers.semrush_provider import SemrushDataProvider

    client = StubClient(fail={"lost"})
    provider = SemrushDataProvider(api_key="key", client=client)
    shared = {}

    assert provider.collect(SiteContext(base_url="https://www.example.com/path"), [], shared)
    assert client.calls[0] == ("overview", "www.example.com")
    assert shared["semrush"]["errors"] == ["lost_links:SemrushAPIError"]


def test_all_failures_make_runtime_source_unavailable():
    from audit_rules.providers.semrush_provider import SemrushDataProvider

    provider = SemrushDataProvider(
        api_key="key", client=StubClient(fail={"overview", "lost"}))
    shared = {}
    assert provider.collect(SiteContext(base_url="https://example.com"), [], shared) is False
    assert provider.runtime_available is False


def test_integration_registers_semrush_provider(monkeypatch):
    from audit_rules import integration
    from audit_rules.providers.semrush_provider import SemrushDataProvider

    monkeypatch.delenv("SEMRUSH_API_KEY", raising=False)
    integration.reset_runner_cache()
    runner = integration._get_runner()
    assert isinstance(runner.providers["Semrush API"], SemrushDataProvider)
    assert runner.providers["Semrush API"].is_available() is False
