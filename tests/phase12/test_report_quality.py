"""Final client-report quality contracts (13-blocker fix round)."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _registry():
    from audit_rules.registry import load_registry
    return load_registry()


def _rule(audit_id: int):
    return next(r for r in _registry() if r.audit_id == audit_id)


def _page(url="https://example.com/", status=200, title="Unique title",
          word_count=500, json_ld=None, robots=""):
    from audit_rules.context import PageContext
    return PageContext(
        url=url, status_code=status, title=title, word_count=word_count,
        robots=robots, json_ld_types=json_ld or [],
        _raw_export={"links_detailed": [], "linked_from": []},
    )


def _site(profile="generic", sitemap_found=True):
    from audit_rules.context import SiteContext
    return SiteContext(
        base_url="https://example.com/", robots_txt_found=True,
        sitemap_found=sitemap_found,
        sitemap_url="https://example.com/sitemap.xml",
        site_profile=profile,
        _site_data={"sitemap": {"found": sitemap_found,
                                 "url": "https://example.com/sitemap.xml"}},
    )


def _coverage(audit_id, pages, findings, providers=None, executed=None,
              overrides=None):
    from audit_rules.coverage import CoverageManager
    rows = CoverageManager(_registry()).compute(
        _site(), pages, findings,
        providers_available=providers or {"LibreCrawl"},
        executed_rule_ids=executed or {audit_id},
        evaluated_overrides=overrides or {},
    )
    return next(r for r in rows if r.audit_id == audit_id)


def test_partial_pass_requires_positive_evaluated_evidence():
    from audit_rules.checks.foundation_gaps import check_xml_sitemap_valid
    pages = [_page()]
    findings = check_xml_sitemap_valid(_rule(2), _site(), pages, {})
    row = _coverage(2, pages, findings, executed={2}, overrides={2: 1})
    assert row.execution_status.value == "EXECUTED_PARTIAL"
    assert row.evaluated_count == 1


def test_sitemap_partial_pass_records_real_counts():
    from audit_rules.checks.foundation_gaps import check_xml_sitemap_valid
    pages = [_page()]
    findings = check_xml_sitemap_valid(_rule(2), _site(), pages, {})
    row = _coverage(2, pages, findings, executed={2}, overrides={2: 1})
    assert "GSC" in (row.not_checked_reason or "")
    assert row.result_status.value == "PASS"


def test_thin_content_partial_counts():
    from audit_rules.checks.content_metadata import check_thin_content
    pages = [_page("https://example.com/a.html", word_count=400),
             _page("https://example.com/b.html", word_count=380)]
    findings = check_thin_content(_rule(16), _site(), pages, {})
    row = _coverage(16, pages, findings, executed={16}, overrides={16: 2})
    assert row.execution_status.value == "EXECUTED_PARTIAL"
    assert row.evaluated_count == 2


def test_shared_psi_execution_summary():
    from audit_rules.checks.performance import build_psi_execution_summary
    from audit_rules.providers.performance_snapshot import PerformanceSnapshot
    cache = {}
    for i in range(4):
        snap = PerformanceSnapshot(
            url=f"https://example.com/p{i}.html", strategy="mobile",
            psi_status="success", lab_performance_score=70)
        cache[(snap.url, "mobile")] = snap
    err = PerformanceSnapshot(
        url="https://example.com/", strategy="mobile", psi_status="error",
        error="PSI request timed out after 30s")
    cache[(err.url, "mobile")] = err
    summary = build_psi_execution_summary(cache, sampled_count=5,
                                          eligible_pages=315)
    assert summary["sampled_urls"] == 5
    assert summary["success"] == 4
    assert summary["timeout"] == 1
    assert summary["field_data_available"] == 0
    assert summary["eligible_pages"] == 315


def test_no_fake_ttfb_task():
    from audit_rules.checks.performance import check_ttfb
    from audit_rules.adapters import DataUnavailableError
    from audit_rules.providers.performance_snapshot import PerformanceSnapshot
    snap = PerformanceSnapshot(
        url="https://example.com/", strategy="mobile", psi_status="success",
        lab_lcp_ms=5626.0, lab_performance_score=61,
        field_data_scope="NONE")
    data = {"_psi_cache": {("https://example.com", "mobile"): snap},
            "psi_strategy": "mobile"}
    try:
        check_ttfb(_rule(20), _site(), [_page()], data)
    except DataUnavailableError:
        return  # expected: no fake TTFB from LCP
    raise AssertionError("check_ttfb must not emit findings from lab LCP")


def test_schema_type_distribution():
    from audit_rules.reporting import schema_type_distribution
    pages = [
        _page("https://example.com/a", json_ld=["Organization", "WebPage"]),
        _page("https://example.com/b", json_ld=["Organization"]),
        _page("https://example.com/c", json_ld=[]),
    ]
    distribution = schema_type_distribution(pages)
    assert distribution["Organization"] == 2
    assert distribution["WebPage"] == 1


def test_no_raw_url_dump():
    from audit_rules.reporting import truncate_evidence_examples
    rows = [{"url": f"https://example.com/p{i}.html"} for i in range(500)]
    assert len(truncate_evidence_examples(rows, limit=8)) == 8


def test_lastmod_semantic_scope():
    from audit_rules.checks.phase4a_rules import check_sitemap_lastmod
    pages = [_page()]
    findings = check_sitemap_lastmod(_rule(43), _site(), pages, {})
    row = _coverage(43, pages, findings, executed={43})
    assert row.execution_status.value == "EXECUTED_PARTIAL"
    assert "lastmod" in (row.not_checked_reason or "").lower()


def test_report_html_escape():
    from audit_rules.reporting import escape_markdown_literal
    escaped = escape_markdown_literal("可抓取链接 <a href> 使用标准")
    assert "<a href>" not in escaped
    assert "&lt;a href&gt;" in escaped


def test_pass_info_no_task():
    from audit_rules.reporting import task_type_for
    assert task_type_for("Info", "EXECUTED_PARTIAL", "PASS") == "MONITORING"
    assert task_type_for("Info", "EXECUTED_PARTIAL", "PASS") != "REMEDIATION"
    assert task_type_for("Error", "EXECUTED_FULL", "FAIL") == "REMEDIATION"
    assert task_type_for("Opportunity", "EXECUTED_FULL", "OPPORTUNITY") == "OPTIMIZATION"
    assert task_type_for("Info", "NOT_CHECKED", "UNKNOWN") == "DATA_REQUIRED"


def test_accessibility_manual_task_type():
    from audit_rules.reporting import task_type_for
    assert task_type_for("Info", "EXECUTED_PARTIAL", "UNKNOWN",
                         is_manual_rule=True) == "MANUAL_REVIEW"


def test_orphan_task_dedup():
    from audit_rules.reporting import aggregate_orphan_remediation
    tasks = [
        {"audit_id": "11", "rule_id": "internal_link_distribution",
         "url": "https://example.com/a.html"},
        {"audit_id": "11", "rule_id": "internal_link_distribution",
         "url": "https://example.com/b.html"},
        {"audit_id": "45", "rule_id": "orphan_pages",
         "url": "https://example.com/a.html"},
        {"audit_id": "13", "rule_id": "title_uniqueness",
         "url": "https://example.com/c.html"},
    ]
    merged = aggregate_orphan_remediation(tasks)
    orphan_rows = [t for t in merged if t.get("rule_id") == "internal_discoverability"]
    assert len(orphan_rows) == 1
    assert orphan_rows[0]["affected_url_count"] == 2
    assert "Related Audits" in orphan_rows[0]["finding"]
    assert len([t for t in merged if t.get("audit_id") == "13"]) == 1


def test_hashtag_archive_policy():
    from audit_rules.checks.phase4a_rules import (
        _classify_archive_page, check_archive_search_indexability,
    )
    assert _classify_archive_page("https://example.com/hashtag/pet-food") == "tag"
    page = _page("https://example.com/hashtag/pet-food.html")
    findings = check_archive_search_indexability(_rule(18), _site(), [page], {})
    assert any("tag" in (f.detected_value or "") for f in findings)


def test_task_type_separation():
    from audit_rules.reporting import task_type_for
    types = {
        task_type_for("Error", "EXECUTED_FULL", "FAIL"),
        task_type_for("Opportunity", "EXECUTED_FULL", "OPPORTUNITY"),
        task_type_for("Info", "NOT_CHECKED", "UNKNOWN"),
        task_type_for("Info", "EXECUTED_FULL", "PASS"),
    }
    assert types == {"REMEDIATION", "OPTIMIZATION", "DATA_REQUIRED", "MONITORING"}


def test_artifact_metrics_consistency():
    from audit_rules.reporting import final_artifact_metrics
    metrics = final_artifact_metrics(
        audit_rows=80, matrix_rows=80, coverage_rows=80, finding_rows=903,
        task_rows=903, manual_rows=8, performance_rows=5, pdf_pages=79,
        confirmed_remediation=0, optimization=0, data_required=0,
        manual_review_actions=8, p0=0, p1=0, p2=0, p3=0,
        score=90.75, coverage_pct=64.29, confidence_pct=87.09,
    )
    assert metrics["audit_rows"] == metrics["matrix_rows"] == 80
    assert metrics["finding_rows"] == metrics["task_rows"]
