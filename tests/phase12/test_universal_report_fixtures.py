"""Generic offline fixtures all render the same universal report template."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

docx = pytest.importorskip("docx")


def _item(audit_id, result="PASS", execution="EXECUTED_FULL", affected=0,
           priority="Medium"):
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
        "evidence": f"evidence-{audit_id}",
        "affected_urls": affected,
        "representative": [],
        "seo_impact": "Impact text",
        "fix": "No remediation required." if result == "PASS" else "Fix it.",
        "owner": "SEO",
        "acceptance": "Acceptance criteria",
        "limitations": "",
        "observed": "",
        "manual": {},
        "is_pass": result == "PASS",
        "action_required": "None" if result == "PASS" else "Fix",
    }


def _items_with(pattern: str) -> list[dict]:
    items = [_item(i + 1) for i in range(80)]
    items[1]["execution"] = "EXECUTED_PARTIAL"
    if pattern == "generic_wordpress_site":
        pass
    elif pattern == "generic_nonwordpress_site":
        pass
    elif pattern == "multilingual_site":
        items[28]["result"] = "OPPORTUNITY"
        items[28]["affected_urls"] = 199
    elif pattern == "single_language_site":
        pass
    elif pattern == "site_with_failures":
        for audit_id in (6, 8, 15):
            items[audit_id - 1]["result"] = "FAIL"
            items[audit_id - 1]["priority"] = "Critical"
            items[audit_id - 1]["affected_urls"] = 12
    elif pattern == "healthy_site":
        pass
    elif pattern == "site_with_missing_external_data":
        for audit_id in (19, 34, 35, 61):
            items[audit_id - 1]["execution"] = "NOT_CHECKED"
            items[audit_id - 1]["result"] = "UNKNOWN"
            items[audit_id - 1]["limitations"] = "Data source unavailable: GSC"
    elif pattern == "technology_unknown_site":
        pass
    elif pattern == "large_issue_count_site":
        for audit_id in (11, 45, 79):
            items[audit_id - 1]["result"] = "WARNING"
            items[audit_id - 1]["affected_urls"] = 3000
            items[audit_id - 1]["evidence"] = "\n".join(
                f"https://fixture.example/p{i}" for i in range(3000))
    return items


FIXTURES = (
    "generic_wordpress_site",
    "generic_nonwordpress_site",
    "multilingual_site",
    "single_language_site",
    "site_with_failures",
    "healthy_site",
    "site_with_missing_external_data",
    "technology_unknown_site",
    "large_issue_count_site",
)


@pytest.mark.parametrize("pattern", FIXTURES)
def test_generic_fixture_renders_universal_report(tmp_path, pattern):
    from audit_rules.report_view import build_report_view
    from audit_rules.docx_report import build_universal_docx
    from tests.phase12.test_universal_report_view import _metrics
    items = _items_with(pattern)
    metrics = _metrics()
    view = build_report_view(
        items, [], metrics, manual_rows=[],
        technology_profile=None, technology_risks=[],
        domain="https://fixture.example/", audit_date="2026-08-11",
        pages_crawled=len(items))
    output = tmp_path / f"{pattern}.docx"
    build_universal_docx(
        str(output), view_model=view, items=items, task_rows=[],
        metrics=metrics,
        result_counts={"PASS": 80}, execution_counts={"EXECUTED_FULL": 80},
        manual_rows=[], schema_distribution={},
        domain="https://fixture.example/", audit_date="2026-08-11",
        site_name="Fixture", pages_crawled=len(items))
    from docx import Document
    doc = Document(str(output))
    audits = [p for p in doc.paragraphs
              if p.style.name == "Heading 2" and p.text.startswith("AUDIT #")]
    assert len(audits) == 80
