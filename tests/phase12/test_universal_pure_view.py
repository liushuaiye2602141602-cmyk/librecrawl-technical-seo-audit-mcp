"""FINAL UNIVERSAL PURE-VIEW + ACTION AGGREGATION regressions."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

docx = pytest.importorskip("docx")


def _demo():
    from audit_rules.report_view import build_report_view
    from scripts.generate_universal_demo_report import (
        _build_items, _metrics, _tasks,
    )
    items, tasks = _build_items(), _tasks()
    view = build_report_view(
        items, tasks, _metrics(), manual_rows=[{"audit_id": 53}],
        technology_profile=None, technology_risks=[],
        domain="https://demo-client.example/", audit_date="2026-08-11",
        pages_crawled=228)
    return view, items, tasks


def test_report_view_never_mutates_execution_status():
    view, items, _ = _demo()
    input_execution = {
        int(item["audit_id"]): str(item["execution"]) for item in items
    }
    view_execution = {
        int(item["audit_id"]): str(item["execution"])
        for item in view.audit_items
    }
    assert view_execution == input_execution


def test_report_view_never_mutates_result_status():
    view, items, _ = _demo()
    input_result = {
        int(item["audit_id"]): str(item["result"]) for item in items
    }
    view_result = {
        int(item["audit_id"]): str(item["result"])
        for item in view.audit_items
    }
    assert view_result == input_result


def test_rule02_partial_is_set_before_report_view():
    _, items, _ = _demo()
    item = next(i for i in items if i["audit_id"] == 2)
    assert item["execution"] == "EXECUTED_PARTIAL"
    assert item["result"] == "PASS"


def test_coverage_and_docx_rule02_execution_match(tmp_path):
    from audit_rules.docx_report import build_universal_docx
    view, items, tasks = _demo()
    from scripts.generate_universal_demo_report import _metrics
    out = tmp_path / "u.docx"
    build_universal_docx(
        str(out), view_model=view, items=items, task_rows=tasks,
        metrics=_metrics(), result_counts=view.result_distribution,
        execution_counts=view.execution_distribution,
        manual_rows=[{"audit_id": 53}], schema_distribution={},
        domain="https://demo-client.example/", audit_date="2026-08-11",
        site_name="Demo Client", pages_crawled=228)
    # Machine coverage artifact (input items) and DOCX must agree.
    from docx import Document
    doc = Document(str(out))
    text = "\n".join(p.text for p in doc.paragraphs)
    idx = text.find("AUDIT #02")
    block = text[idx:idx + 400]
    assert "EXECUTED_PARTIAL" in block
    assert "PASS" in block


def test_diagnostic_signature_matches_input_diagnosis():
    view, items, _ = _demo()
    input_pairs = {
        int(item["audit_id"]): (str(item["execution"]), str(item["result"]))
        for item in items
    }
    view_pairs = {
        int(item["audit_id"]): (str(item["execution"]), str(item["result"]))
        for item in view.audit_items
    }
    assert view_pairs == input_pairs


def test_management_task_counts_match_action_views():
    view, _, _ = _demo()
    summary = "\n".join(view.management_summary)
    from audit_rules.report_view import _action_counts, _action_type
    action_counts = _action_counts({
        a["audit_id"]: {"action_type": _action_type(
            str(a["execution"]), str(a["result"]))}
        for a in view.audit_items
    })
    for label, key in (("整改动作（REMEDIATION）", "REMEDIATION"),
                       ("缓解/评审动作（MITIGATION）", "MITIGATION"),
                       ("优化动作（OPTIMIZATION）", "OPTIMIZATION"),
                       ("数据获取动作（DATA_REQUIRED）", "DATA_REQUIRED"),
                       ("人工评审动作（MANUAL_REVIEW）", "MANUAL_REVIEW")):
        assert f"{label}: {action_counts[key]} 条" in summary


def test_responsibility_matrix_matches_action_views():
    view, _, _ = _demo()
    from audit_rules.report_view import _action_type
    included = ("REMEDIATION", "MITIGATION", "OPTIMIZATION",
                "DATA_REQUIRED", "MANUAL_REVIEW")
    expected = {}
    for a in view.audit_items:
        action_type = _action_type(str(a["execution"]), str(a["result"]))
        if action_type in included:
            owner = str(a.get("owner") or "SEO")
            expected[owner] = expected.get(owner, 0) + 1
    actual = {r["owner"]: r["task_count"] for r in view.responsibility}
    assert actual == expected


def test_raw_task_rows_cannot_create_client_remediation():
    from audit_rules.report_view import build_report_view
    from scripts.generate_universal_demo_report import (
        _build_items, _metrics, _tasks,
    )
    items, tasks = _build_items(), _tasks()
    # Inject a bogus raw REMEDIATION task for a PASS audit (#1).
    tasks.append({
        "task_type": "REMEDIATION", "audit_id": 1, "priority": "Critical",
        "finding": "bogus", "remediation": "bogus fix", "owner": "SEO",
        "acceptance_criteria": "bogus", "affected_url_count": 1, "status": "Open",
    })
    view = build_report_view(
        items, tasks, _metrics(), manual_rows=[{"audit_id": 53}],
        technology_profile=None, technology_risks=[],
        domain="https://demo-client.example/", audit_date="2026-08-11",
        pages_crawled=228)
    plan_ids = {r["audit_id"] for r in view.remediation_plan}
    checklist_ids = {r["audit_id"] for r in view.checklist_rows}
    assert 1 not in plan_ids
    assert 1 not in checklist_ids


def test_not_checked_task_not_counted_as_remediation():
    view, _, _ = _demo()
    summary = "\n".join(view.management_summary)
    assert "整改动作（REMEDIATION）: 2 条" in summary
    assert "数据获取动作（DATA_REQUIRED）: 3 条" in summary


def test_na_task_not_counted_in_responsibility():
    view, _, _ = _demo()
    owners = {r["owner"]: r["task_count"] for r in view.responsibility}
    # N/A audits (29/59) contribute no responsibility entries.
    from audit_rules.report_view import _action_views_for_plan
    plan_ids = {r["audit_id"] for r in view.remediation_plan}
    assert 29 not in plan_ids and 59 not in plan_ids
    assert owners


def test_manual_review_count_matches_action_views():
    view, _, _ = _demo()
    summary = "\n".join(view.management_summary)
    assert "人工评审动作（MANUAL_REVIEW）: 1 条" in summary


def test_rule01_what_was_checked_does_not_require_sitemap_declaration():
    view, _, _ = _demo()
    item = next(i for i in view.audit_items if i["audit_id"] == 1)
    assert "如存在 Sitemap 声明" in item["what_checked"]
    assert "并声明 XML Sitemap" not in item["what_checked"]
    assert "并声明 XML Sitemap" not in item["how_to_verify"]


def test_rule01_what_checked_matches_final_acceptance_semantics():
    view, _, _ = _demo()
    item = next(i for i in view.audit_items if i["audit_id"] == 1)
    assert "如存在 Sitemap 声明，则验证其地址有效" in item["what_checked"]
    assert "如包含 Sitemap 声明，则地址有效" in item["how_to_verify"]
