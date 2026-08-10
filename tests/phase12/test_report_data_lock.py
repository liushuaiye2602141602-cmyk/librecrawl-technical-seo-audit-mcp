"""CROSS-SITE DATA LOCK regressions.

Client report counts must derive from the current run/replay artifacts; a
second-site fixture must never show the first fixture's page-count metrics.
Performance statements must match the actual performance artifact and rule
execution (no PSI claim when provider data is absent).
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _replay(pages=228, sitemap_total=227, both=227, source="https://client.example/"):
    return {
        "counts": {"page_count": pages, "link_count": pages * 10},
        "sitemap_reconciliation": {
            "sitemap_total": sitemap_total,
            "both_count": both,
            "sitemap_fetch_errors": [],
            "crawl_total": pages,
        },
        "source_url": source,
    }


def _pages(n=228, suffix=".html"):
    return [{"url": f"https://client.example/p{i}{suffix}", "status_code": 200}
            for i in range(n)]


def test_report_actual_state_uses_current_run_page_count():
    from audit_rules.reporting import report_run_metrics
    metrics = report_run_metrics(_replay(pages=228), _pages(228))
    assert metrics["pages_crawled"] == 228
    other = report_run_metrics(_replay(pages=315), _pages(315))
    assert other["pages_crawled"] == 315
    # The second fixture never inherits the first fixture's counts.
    assert metrics["pages_crawled"] != other["pages_crawled"]


def test_report_sitemap_metrics_use_current_run():
    from audit_rules.reporting import report_run_metrics
    metrics = report_run_metrics(_replay(sitemap_total=227, both=226), _pages())
    assert metrics["sitemap_urls_parsed"] == 227
    assert metrics["sitemap_urls_matched"] == 226
    other = report_run_metrics(
        _replay(sitemap_total=315, both=315), _pages(315))
    assert other["sitemap_urls_parsed"] == 315
    assert metrics["sitemap_urls_parsed"] != other["sitemap_urls_parsed"]


def test_report_lastmod_metrics_use_current_run():
    from audit_rules.reporting import report_run_metrics
    metrics = report_run_metrics(_replay(sitemap_total=227), _pages())
    assert metrics["sitemap_lastmod_scanned"] == 227
    other = report_run_metrics(_replay(sitemap_total=315), _pages(315))
    assert other["sitemap_lastmod_scanned"] == 315


def test_report_remote_observation_does_not_reuse_previous_site_counts():
    from audit_rules.reporting import remote_observation_counts
    # First fixture: Baolai-like .html-heavy crawl.
    first = remote_observation_counts(_pages(315))
    # Second fixture: extensionless crawl.
    second = remote_observation_counts(_pages(228, suffix=""))
    assert first["html_suffix"] == 315
    assert second["html_suffix"] == 0
    assert second["extensionless"] == 228
    assert first["html_suffix"] != second["html_suffix"]


def test_technical_appendix_matches_rule_execution():
    from audit_rules.docx_report import _psi_appendix_note
    base = {
        "audit_id": 19, "execution": "EXECUTED_PARTIAL",
        "result": "WARNING", "check": "CWV",
    }
    partial_items = [dict(base, audit_id=aid) for aid in (19, 21, 22, 24, 61)]
    assert "partial execution" in _psi_appendix_note(partial_items)
    assert "NOT_CHECKED" not in _psi_appendix_note(partial_items)


def test_no_psi_claim_when_provider_data_absent():
    from audit_rules.docx_report import _psi_appendix_note
    not_checked_items = [
        {"audit_id": aid, "execution": "NOT_CHECKED", "result": "UNKNOWN"}
        for aid in (19, 21, 22, 24, 61, 62, 63)
    ]
    note = _psi_appendix_note(not_checked_items)
    assert "NOT_CHECKED" in note
    assert "no PSI success is claimed" in note
    assert "partial execution" not in note


def test_performance_report_matches_performance_artifact():
    from audit_rules.docx_report import _psi_appendix_note
    # With zero PSI rows in the artifact, no partial claim may appear.
    assert _psi_appendix_note([]) == ""
