"""Regression: report site identity is URL/replay-driven; the production
report path must never fall back to a customer domain.

The formal pipeline derives domain/site identity from the audit URL (and the
replay's source_url when rebuilding offline). This locks that invariant:
no ``baolaipackaging.com`` literal may exist in production report code, and
the derivation expression must yield the audited host, not a constant.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

_PRODUCTION_REPORT_FILES = (
    "runner.py",
    "server.py",
    "pdf_report.py",
    "audit_rules/reporting.py",
)


def test_report_identity_derives_from_audit_url():
    from audit_rules.reporting import report_host
    assert report_host("https://client-x.example/") == "client-x.example"
    assert report_host("https://gelgoogsort.com/") == "gelgoogsort.com"
    assert report_host("https://www.gelgoogsort.com/about/") == "www.gelgoogsort.com"


def test_no_customer_domain_fallback_in_production_report_code():
    for relative in _PRODUCTION_REPORT_FILES:
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        assert "baolaipackaging" not in text, (
            f"{relative} contains a customer-domain fallback")
        assert "gelgoogsort" not in text, (
            f"{relative} contains a customer-domain literal")


def test_replay_source_url_drives_offline_identity(tmp_path):
    from audit_rules.replay import (
        build_replay_document, load_replay_artifact, write_replay_artifact,
    )
    document = build_replay_document(
        source_url="https://client-y.example/",
        git_head="b" * 40,
        generated_at="2026-08-10T00:00:00Z",
        crawl_metadata={
            "crawl_parameters": {}, "truncation_status": "NOT_TRUNCATED"},
        pages=[{
            "url": "https://client-y.example/", "status_code": 200,
        }],
        links=[],
        site_data={},
        sitemap_reconciliation={},
        crawl_completeness={"pages_crawled": 1, "audit_complete": True},
        provider_evidence={},
    )
    target = tmp_path / "client.audit-replay-v1.json.gz"
    write_replay_artifact(document, target, expected_completed_pages=1)
    loaded = load_replay_artifact(target, expected_completed_pages=1)
    assert loaded["source_url"] == "https://client-y.example/"
