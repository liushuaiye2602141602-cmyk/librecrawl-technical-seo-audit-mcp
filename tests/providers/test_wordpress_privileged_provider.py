"""Read-only WordPress privileged snapshot provider contracts."""

from __future__ import annotations

from datetime import datetime, timezone
import json


def _snapshot(**overrides):
    data = {
        "schema_version": "wordpress-audit-v1",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "site_url": "https://example.com",
        "core": {"version": "6.6.1", "update_available": True,
                 "vulnerable": False},
        "php": {"version": "8.2.20"},
        "plugins": [
            {"slug": "seo-plugin", "version": "1.2.3", "status": "active",
             "update_available": True, "last_updated_days": 12,
             "abandoned": False, "vulnerable": False},
        ],
        "themes": [
            {"slug": "site-theme", "version": "4.5.6", "status": "active",
             "update_available": False, "last_updated_days": 60,
             "abandoned": False, "vulnerable": False},
        ],
        "cron_events": [
            {"hook": "daily_cleanup", "interval_seconds": 86400,
             "overdue_seconds": 0},
        ],
        "autoload": {
            "total_bytes": 500000,
            "largest_options": [{"name": "plugin_cache", "bytes": 120000}],
        },
        "administrators": [
            {"two_factor_enabled": True},
            {"two_factor_enabled": False},
        ],
    }
    data.update(overrides)
    return data


def _write(tmp_path, data):
    path = tmp_path / "wordpress-audit.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_provider_is_opt_in_and_requires_existing_snapshot(tmp_path, monkeypatch):
    from audit_rules.providers.wordpress_privileged_provider import WordPressPrivilegedProvider

    path = _write(tmp_path, _snapshot())
    monkeypatch.setenv("MASTER_AUDIT_V3_ENABLED", "true")
    monkeypatch.delenv("MASTER_AUDIT_WORDPRESS_ENABLED", raising=False)
    assert WordPressPrivilegedProvider(path=str(path)).is_available() is False

    monkeypatch.setenv("MASTER_AUDIT_WORDPRESS_ENABLED", "true")
    assert WordPressPrivilegedProvider(path=str(path)).is_available() is True
    assert WordPressPrivilegedProvider(path=str(tmp_path / "missing.json")).is_available() is False


def test_collect_normalizes_privileged_snapshot_without_identities_or_values(tmp_path, monkeypatch):
    from audit_rules.context import SiteContext
    from audit_rules.providers.wordpress_privileged_provider import WordPressPrivilegedProvider

    raw = _snapshot(
        administrators=[
            {"two_factor_enabled": False},
        ],
        autoload={
            "total_bytes": 900000,
            "largest_options": [
                {"name": "plugin_cache", "bytes": 150000},
            ],
        },
    )
    path = _write(tmp_path, raw)
    monkeypatch.setenv("MASTER_AUDIT_V3_ENABLED", "true")
    monkeypatch.setenv("MASTER_AUDIT_WORDPRESS_ENABLED", "true")
    provider = WordPressPrivilegedProvider(path=str(path))
    site = SiteContext(base_url="https://example.com/shop")
    shared = {}

    assert provider.collect(site, [], shared) is True
    assert site.site_profile == "wordpress"
    payload = shared["wordpress_privileged"]
    assert payload["admin_total"] == 1
    assert payload["admin_without_2fa"] == 1
    assert payload["autoload"]["largest_options"] == [
        {"name": "plugin_cache", "bytes": 150000}
    ]
    serialized = json.dumps(payload)
    assert "username" not in serialized
    assert "email" not in serialized
    assert '"value"' not in serialized


def test_collect_rejects_schema_host_secret_and_stale_snapshots(tmp_path, monkeypatch):
    from audit_rules.context import SiteContext
    from audit_rules.providers.wordpress_privileged_provider import WordPressPrivilegedProvider

    monkeypatch.setenv("MASTER_AUDIT_V3_ENABLED", "true")
    monkeypatch.setenv("MASTER_AUDIT_WORDPRESS_ENABLED", "true")
    cases = [
        _snapshot(schema_version="wordpress-audit-v0"),
        _snapshot(site_url="https://other.example"),
        _snapshot(api_token="must-not-be-accepted"),
        _snapshot(administrators=[{
            "username": "private-admin", "two_factor_enabled": True}]),
        _snapshot(autoload={"total_bytes": 12, "largest_options": [{
            "name": "x", "bytes": 12, "value": "private"}]}),
        _snapshot(collected_at="2020-01-01T00:00:00+00:00"),
    ]
    for index, raw in enumerate(cases):
        path = tmp_path / f"bad-{index}.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        shared = {}
        provider = WordPressPrivilegedProvider(path=str(path), max_age_hours=168)
        assert provider.collect(SiteContext(base_url="https://example.com"), [], shared) is False
        assert shared["wordpress_privileged"]["errors"]


def test_invalid_component_record_fails_closed(tmp_path, monkeypatch):
    from audit_rules.context import SiteContext
    from audit_rules.providers.wordpress_privileged_provider import WordPressPrivilegedProvider

    path = _write(tmp_path, _snapshot(plugins=[{"slug": "x", "status": "active"}]))
    monkeypatch.setenv("MASTER_AUDIT_V3_ENABLED", "true")
    monkeypatch.setenv("MASTER_AUDIT_WORDPRESS_ENABLED", "true")
    shared = {}
    assert WordPressPrivilegedProvider(path=str(path)).collect(
        SiteContext(base_url="https://example.com"), [], shared) is False


def test_integration_registers_wordpress_provider(monkeypatch):
    from audit_rules import integration
    from audit_rules.providers.wordpress_privileged_provider import WordPressPrivilegedProvider

    monkeypatch.delenv("WP_AUDIT_EXPORT_PATH", raising=False)
    integration.reset_runner_cache()
    runner = integration._get_runner()
    assert isinstance(runner.providers["WordPress Privileged"], WordPressPrivilegedProvider)
    assert runner.providers["WordPress Privileged"].is_available() is False
