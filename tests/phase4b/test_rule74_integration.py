"""TDD integration coverage for Rule 74 snapshot regressions."""

from __future__ import annotations

from audit_rules.context import PageContext, SiteContext
from audit_rules.snapshot_diff import SnapshotChange


def _export() -> dict:
    return {
        "site_check": {},
        "pages": [
            {
                "url": "https://example.com/a",
                "status_code": 200,
                "title": "Alpha",
                "meta_description": "Alpha description",
                "h1": "Alpha heading",
                "canonical_url": "https://example.com/a",
                "robots": "index, follow",
                "word_count": 500,
            }
        ],
        "links": [],
    }


def _runner():
    from audit_rules.registry import load_registry
    from audit_rules.runner import RuleRunner

    return RuleRunner(load_registry())


def _rule74():
    return next(rule for rule in _runner().registry if rule.audit_id == 74)


def test_rule74_without_baseline_is_not_checked_unknown() -> None:
    """Registering the adapter must not turn a missing baseline into PASS."""
    _, coverage = _runner().run_from_export(
        _export(),
        base_url="https://example.com",
    )

    row = next(item for item in coverage if item.audit_id == 74)
    assert row.execution_status.value == "NOT_CHECKED"
    assert row.result_status.value == "UNKNOWN"
    assert row.evaluated_count == 0
    assert "SnapshotBaseline" in row.not_checked_reason


def test_rule74_identical_valid_baseline_is_executed_pass() -> None:
    """An explicit comparison with zero changes is a real executed PASS."""
    _, coverage = _runner().run_from_export(
        _export(),
        base_url="https://example.com",
        existing_data={
            "snapshot_baseline_available": True,
            "snapshot_changes": [],
        },
    )

    row = next(item for item in coverage if item.audit_id == 74)
    assert row.execution_status.value == "EXECUTED_FULL"
    assert row.result_status.value == "PASS"
    assert row.not_checked_reason == ""


def test_rule74_critical_regression_produces_error_with_evidence() -> None:
    """Losing an indexable URL must remain an actionable Error finding."""
    from audit_rules.checks.snapshot_diff import check_regression_test

    change = SnapshotChange(
        url="https://example.com/a",
        change_type="URL_REMOVED",
        classification="REGRESSED",
        field="url",
        before="https://example.com/a",
        after=None,
        evidence="url changed: before=https://example.com/a; after=",
    )
    findings = check_regression_test(
        _rule74(),
        SiteContext(base_url="https://example.com"),
        [PageContext(url="https://example.com/a", status_code=200)],
        {"snapshot_changes": [change]},
    )

    assert len(findings) == 1
    assert findings[0].severity == "Error"
    assert findings[0].confidence == 1.0
    assert "before=https://example.com/a" in findings[0].evidence
    assert findings[0].detected_value == "URL_REMOVED: REGRESSED"


def test_rule74_noncritical_new_issue_produces_warning() -> None:
    """Metadata loss must not be silently reduced to informational output."""
    from audit_rules.checks.snapshot_diff import check_regression_test

    change = SnapshotChange(
        url="https://example.com/a",
        change_type="TITLE_CHANGED",
        classification="NEW_ISSUE",
        field="title",
        before="Alpha",
        after="",
        evidence="title changed: before=Alpha; after=",
    )
    finding = check_regression_test(
        _rule74(),
        SiteContext(base_url="https://example.com"),
        [],
        {"snapshot_changes": [change]},
    )[0]

    assert finding.severity == "Warning"
    assert finding.url == "https://example.com/a"


def test_rule74_fixed_and_informational_changes_are_info() -> None:
    """Improvements and neutral rewrites must not inflate issue counts."""
    from audit_rules.checks.snapshot_diff import check_regression_test

    changes = [
        SnapshotChange(
            url="https://example.com/a",
            change_type="STATUS_CHANGED",
            classification="FIXED",
            field="status",
            before=404,
            after=200,
            evidence="status changed: before=404; after=200",
        ),
        SnapshotChange(
            url="https://example.com/a",
            change_type="CONTENT_CHANGED",
            classification="INFORMATIONAL_CHANGE",
            field="content_fingerprint",
            before="old",
            after="new",
            evidence="content_fingerprint changed: before=old; after=new",
        ),
    ]
    findings = check_regression_test(
        _rule74(),
        SiteContext(base_url="https://example.com"),
        [],
        {"snapshot_changes": changes},
    )

    assert [item.severity for item in findings] == ["Info", "Info"]


def test_rule74_registered_and_zero_new_auto() -> None:
    """Forgetting CSV or adapter registration must break source-of-truth facts."""
    from collections import Counter

    from audit_rules.adapters import CompatibilityHarness
    from audit_rules.registry import load_registry

    registry = load_registry()
    harness = CompatibilityHarness(registry)
    counts = Counter(rule.impl_status.value for rule in registry)

    assert harness._adapters["regression_test"].__name__ == "check_regression_test"
    assert len(harness._adapters) == 64
    assert counts == {
        "EXISTING_FULL": 18,
        "EXISTING_PARTIAL": 42,
        "NEW_EXTERNAL_DATA": 7,
        "NEW_MANUAL": 13,
    }
