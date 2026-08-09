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

    def referring_domains(self, target, *, limit):
        self.calls.append(("referring_domains", target, limit))
        if "referring_domains" in self.fail:
            raise RuntimeError("unavailable")
        return {"domains": [{"domain": "ref.example", "domain_score": 60}],
                "total": 1, "limit": limit, "truncated": False}

    def domain_keywords(self, target, *, database, limit):
        self.calls.append(("keywords", target, database, limit))
        if "keywords" in self.fail:
            raise RuntimeError("unavailable")
        return [{"keyword": "seo audit", "position": 4,
                 "previous_position": 7, "position_change": 3,
                 "url": "https://example.com/a"}]

    def organic_competitors(self, target, *, database, limit):
        self.calls.append(("competitors", target, database, limit))
        if "competitors" in self.fail:
            raise RuntimeError("unavailable")
        return [{"domain": "competitor.example", "common_keywords": 25}]


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
        api_key="key", target="example.com", client=client, lost_link_limit=25)
    shared = {}

    assert provider.collect(SiteContext(base_url="https://shop.example.com"), [], shared)
    assert client.calls == [
        ("overview", "example.com"), ("lost", "example.com", 25),
        ("referring_domains", "example.com", 100),
        ("keywords", "example.com", "us", 100),
        ("competitors", "example.com", "us", 25)]
    assert shared["semrush"]["overview"]["domains_count"] == 20
    assert shared["semrush"]["lost_links"][0]["domain_score"] == 60
    assert shared["semrush"]["referring_domains"][0]["domain"] == "ref.example"
    assert shared["semrush"]["domain_keywords"][0]["position_change"] == 3
    assert shared["semrush"]["organic_competitors"][0]["common_keywords"] == 25


def test_rejects_cross_site_configured_target_before_calling_semrush():
    from audit_rules.providers.semrush_provider import SemrushDataProvider

    client = StubClient()
    provider = SemrushDataProvider(api_key="key", target="other.example", client=client)
    shared = {}

    assert provider.collect(SiteContext(base_url="https://example.com"), [], shared) is False
    assert client.calls == []
    assert shared["semrush"]["errors"] == ["target:SiteMismatch"]


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
        api_key="key", client=StubClient(
            fail={"overview", "lost", "referring_domains", "keywords", "competitors"}))
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
