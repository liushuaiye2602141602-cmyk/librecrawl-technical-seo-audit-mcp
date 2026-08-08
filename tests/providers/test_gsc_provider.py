"""Production configuration and enrichment tests for the GSC provider."""

from datetime import date

from audit_rules.context import PageContext, SiteContext


class StubClient:
    def __init__(self, *, fail_all=False, fail_inspection_for=()):
        self.fail_all = fail_all
        self.fail_inspection_for = set(fail_inspection_for)
        self.search_calls = []
        self.inspect_calls = []

    def query_search_analytics(self, start_date, end_date, **kwargs):
        from audit_rules.providers.gsc_client import GSCAPIError

        self.search_calls.append((start_date, end_date, kwargs))
        if self.fail_all:
            raise GSCAPIError("GSC authentication failed (HTTP 401)")
        return {"rows": [{
            "keys": ["https://example.com/a", "widget", "usa", "MOBILE"],
            "clicks": 10,
            "impressions": 100,
            "ctr": 0.1,
            "position": 8.0,
        }]}

    def list_sitemaps(self):
        from audit_rules.providers.gsc_client import GSCAPIError

        if self.fail_all:
            raise GSCAPIError("GSC authentication failed (HTTP 401)")
        return {"sitemap": [{"path": "https://example.com/sitemap.xml"}]}

    def inspect_url(self, url):
        from audit_rules.providers.gsc_client import GSCAPIError

        self.inspect_calls.append(url)
        if self.fail_all or url in self.fail_inspection_for:
            raise GSCAPIError("GSC quota exceeded (HTTP 429)")
        return {"inspectionResult": {"indexStatusResult": {
            "verdict": "PASS",
            "googleCanonical": url,
            "userCanonical": url,
        }}}


def _pages():
    return [
        PageContext(url="https://example.com/b", status_code=200),
        PageContext(url="https://example.com/a", status_code=200),
        PageContext(url="https://example.com/not-found", status_code=404),
    ]


def test_provider_configuration_gate(monkeypatch):
    from audit_rules.providers.gsc_provider import GSCDataProvider

    monkeypatch.setenv("MASTER_AUDIT_V3_ENABLED", "true")
    monkeypatch.setenv("MASTER_AUDIT_GSC_ENABLED", "true")
    monkeypatch.delenv("GSC_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("GSC_SITE_URL", "sc-domain:example.com")

    assert GSCDataProvider().name == "GSC API"
    assert GSCDataProvider().aliases == {"GSC API", "GSC"}
    assert GSCDataProvider().is_available() is False


def test_collects_comparable_windows_sitemaps_and_deterministic_inspection_sample():
    from audit_rules.providers.gsc_provider import GSCDataProvider

    client = StubClient()
    provider = GSCDataProvider(
        access_token="token",
        site_url="sc-domain:example.com",
        client=client,
        today=date(2026, 8, 9),
        inspection_limit=1,
    )
    pages = _pages()
    shared = {}

    assert provider.collect(SiteContext(base_url="https://example.com"), pages, shared)
    assert [call[:2] for call in client.search_calls] == [
        ("2026-07-10", "2026-08-06"),
        ("2026-06-12", "2026-07-09"),
    ]
    assert client.search_calls[0][2]["dimensions"] == ["page", "query", "country", "device"]
    assert client.inspect_calls == ["https://example.com/a"]
    assert shared["gsc"]["sitemaps"][0]["path"].endswith("sitemap.xml")
    assert shared["gsc"]["current_rows"][0]["query"] == "widget"
    assert pages[1].gsc_data["inspection"]["googleCanonical"] == "https://example.com/a"


def test_partial_inspection_success_is_preserved_without_leaking_error_detail():
    from audit_rules.providers.gsc_provider import GSCDataProvider

    client = StubClient(fail_inspection_for={"https://example.com/b"})
    provider = GSCDataProvider(
        access_token="token", site_url="sc-domain:example.com", client=client,
        today=date(2026, 8, 9), inspection_limit=2,
    )
    shared = {}

    assert provider.collect(SiteContext(), _pages(), shared)
    assert shared["gsc"]["inspection_attempted"] == 2
    assert shared["gsc"]["inspection_succeeded"] == 1
    assert shared["gsc"]["errors"] == ["url_inspection:GSCAPIError"]


def test_all_api_failures_make_runtime_source_unavailable():
    from audit_rules.providers.gsc_provider import GSCDataProvider

    provider = GSCDataProvider(
        access_token="token", site_url="sc-domain:example.com",
        client=StubClient(fail_all=True), today=date(2026, 8, 9),
    )
    shared = {}

    assert provider.collect(SiteContext(), _pages(), shared) is False
    assert provider.runtime_available is False
    assert set(shared["gsc"]["errors"]) == {
        "search_analytics:GSCAPIError", "sitemaps:GSCAPIError",
        "url_inspection:GSCAPIError",
    }


def test_integration_registers_gsc_provider(monkeypatch):
    from audit_rules import integration
    from audit_rules.providers.gsc_provider import GSCDataProvider

    monkeypatch.delenv("GSC_ACCESS_TOKEN", raising=False)
    integration.reset_runner_cache()
    runner = integration._get_runner()

    assert isinstance(runner.providers["GSC API"], GSCDataProvider)
    assert runner.providers["GSC API"].is_available() is False


def test_runner_uses_gsc_aliases_and_reports_sampled_inspection(monkeypatch):
    from audit_rules.categories import ExecutionStatus, ResultStatus
    from audit_rules.providers.gsc_provider import GSCDataProvider
    from audit_rules.registry import load_registry
    from audit_rules.runner import RuleRunner

    monkeypatch.setenv("MASTER_AUDIT_V3_ENABLED", "true")
    provider = GSCDataProvider(
        access_token="token", site_url="sc-domain:example.com", client=StubClient(),
        today=date(2026, 8, 9), inspection_limit=1)
    runner = RuleRunner(load_registry(), providers={provider.name: provider})
    export = {"site_check": {}, "links": [], "pages": [
        {"url": "https://example.com/a", "status_code": 200,
         "canonical_url": "https://example.com/a"},
        {"url": "https://example.com/b", "status_code": 200,
         "canonical_url": "https://example.com/b"},
    ]}

    _, rows = runner.run_from_export(export, "https://example.com")
    by_id = {row.audit_id: row for row in rows}
    assert by_id[44].execution_status == ExecutionStatus.EXECUTED_PARTIAL
    assert by_id[44].result_status == ResultStatus.PASS
    assert "1/2" in by_id[44].not_checked_reason
    for audit_id in (52, 75, 76):
        assert by_id[audit_id].execution_status == ExecutionStatus.EXECUTED_FULL


def test_runner_all_gsc_errors_are_not_checked_unknown(monkeypatch):
    from audit_rules.categories import ExecutionStatus, ResultStatus
    from audit_rules.providers.gsc_provider import GSCDataProvider
    from audit_rules.registry import load_registry
    from audit_rules.runner import RuleRunner

    monkeypatch.setenv("MASTER_AUDIT_V3_ENABLED", "true")
    provider = GSCDataProvider(
        access_token="token", site_url="sc-domain:example.com",
        client=StubClient(fail_all=True), today=date(2026, 8, 9))
    runner = RuleRunner(load_registry(), providers={provider.name: provider})
    export = {"site_check": {}, "links": [], "pages": [
        {"url": "https://example.com/a", "status_code": 200}]}

    _, rows = runner.run_from_export(export, "https://example.com")
    by_id = {row.audit_id: row for row in rows}
    for audit_id in (44, 52, 75, 76):
        assert by_id[audit_id].execution_status == ExecutionStatus.NOT_CHECKED
        assert by_id[audit_id].result_status == ResultStatus.UNKNOWN
        assert by_id[audit_id].not_checked_reason == "Data source unavailable: GSC API"
