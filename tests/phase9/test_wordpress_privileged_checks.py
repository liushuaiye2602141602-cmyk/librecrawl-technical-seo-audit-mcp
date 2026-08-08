"""Rules 36, 64, 65, 68, and 69 privileged snapshot contracts."""

import pytest

from audit_rules.adapters import DataUnavailableError, PartialExecutionError
from audit_rules.context import SiteContext
from audit_rules.registry import load_registry


def _rule(audit_id):
    return next(rule for rule in load_registry() if rule.audit_id == audit_id)


def _wp(**overrides):
    data = {
        "schema_version": "wordpress-audit-v1",
        "core": {"version": "6.6.1", "update_available": False,
                 "vulnerable": False},
        "php": {"version": "8.2.20"},
        "plugins": [], "themes": [], "cron_events": [],
        "autoload": {"total_bytes": 100000, "largest_options": []},
        "admin_total": 2, "admin_without_2fa": 0, "errors": [],
    }
    data.update(overrides)
    return data


def _partial(check, audit_id, payload):
    with pytest.raises(PartialExecutionError) as caught:
        check(_rule(audit_id), SiteContext(site_profile="wordpress"), [],
              {"wordpress_privileged": payload})
    return caught.value


def test_rule_36_flags_updates_and_vulnerable_components():
    from audit_rules.checks.wordpress_privileged import check_wp_updates_security

    payload = _wp(
        core={"version": "6.5", "update_available": True, "vulnerable": False},
        plugins=[{"slug": "old-plugin", "version": "1.0", "status": "active",
                  "update_available": False, "last_updated_days": 30,
                  "abandoned": False, "vulnerable": True}],
        themes=[{"slug": "theme", "version": "2.0", "status": "active",
                 "update_available": True, "last_updated_days": 20,
                 "abandoned": False, "vulnerable": False}],
    )
    result = _partial(check_wp_updates_security, 36, payload)
    detected = " ".join(item.detected_value for item in result.findings).lower()
    assert "core" in detected and "old-plugin" in detected and "theme" in detected
    assert all(item.data_source == "WordPress Privileged" for item in result.findings)
    assert "staging" in str(result).lower()


def test_rule_64_flags_overdue_and_sub_minute_cron():
    from audit_rules.checks.wordpress_privileged import check_wp_cron_tasks

    result = _partial(check_wp_cron_tasks, 64, _wp(cron_events=[
        {"hook": "stuck_job", "interval_seconds": 3600, "overdue_seconds": 900},
        {"hook": "hot_loop", "interval_seconds": 30, "overdue_seconds": 0},
    ]))
    detected = " ".join(item.detected_value for item in result.findings)
    assert "stuck_job" in detected and "hot_loop" in detected
    assert "server-log" in str(result).lower()


def test_rule_65_flags_total_and_large_autoload_options():
    from audit_rules.checks.wordpress_privileged import check_database_autoload_bloat

    result = _partial(check_database_autoload_bloat, 65, _wp(autoload={
        "total_bytes": 900000,
        "largest_options": [{"name": "giant_cache", "bytes": 150000}],
    }))
    assert len(result.findings) == 2
    assert "dba" in str(result).lower()


def test_rule_68_flags_administrators_without_2fa():
    from audit_rules.checks.wordpress_privileged import check_admin_2fa

    result = _partial(check_admin_2fa, 68, _wp(
        admin_total=3, admin_without_2fa=2))
    assert len(result.findings) == 1
    assert "2 of 3" in result.findings[0].detected_value
    assert "waf" in str(result).lower()


def test_rule_69_flags_inactive_abandoned_and_stale_components():
    from audit_rules.checks.wordpress_privileged import check_abandoned_plugins_themes

    components = [
        {"slug": "inactive-one", "version": "1", "status": "inactive",
         "update_available": False, "last_updated_days": 20,
         "abandoned": False, "vulnerable": False},
        {"slug": "stale-one", "version": "1", "status": "active",
         "update_available": False, "last_updated_days": 800,
         "abandoned": False, "vulnerable": False},
        {"slug": "abandoned-one", "version": "1", "status": "active",
         "update_available": False, "last_updated_days": 30,
         "abandoned": True, "vulnerable": False},
    ]
    result = _partial(check_abandoned_plugins_themes, 69, _wp(plugins=components))
    detected = " ".join(item.detected_value for item in result.findings)
    assert all(slug in detected for slug in ("inactive-one", "stale-one", "abandoned-one"))
    assert "collector" in str(result).lower()


@pytest.mark.parametrize("audit_id,check_name", [
    (36, "check_wp_updates_security"),
    (64, "check_wp_cron_tasks"),
    (65, "check_database_autoload_bloat"),
    (68, "check_admin_2fa"),
    (69, "check_abandoned_plugins_themes"),
])
def test_missing_snapshot_never_passes(audit_id, check_name):
    from audit_rules.checks import wordpress_privileged

    with pytest.raises(DataUnavailableError):
        getattr(wordpress_privileged, check_name)(
            _rule(audit_id), SiteContext(site_profile="wordpress"), [], {})


def test_wordpress_checks_are_registered_as_partial_provider_rules():
    from audit_rules.adapters import CompatibilityHarness

    registry = load_registry()
    harness = CompatibilityHarness(registry)
    for audit_id in (36, 64, 65, 68, 69):
        rule = _rule(audit_id)
        assert rule.impl_status.value == "EXISTING_PARTIAL"
        assert "WordPress Privileged" in rule.required_data_sources
        assert rule.rule_id in harness._adapters
