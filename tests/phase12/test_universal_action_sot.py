"""FINAL UNIVERSAL ACTION SOURCE-OF-TRUTH regressions.

All client sections consume one normalized action model derived from
execution-first semantics; task-based sections never re-interpret raw task
text.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

docx = pytest.importorskip("docx")


def _demo_view():
    from audit_rules.report_view import build_report_view
    from scripts.generate_universal_demo_report import (
        _build_items, _metrics, _tasks,
    )
    items, tasks = _build_items(), _tasks()
    view = build_report_view(
        items, tasks, _metrics(), manual_rows=[
            {"audit_id": 53, "rule": "搜索意图匹配", "scope": "SITE",
             "status": "PENDING"}],
        technology_profile=None, technology_risks=[],
        domain="https://demo-client.example/", audit_date="2026-08-11",
        pages_crawled=228)
    return view, items, tasks


def test_summary_not_checked_action_is_data_required():
    view, _, _ = _demo_view()
    for audit_id in (20, 34, 46):
        item = next(i for i in view.audit_items if i["audit_id"] == audit_id)
        assert item["summary_label"] == "Data Required"
        assert item["summary_action"] == "Data Required"


def test_summary_na_action_is_na():
    view, _, _ = _demo_view()
    for audit_id in (29, 59):
        item = next(i for i in view.audit_items if i["audit_id"] == audit_id)
        assert item["summary_label"] == "N/A"
        assert item["summary_action"] == "None / N/A"


def test_summary_manual_action_is_manual_review():
    view, _, _ = _demo_view()
    item = next(i for i in view.audit_items if i["audit_id"] == 53)
    assert item["summary_label"] == "Manual Review"


def test_summary_action_uses_execution_first():
    view, _, _ = _demo_view()
    # UNKNOWN + N/A must not be "Data gap".
    for audit_id in (29, 59):
        item = next(i for i in view.audit_items if i["audit_id"] == audit_id)
        assert item["summary_label"] == "N/A"
    # UNKNOWN + NOT_CHECKED must be Data Required, not Fix.
    for audit_id in (20, 34, 46):
        item = next(i for i in view.audit_items if i["audit_id"] == audit_id)
        assert item["summary_label"] == "Data Required"


def test_not_checked_plan_uses_data_acquisition():
    view, _, _ = _demo_view()
    for audit_id in (20, 34, 46):
        row = next(r for r in view.remediation_plan
                   if r["audit_id"] == audit_id)
        assert "Provide" in row["action"]
        assert "re-run" in row["action"]
        assert "optimize" not in row["action"].lower()
        assert "fix" not in row["action"].lower()


def test_not_checked_checklist_uses_data_acquisition():
    view, _, _ = _demo_view()
    for audit_id in (20, 34, 46):
        row = next(r for r in view.checklist_rows
                   if r["audit_id"] == audit_id)
        assert "Provide" in row["action"]
        assert "Data obtained and rule successfully re-evaluated" in (
            row["verification"])


def test_manual_plan_and_checklist_use_review():
    view, _, _ = _demo_view()
    plan = next(r for r in view.remediation_plan if r["audit_id"] == 53)
    checklist = next(r for r in view.checklist_rows if r["audit_id"] == 53)
    assert "Complete the manual review" in plan["action"]
    assert "Complete the manual review" in checklist["action"]


def test_roadmap_separates_confirmed_and_unverified():
    view, _, _ = _demo_view()
    data_collection = view.roadmap.get("data_collection", [])
    manual_review = view.roadmap.get("manual_review", [])
    assert any(str(e).startswith("#20") for e in data_collection)
    assert any(str(e).startswith("#34") for e in data_collection)
    assert any(str(e).startswith("#46") for e in data_collection)
    assert any(str(e).startswith("#53") for e in manual_review)
    confirmed = (view.roadmap.get("immediate", [])
                 + view.roadmap.get("short_term", [])
                 + view.roadmap.get("medium_term", []))
    confirmed_text = " ".join(str(e) for e in confirmed)
    assert "#20" not in confirmed_text
    assert "#34" not in confirmed_text
    assert "#46" not in confirmed_text
    assert "#53" not in confirmed_text


def test_pass_primary_action_is_no_remediation():
    view, _, _ = _demo_view()
    item = next(i for i in view.audit_items if i["audit_id"] == 1)
    assert item["result"] == "PASS"
    assert item["what_to_do"] == "No remediation required."


def test_pass_remediation_is_optional_maintenance():
    view, _, _ = _demo_view()
    item = next(i for i in view.audit_items if i["audit_id"] == 1)
    assert item["optional_maintenance"]
    assert "Sitemap" in item["optional_maintenance"]


def test_pass_rule_never_appears_in_remediation_checklist():
    view, _, _ = _demo_view()
    plan_ids = {r["audit_id"] for r in view.remediation_plan}
    checklist_ids = {r["audit_id"] for r in view.checklist_rows}
    for audit_id in (1, 2):
        assert audit_id not in plan_ids
        assert audit_id not in checklist_ids


def test_na_not_in_plan_checklist_roadmap():
    view, _, _ = _demo_view()
    plan_ids = {r["audit_id"] for r in view.remediation_plan}
    checklist_ids = {r["audit_id"] for r in view.checklist_rows}
    for audit_id in (29, 59):
        assert audit_id not in plan_ids
        assert audit_id not in checklist_ids
    all_roadmap = " ".join(
        str(e) for section in view.roadmap.values() for e in section)
    assert "#29" not in all_roadmap
    assert "#59" not in all_roadmap


def test_na_why_it_matters_has_no_remediation_ask():
    view, _, _ = _demo_view()
    item = next(i for i in view.audit_items if i["audit_id"] == 29)
    assert "no remediation is required" in item["why_it_matters"]
    assert "Re-evaluate only if the architecture changes" in (
        item["why_it_matters"])


def test_manual_review_has_no_empty_required_data_fields():
    view, _, _ = _demo_view()
    item = next(i for i in view.audit_items if i["audit_id"] == 53)
    assert item["required_data"]
    assert item["how_to_complete"]


def test_rule02_without_external_provider_is_partial():
    view, _, _ = _demo_view()
    item = next(i for i in view.audit_items if i["audit_id"] == 2)
    assert item["execution"] == "EXECUTED_PARTIAL"
    assert item["result"] == "PASS"


def test_rule02_what_was_checked_does_not_claim_gsc_bing():
    view, _, _ = _demo_view()
    item = next(i for i in view.audit_items if i["audit_id"] == 2)
    assert "Automated/Crawl Layer" in item["what_checked"]
    assert "External Layer" in item["what_checked"]
    assert "not checked" in item["what_checked"]
    assert "已提交" not in item["what_checked"]


def test_rule02_external_validation_not_checked_matches_execution():
    from audit_rules.report_consistency import validate_report_consistency
    view, items, tasks = _demo_view()
    violations = validate_report_consistency(view, items, tasks)
    assert not any("#02" in v for v in violations)
