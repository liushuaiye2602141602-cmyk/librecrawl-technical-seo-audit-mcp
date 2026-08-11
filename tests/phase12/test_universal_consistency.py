"""FINAL UNIVERSAL REPORT CONTENT CONSISTENCY LOCK regressions."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

docx = pytest.importorskip("docx")


def _view(**overrides):
    from audit_rules.report_view import build_report_view
    from tests.phase12.test_universal_report_view import (
        _items, _metrics, _tasks,
    )
    kwargs = dict(
        items=_items(), task_rows=_tasks(), metrics=_metrics(),
        manual_rows=[{"audit_id": 53}],
        technology_profile=None, technology_risks=[],
        domain="https://site-a.example/", audit_date="2026-08-11",
        pages_crawled=228,
    )
    kwargs.update(overrides)
    return build_report_view(**kwargs)


def test_management_result_distribution_matches_80_rows():
    view = _view()
    actual = {}
    for item in view.audit_items:
        actual[item["result"]] = actual.get(item["result"], 0) + 1
    assert view.result_distribution == actual


def test_management_execution_distribution_matches_80_rows():
    view = _view()
    actual = {}
    for item in view.audit_items:
        actual[item["execution"]] = actual.get(item["execution"], 0) + 1
    assert view.execution_distribution == actual


def test_management_totals_equal_80():
    view = _view()
    assert sum(view.result_distribution.values()) == 80
    assert sum(view.execution_distribution.values()) == 80


def test_summary_table_and_management_use_same_source(tmp_path):
    from docx import Document
    from audit_rules.report_view import build_report_view
    from audit_rules.docx_report import build_universal_docx
    from tests.phase12.test_universal_report_view import (
        _items, _metrics, _tasks,
    )
    items, tasks, metrics = _items(), _tasks(), _metrics()
    view = build_report_view(
        items, tasks, metrics, manual_rows=[],
        technology_profile=None, technology_risks=[],
        domain="https://site-a.example/", audit_date="2026-08-11",
        pages_crawled=228)
    output = tmp_path / "u.docx"
    build_universal_docx(
        str(output), view_model=view, items=items, task_rows=tasks,
        metrics=metrics, result_counts={}, execution_counts={},
        manual_rows=[], schema_distribution={},
        domain="https://site-a.example/", audit_date="2026-08-11",
        site_name="Site A", pages_crawled=228)
    doc = Document(str(output))
    text = "\n".join(p.text for p in doc.paragraphs)
    text += "\n" + "\n".join(
        c.text for t in doc.tables for r in t.rows for c in r.cells)
    for result, count in view.result_distribution.items():
        assert f"{result}\n{count}" in text
    # The 80-row summary table also contains all 80 audits.
    audits = [p for p in doc.paragraphs
              if p.style.name == "Heading 2" and p.text.startswith("AUDIT #")]
    assert len(audits) == 80


def test_fail_never_says_no_remediation_required():
    item = next(i for i in _view().audit_items if i["result"] == "FAIL")
    assert "no remediation required" not in item["what_to_do"].lower()


def test_fail_never_says_acceptance_criteria_met():
    item = next(i for i in _view().audit_items if i["result"] == "FAIL")
    assert "met" not in item["how_to_verify"].lower()


def test_warning_has_action():
    item = next(i for i in _view().audit_items if i["result"] == "WARNING")
    assert item["what_to_do"]


def test_opportunity_has_optimization_action():
    opps = [i for i in _view().audit_items if i["result"] == "OPPORTUNITY"]
    assert opps and all(i["what_to_do"] for i in opps)


def test_confirmed_issue_has_nonempty_fix():
    for item in _view().audit_items:
        if item["result"] in ("FAIL", "WARNING", "OPPORTUNITY"):
            assert item["what_to_do"]


def test_confirmed_issue_has_nonempty_verification():
    for item in _view().audit_items:
        if item["result"] in ("FAIL", "WARNING", "OPPORTUNITY"):
            assert item["how_to_verify"]


def test_fail_diagnosis_is_not_normal():
    item = next(i for i in _view().audit_items if i["result"] == "FAIL")
    assert item["diagnosis"].lower() != "normal"
    assert item["diagnosis"]


def test_warning_diagnosis_explains_observation():
    item = next(i for i in _view().audit_items if i["result"] == "WARNING")
    assert item["diagnosis"]


def test_not_checked_semantics():
    item = next(i for i in _view().audit_items if i["execution"] == "NOT_CHECKED")
    assert item["current_state"] == "Not verified"
    assert item["required_data"]
    assert item["how_to_complete"]
    assert "Not yet verified" in item["how_to_verify"]


def test_not_applicable_is_not_data_gap():
    item = next(i for i in _view().audit_items
                if i["execution"] == "NOT_APPLICABLE")
    assert item["action_priority"] == "N/A"
    assert "Data gap" != item["action_priority"]


def test_not_applicable_does_not_request_data():
    item = next(i for i in _view().audit_items
                if i["execution"] == "NOT_APPLICABLE")
    assert "required_data" not in item
    assert "how_to_complete" not in item


def test_not_applicable_contains_reason():
    item = next(i for i in _view().audit_items
                if i["execution"] == "NOT_APPLICABLE")
    assert item["why_not_applicable"]


def test_every_task_reconciles_with_audit_result():
    from audit_rules.report_consistency import validate_report_consistency
    view = _view()
    violations = validate_report_consistency(view, _view().audit_items, [])
    # Only task-related checks apply when tasks are passed; empty task list
    # must not introduce task violations. Build with the real task rows:
    from tests.phase12.test_universal_report_view import _tasks
    violations = validate_report_consistency(view, _view().audit_items, _tasks())
    assert not any("task" in v for v in violations)


def test_pass_rule_does_not_generate_confirmed_remediation():
    from tests.phase12.test_universal_report_view import _items, _tasks
    items = _items()
    tasks = [t for t in _tasks() if int(t["audit_id"]) in
             (i["audit_id"] for i in items if i["result"] == "PASS")]
    for task in tasks:
        assert task.get("task_type") != "REMEDIATION"


def test_optimization_task_maps_to_opportunity_or_explicit_maintenance():
    from audit_rules.report_consistency import _ALLOWED_TASK_RESULT
    assert "OPPORTUNITY" in _ALLOWED_TASK_RESULT["OPTIMIZATION"]


def test_checklist_matches_remediation_plan():
    view = _view()
    plan_keys = {(r["audit_id"], r["problem"], r["action"])
                 for r in view.remediation_plan}
    checklist_keys = {(r["audit_id"], r["problem"], r["action"])
                      for r in view.checklist_rows}
    assert plan_keys == checklist_keys


def test_action_priority_uses_p0_p3():
    view = _view()
    for row in view.remediation_plan:
        assert row["action_priority"] in (
            "P0", "P1", "P2", "P3", "N/A", "Data gap", "Manual Review")


def test_validator_fails_on_contradictory_distribution():
    from audit_rules.report_consistency import validate_report_consistency
    view = _view()
    view.result_distribution = {"PASS": 99, "FAIL": 1}
    violations = validate_report_consistency(view, view.audit_items, [])
    assert any("result_distribution" in v for v in violations)


def test_validator_fails_when_fail_has_no_action():
    from audit_rules.report_consistency import validate_report_consistency
    view = _view()
    for item in view.audit_items:
        if item["result"] == "FAIL":
            item["what_to_do"] = ""
    violations = validate_report_consistency(view, view.audit_items, [])
    assert any("has no action" in v for v in violations)


def test_client_mode_fails_closed_on_inconsistency(tmp_path):
    import pytest as pt
    from audit_rules.report_view import build_report_view
    from audit_rules.docx_report import build_universal_docx
    from tests.phase12.test_universal_report_view import (
        _items, _metrics, _tasks,
    )
    items = _items()
    items[5]["result"] = "FAIL"
    items[5]["fix"] = "No remediation required."
    view = build_report_view(
        items, _tasks(), _metrics(), manual_rows=[],
        technology_profile=None, technology_risks=[],
        domain="https://site-a.example/", audit_date="2026-08-11",
        pages_crawled=228)
    # Post-build corruption the view model cannot auto-heal.
    for item in view.audit_items:
        if item["result"] == "FAIL":
            item["what_to_do"] = "No remediation required."
    with pt.raises(ValueError, match="consistency check failed"):
        build_universal_docx(
            str(tmp_path / "x.docx"), view_model=view,
            items=items, task_rows=_tasks(), metrics=_metrics(),
            result_counts={}, execution_counts={}, manual_rows=[],
            schema_distribution={}, domain="https://site-a.example/",
            audit_date="2026-08-11", site_name="Site A", pages_crawled=228)
