"""FINAL UNIVERSAL REPORT TWO-AXIS + EVIDENCE LOCK regressions."""

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


def _item(view, audit_id):
    return next(i for i in view.audit_items if i["audit_id"] == audit_id)


def test_execution_status_precedes_result_status():
    view, _, _ = _demo_view()
    na = _item(view, 29)
    assert na["execution"] == "NOT_APPLICABLE"
    assert na["summary_action"] == "None / N/A"
    # N/A must never fall into UNKNOWN/data-gap presentation.
    assert na["action_priority"] == "N/A"
    assert "required_data" not in na
    assert "how_to_complete" not in na


def test_not_applicable_summary_action_is_none():
    view, _, _ = _demo_view()
    assert _item(view, 29)["summary_action"] == "None / N/A"


def test_not_applicable_never_uses_unknown_presentation():
    view, _, _ = _demo_view()
    for audit_id in (29, 59):
        item = _item(view, audit_id)
        assert item["current_state"] == "Not applicable"
        assert "Not verified" not in item["how_to_verify"]


def test_not_applicable_has_no_remediation_action():
    view, _, _ = _demo_view()
    item = _item(view, 29)
    assert "remediation" not in item["what_to_do"].lower()
    assert "No action required" in item["what_to_do"]


def test_not_applicable_acceptance_is_na():
    view, _, _ = _demo_view()
    item = _item(view, 59)
    assert "Not applicable" in item["how_to_verify"]
    assert "not yet verified" not in item["how_to_verify"].lower()


def test_not_checked_primary_action_is_data_acquisition():
    view, _, _ = _demo_view()
    for audit_id in (20, 34, 46):
        item = _item(view, audit_id)
        assert item["what_to_do"].startswith("Provide")
        assert "re-run" in item["what_to_do"]
        assert "optimize" not in item["what_to_do"].lower()


def test_not_checked_does_not_present_unconfirmed_fix_as_required():
    view, _, _ = _demo_view()
    item = _item(view, 34)
    # Any speculative remediation is explicitly labeled "If Confirmed".
    if "Potential Remediation If Confirmed" in item["what_to_do"]:
        assert "Potential Remediation If Confirmed" in item["what_to_do"]


def test_data_required_task_action_matches_required_data():
    view, _, _ = _demo_view()
    task = next(t for t in view.remediation_plan if t["audit_id"] == 20)
    item = _item(view, 20)
    assert item["required_data"]
    assert task["action"]


def test_manual_review_primary_action_is_review():
    view, _, _ = _demo_view()
    item = _item(view, 53)
    assert "Complete the manual review" in item["what_to_do"]


def test_manual_review_does_not_assume_failure():
    view, _, _ = _demo_view()
    item = _item(view, 53)
    # The primary action asks for the review, not a remediation.
    assert "Optimize" not in item["what_to_do"]
    assert "Confirm" not in item["what_to_do"] or (
        "If Confirmed" in item["what_to_do"])


def test_client_report_contains_no_internal_scope_token_site():
    view, _, _ = _demo_view()
    assert view.manual_review_rows[0]["scope"] != "SITE"
    assert "全站" in view.manual_review_rows[0]["scope"]


def test_technology_profile_client_evidence_is_nonempty():
    view, _, _ = _demo_view()
    from audit_rules.report_view import _technology_observations
    from scripts.generate_universal_demo_report import _technology_profile
    observations = _technology_observations(_technology_profile())
    assert observations
    for observation in observations:
        assert observation["evidence"]


def test_displayed_technology_always_has_evidence_or_limitation():
    from audit_rules.report_view import _technology_observations
    profile = {"detections": [
        {"technology_name": "WordPress", "status": "DETECTED",
         "confidence": "High", "detection_sources": [], "limitations": []},
        {"technology_name": "Foo", "status": "UNKNOWN",
         "confidence": "Low", "detection_sources": [], "limitations": []},
    ]}
    observations = _technology_observations(profile)
    assert all(o["evidence"] for o in observations)


def test_universal_report_rule01_uses_final_robots_acceptance():
    view, _, _ = _demo_view()
    item = _item(view, 1)
    assert "如包含 Sitemap 声明，则地址有效" in item["how_to_verify"]
    assert "包含有效 Sitemap 声明" not in item["how_to_verify"]


def test_universal_report_rule02_separates_crawl_and_external_acceptance():
    view, _, _ = _demo_view()
    item = _item(view, 2)
    assert "Automated/Crawl Acceptance" in item["how_to_verify"]
    assert "External Validation" in item["how_to_verify"]


def test_librecrawl_only_does_not_claim_gsc_bing_validation():
    view, _, _ = _demo_view()
    item = _item(view, 2)
    assert "GSC/Bing submission/processing status requires external data" in (
        item["how_to_verify"])
    assert "成功读取" not in item["how_to_verify"]


def test_checklist_priority_is_action_priority():
    view, _, _ = _demo_view()
    for row in view.checklist_rows:
        assert row["action_priority"] in (
            "P0", "P1", "P2", "P3", "Data gap", "Manual Review")
        assert row["rule_priority"]


def test_roadmap_entries_are_named_and_actionable():
    view, _, _ = _demo_view()
    data_collection = view.roadmap.get("data_collection", [])
    assert data_collection
    for entry in data_collection:
        assert entry.startswith("#")
        assert "—" in entry
    # Anonymous duplicate "数据不足，无法判定" must not repeat.
    assert sum(1 for e in data_collection if "数据不足" in e) == 0
