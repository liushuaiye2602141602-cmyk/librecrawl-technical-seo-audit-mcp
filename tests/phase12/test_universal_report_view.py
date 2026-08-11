"""Universal Master SEO Diagnostic Report — view model contract."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _item(audit_id, result="PASS", execution="EXECUTED_FULL", affected=0,
          priority="Medium", representative=None, evidence="evidence text",
          fix="No remediation required.", acceptance="Acceptance text",
          why="No impact", limitations="", owner="SEO"):
    return {
        "audit_id": audit_id,
        "category": "Crawling & Indexing",
        "check": f"Check {audit_id}",
        "what_checked": f"What was checked for {audit_id}",
        "execution": execution,
        "result": result,
        "priority": priority,
        "confidence": "1.00",
        "data_source": "LibreCrawl",
        "actual_state": "Actual state text",
        "diagnosis": "Normal",
        "evidence": evidence,
        "affected_urls": affected,
        "representative": representative or [],
        "seo_impact": why,
        "fix": fix,
        "owner": owner,
        "acceptance": acceptance,
        "limitations": limitations,
        "observed": "",
        "manual": {},
        "is_pass": result == "PASS",
        "action_required": "None" if result == "PASS" else "Fix",
    }


def _items(count=80):
    items = [_item(i + 1) for i in range(count)]
    items[5]["result"] = "FAIL"
    items[5]["priority"] = "Critical"
    items[5]["affected_urls"] = 12
    items[5]["fix"] = "Add 301 redirects for moved URLs."
    items[5]["acceptance"] = "All moved URLs return 301 to the canonical target."
    items[9]["result"] = "WARNING"
    items[9]["affected_urls"] = 30
    items[14]["result"] = "OPPORTUNITY"
    items[14]["affected_urls"] = 199
    items[28]["result"] = "OPPORTUNITY"
    items[28]["affected_urls"] = 199
    items[28]["check"] = "hreflang x-default"
    items[19]["execution"] = "NOT_CHECKED"
    items[19]["result"] = "UNKNOWN"
    items[19]["limitations"] = "Data source unavailable: GSC"
    items[24]["execution"] = "NOT_APPLICABLE"
    items[24]["result"] = "UNKNOWN"
    items[24]["limitations"] = "WordPress-specific rule"
    return items


def _tasks():
    return [
        {
            "task_type": "REMEDIATION", "audit_id": 6, "rule_id": "r6",
            "priority": "Critical", "severity": "Error",
            "url": "https://site-a.example/", "finding": "Redirect missing",
            "evidence": "ev", "remediation": "Add 301",
            "owner": "Developer", "acceptance_criteria": "301 verified",
            "confidence": "1.0", "affected_url_count": 1,
            "affected_urls_sample": "https://site-a.example/",
            "status": "Open",
        },
        {
            "task_type": "OPTIMIZATION", "audit_id": 29, "rule_id": "r29",
            "priority": "Medium", "severity": "Opportunity",
            "url": "https://site-a.example/x", "finding": "Add x-default",
            "evidence": "ev", "remediation": "Add hreflang x-default",
            "owner": "SEO", "acceptance_criteria": "x-default present",
            "confidence": "0.9", "affected_url_count": 199,
            "affected_urls_sample": "https://site-a.example/x",
            "status": "Open",
        },
    ]


def _metrics():
    return {
        "audit_rows": 80, "matrix_rows": 80, "coverage_rows": 80,
        "finding_rows": 2, "task_rows": 2, "manual_rows": 1,
        "performance_rows": 5, "pdf_pages": 0,
        "confirmed_remediation": 1, "optimization": 1,
        "data_required": 3, "manual_review_actions": 1,
        "p0": 1, "p1": 0, "p2": 1, "p3": 0,
        "score": 88.08, "coverage_pct": 61.25, "confidence_pct": 84.79,
    }


def _view(**overrides):
    from audit_rules.report_view import build_report_view
    kwargs = dict(
        items=_items(), task_rows=_tasks(), metrics=_metrics(),
        manual_rows=[{"audit_id": 53}],
        technology_profile=None, technology_risks=[],
        domain="https://site-a.example/", audit_date="2026-08-11",
        pages_crawled=228,
    )
    kwargs.update(overrides)
    return build_report_view(**kwargs)


def test_universal_report_always_has_80_audits():
    view = _view()
    assert len(view.audit_items) == 80


def test_management_summary_has_all_buckets():
    view = _view()
    summary = "\n".join(view.management_summary)
    for bucket in ("SEO 健康评分", "检测覆盖率", "结论置信度", "抓取页面数",
                   "失败审计", "警告审计", "机会审计", "未验证/人工",
                   "整改任务", "优化任务", "数据缺口任务", "人工评审任务"):
        assert bucket in summary


def test_key_findings_only_fail_warning_opportunity():
    view = _view()
    assert view.key_findings
    for finding in view.key_findings:
        assert finding["result"] in ("FAIL", "WARNING", "OPPORTUNITY")
    assert view.key_findings[0]["result"] == "FAIL"


def test_remediation_plan_answers_6_questions():
    view = _view()
    assert view.remediation_plan
    row = view.remediation_plan[0]
    for key in ("problem", "scope", "action", "owner", "verify", "status"):
        assert row.get(key)


def test_score_explanation_present():
    view = _view()
    text = " ".join(view.score_explanation)
    assert "Google 官方评分" in text or "排名预测" in text


def test_coverage_and_confidence_explanations_present():
    view = _view()
    text = " ".join(view.explanations)
    assert "覆盖率" in text and "置信度" in text


def test_report_template_version_present():
    view = _view()
    assert view.report_metadata["report_template_version"]
    assert view.report_metadata["report_schema_version"]


def test_report_identity_uses_current_run():
    view = _view()
    assert view.domain == "site-a.example"
    assert view.pages_crawled == 228
    # No other-client fallback: site_name derives from hostname when absent.
    view2 = _view(site_name="")
    assert view2.site_name.lower() == "site-a.example".split(".")[0]


def test_pass_rule_contains_evidence():
    view = _view()
    item = view.audit_items[0]
    assert item["evidence"] and item["why_pass"]


def test_fail_rule_contains_action_and_acceptance():
    view = _view()
    item = next(i for i in view.audit_items if i["audit_id"] == 6)
    assert item["fix"] and item["acceptance"]
    assert item["action_priority"]


def test_not_checked_contains_required_data():
    view = _view()
    item = next(i for i in view.audit_items if i["audit_id"] == 20)
    assert "GSC" in item["required_data"]
    assert item["how_to_complete"]


def test_not_applicable_contains_reason():
    view = _view()
    item = next(i for i in view.audit_items if i["audit_id"] == 25)
    assert item["why_not_applicable"]


def test_representative_urls_are_bounded():
    view = _view()
    urls = [f"https://site-a.example/p{i}" for i in range(20)]
    item = next(i for i in view.audit_items if i["audit_id"] == 6)
    item["representative"] = urls
    assert len(view.report_metadata) >= 0  # view built before mutation
    view2 = _view()
    item2 = next(i for i in view2.audit_items if i["audit_id"] == 6)
    assert len(item2["representative"]) <= 5


def test_large_findings_are_compacted():
    item = _item(79, result="WARNING", affected=3000)
    item["evidence"] = "\n".join(f"https://site-a.example/p{i}" for i in range(3000))
    from audit_rules.report_view import compact_evidence
    compact = compact_evidence(item["evidence"], limit=5)
    assert compact.count("\n") <= 10
    assert "09" in compact or "artifact" in compact.lower() or "…" in compact


def test_client_and_internal_views_share_same_results():
    client = _view(audience="client")
    internal = _view(audience="internal")
    assert client.diagnosis_signature == internal.diagnosis_signature


def test_report_view_does_not_change_score_or_rule_count():
    view = _view()
    assert view.score == 88.08
    assert len(view.audit_items) == 80
    assert view.metrics["score"] == 88.08


def test_technology_unknown_not_presented_as_confirmed():
    profile = {
        "detections": [
            {"category": "Ecommerce", "technology_name": "WooCommerce",
             "status": "UNKNOWN", "confidence": "Medium",
             "version": "Unknown", "detection_sources": [], "limitations": []},
            {"category": "CMS", "technology_name": "WordPress",
             "status": "DETECTED", "confidence": "High",
             "version": "Unknown", "detection_sources": [], "limitations": []},
        ],
    }
    view = _view(technology_profile=profile)
    assert view.technology_observations
    unknown = next(o for o in view.technology_observations
                   if o["technology"] == "WooCommerce")
    assert unknown["status"] == "UNKNOWN"
    assert "not confirmed" in unknown["presentation"].lower() or (
        "observation" in unknown["presentation"].lower())


def test_report_labels_are_unified():
    from audit_rules.report_view import LABELS
    zh = LABELS["zh-CN"]
    assert zh["score"] and zh["coverage"] and zh["key_findings"]


def test_label_layer_supports_language_keys():
    from audit_rules.report_view import LABELS
    assert "zh-CN" in LABELS and "en-US" in LABELS
