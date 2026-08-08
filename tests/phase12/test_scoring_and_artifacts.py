"""Deterministic audit score and production summary artifact contracts."""

import json

from audit_rules.categories import (
    ExecutionStatus, ImplStatus, Priority, ResultStatus, Scope,
)
from audit_rules.models import CoverageRow, Finding


def _coverage(audit_id, *, category="Technical", priority=Priority.HIGH,
              execution=ExecutionStatus.EXECUTED_FULL):
    return CoverageRow(
        audit_id=audit_id, rule_id=f"rule_{audit_id}", category=category,
        check=f"Rule {audit_id}", priority=priority, scope=Scope.SITE,
        impl_status=ImplStatus.EXISTING_PARTIAL,
        execution_status=execution,
        result_status=(ResultStatus.PASS if execution != ExecutionStatus.NOT_CHECKED
                       else ResultStatus.UNKNOWN),
    )


def _finding(audit_id, *, priority="High", severity="Error", confidence=1.0,
             category="Technical"):
    return Finding(
        audit_id=audit_id, rule_id=f"rule_{audit_id}", url="SITE",
        category=category, priority=priority, severity=severity,
        finding_type="Error", scope="SITE", confidence=confidence,
    )


def test_score_separates_quality_coverage_and_confidence():
    from audit_rules.scoring import compute_audit_score

    coverage = [
        _coverage(1, priority=Priority.CRITICAL),
        _coverage(2, priority=Priority.LOW),
        _coverage(3, execution=ExecutionStatus.NOT_CHECKED),
    ]
    score = compute_audit_score([_finding(1, priority="Critical")], coverage)

    assert score.overall_score == 20.0
    assert score.coverage_pct == 66.67
    assert score.finding_confidence_pct == 100.0
    assert score.executed_rules == 2 and score.eligible_rules == 3


def test_priority_severity_and_confidence_change_penalty_deterministically():
    from audit_rules.scoring import compute_audit_score

    coverage = [
        _coverage(1, priority=Priority.CRITICAL),
        _coverage(2, priority=Priority.LOW),
    ]
    critical_error = compute_audit_score(
        [_finding(1, priority="Critical", severity="Error", confidence=1.0)], coverage)
    low_warning = compute_audit_score(
        [_finding(2, priority="Low", severity="Warning", confidence=1.0)], coverage)
    low_confidence = compute_audit_score(
        [_finding(1, priority="Critical", severity="Error", confidence=0.5)], coverage)

    assert critical_error.overall_score < low_warning.overall_score
    assert critical_error.overall_score < low_confidence.overall_score
    assert compute_audit_score(
        [_finding(1, priority="Critical")], coverage).to_dict() == critical_error.to_dict()


def test_score_is_unknown_when_nothing_executed_and_has_category_breakdown():
    from audit_rules.scoring import compute_audit_score

    unknown = compute_audit_score([], [
        _coverage(1, execution=ExecutionStatus.NOT_CHECKED)])
    assert unknown.overall_score is None
    assert unknown.coverage_pct == 0.0

    score = compute_audit_score(
        [_finding(1, category="Security")],
        [_coverage(1, category="Security"), _coverage(2, category="Content")])
    assert set(score.category_scores) == {"Security", "Content"}
    assert score.category_scores["Security"] < score.category_scores["Content"]


def test_runner_writes_score_and_performance_artifacts(tmp_path, monkeypatch):
    import runner
    from tests.fixtures.psi import make_good_mobile, make_psi_cache

    registered = []
    monkeypatch.setattr(
        runner.state, "add_artifact",
        lambda sid, kind, path: registered.append((kind, path)))

    class Psi:
        _cache = make_psi_cache([make_good_mobile()])
        _strategies = ["mobile"]

    class AuditRunner:
        providers = {"PageSpeed API": Psi()}

    paths = runner._write_v3_summary_artifacts(
        "session-1", [], [_coverage(1)], "example.com", "20260809-1200",
        tmp_path, AuditRunner())

    assert set(paths) == {"audit_score_json", "performance_csv"}
    score_data = json.loads(paths["audit_score_json"].read_text(encoding="utf-8"))
    assert score_data["overall_score"] == 100.0
    assert paths["performance_csv"].read_text(encoding="utf-8-sig").startswith("url,")
    assert [kind for kind, _ in registered] == ["audit_score_json", "performance_csv"]


def test_runner_omits_performance_artifact_without_current_psi_rows(tmp_path, monkeypatch):
    import runner

    registered = []
    monkeypatch.setattr(
        runner.state, "add_artifact",
        lambda sid, kind, path: registered.append((kind, path)))

    class Psi:
        _cache = {}
        _strategies = ["mobile"]

    class AuditRunner:
        providers = {"PageSpeed API": Psi()}

    paths = runner._write_v3_summary_artifacts(
        "session-2", [], [_coverage(1)], "example.com", "20260809-1201",
        tmp_path, AuditRunner())
    assert set(paths) == {"audit_score_json"}
    assert [kind for kind, _ in registered] == ["audit_score_json"]
