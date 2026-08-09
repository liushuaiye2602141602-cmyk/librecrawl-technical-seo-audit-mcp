"""Rendered-DOM and availability aggregate snapshot provider contracts."""

from datetime import datetime, timezone
import json

from audit_rules.context import SiteContext


def _now():
    return datetime.now(timezone.utc).isoformat()


def _render_snapshot(**overrides):
    data = {
        "schema_version": "render-audit-v1", "collected_at": _now(),
        "site_url": "https://example.com",
        "pages": [{
            "url": "https://example.com/products",
            "raw_text_chars": 1000, "rendered_text_chars": 1600,
            "raw_internal_links": 10, "rendered_internal_links": 15,
            "initial_items": 12, "after_scroll_items": 24,
            "load_more_requires_interaction": True,
            "crawlable_pagination_fallback": False,
            "lazy_images_without_fallback": 3,
        }],
    }
    data.update(overrides)
    return data


def _availability_snapshot(**overrides):
    data = {
        "schema_version": "availability-monitor-v1", "collected_at": _now(),
        "site_url": "https://example.com", "window_hours": 168,
        "endpoints": [{
            "url": "https://example.com/", "total_checks": 2016,
            "failed_checks": 3, "five_xx_checks": 2,
            "availability_pct": 99.85, "p95_ms": 1200,
            "locations": 3,
        }],
    }
    data.update(overrides)
    return data


def _write(tmp_path, name, data):
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_render_provider_is_opt_in_and_normalizes_counts(tmp_path, monkeypatch):
    from audit_rules.providers.render_snapshot_provider import RenderSnapshotProvider

    path = _write(tmp_path, "render.json", _render_snapshot())
    monkeypatch.setenv("MASTER_AUDIT_V3_ENABLED", "true")
    monkeypatch.delenv("MASTER_AUDIT_RENDER_ENABLED", raising=False)
    assert RenderSnapshotProvider(path=str(path)).is_available() is False
    monkeypatch.setenv("MASTER_AUDIT_RENDER_ENABLED", "true")
    provider = RenderSnapshotProvider(path=str(path))
    shared = {}
    assert provider.is_available() is True
    assert provider.collect(SiteContext(base_url="https://example.com"), [], shared)
    assert shared["render_snapshot"]["pages"][0]["rendered_text_chars"] == 1600


def test_render_provider_rejects_raw_content_host_mismatch_and_page_overflow(tmp_path, monkeypatch):
    from audit_rules.providers.render_snapshot_provider import RenderSnapshotProvider

    monkeypatch.setenv("MASTER_AUDIT_V3_ENABLED", "true")
    monkeypatch.setenv("MASTER_AUDIT_RENDER_ENABLED", "true")
    cases = [
        _render_snapshot(raw_html="<p>private content</p>"),
        _render_snapshot(site_url="https://other.example"),
        _render_snapshot(pages=[_render_snapshot()["pages"][0]] * 501),
    ]
    for index, data in enumerate(cases):
        shared = {}
        provider = RenderSnapshotProvider(path=str(_write(tmp_path, f"render-{index}.json", data)))
        assert provider.collect(SiteContext(base_url="https://example.com"), [], shared) is False
        assert shared["render_snapshot"]["errors"]


def test_availability_provider_is_opt_in_and_normalizes_window(tmp_path, monkeypatch):
    from audit_rules.providers.availability_snapshot_provider import AvailabilitySnapshotProvider

    path = _write(tmp_path, "availability.json", _availability_snapshot())
    monkeypatch.setenv("MASTER_AUDIT_V3_ENABLED", "true")
    monkeypatch.setenv("MASTER_AUDIT_AVAILABILITY_ENABLED", "true")
    provider = AvailabilitySnapshotProvider(path=str(path))
    shared = {}
    assert provider.is_available()
    assert provider.collect(SiteContext(base_url="https://example.com"), [], shared)
    assert shared["availability_snapshot"]["window_hours"] == 168
    assert shared["availability_snapshot"]["endpoints"][0]["five_xx_checks"] == 2


def test_availability_provider_rejects_secrets_bad_totals_and_cross_host_urls(tmp_path, monkeypatch):
    from audit_rules.providers.availability_snapshot_provider import AvailabilitySnapshotProvider

    monkeypatch.setenv("MASTER_AUDIT_V3_ENABLED", "true")
    monkeypatch.setenv("MASTER_AUDIT_AVAILABILITY_ENABLED", "true")
    base = _availability_snapshot()["endpoints"][0]
    cases = [
        _availability_snapshot(api_token="secret"),
        _availability_snapshot(endpoints=[{**base, "failed_checks": 3000}]),
        _availability_snapshot(endpoints=[{**base, "url": "https://other.example/"}]),
    ]
    for index, data in enumerate(cases):
        shared = {}
        provider = AvailabilitySnapshotProvider(
            path=str(_write(tmp_path, f"availability-{index}.json", data)))
        assert provider.collect(SiteContext(base_url="https://example.com"), [], shared) is False
        assert shared["availability_snapshot"]["errors"]


def test_integration_registers_remaining_snapshot_providers(monkeypatch):
    from audit_rules import integration
    from audit_rules.providers.availability_snapshot_provider import AvailabilitySnapshotProvider
    from audit_rules.providers.render_snapshot_provider import RenderSnapshotProvider

    integration.reset_runner_cache()
    runner = integration._get_runner()
    assert isinstance(runner.providers["Rendered DOM Snapshot"], RenderSnapshotProvider)
    assert isinstance(runner.providers["Availability Monitor"], AvailabilitySnapshotProvider)
