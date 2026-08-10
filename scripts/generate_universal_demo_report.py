"""Generate the Universal Master SEO Diagnostic Report demo from a generic
offline fixture. No live site, no client data, no crawl.

Output: reports/universal-demo-<date>/ (DOCX + machine artifacts + ZIP).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _item(audit_id, result="PASS", execution="EXECUTED_FULL", affected=0,
          priority="Medium", limitations="", representative=None):
    return {
        "audit_id": audit_id,
        "category": "Crawling & Indexing",
        "check": f"Check {audit_id}",
        "what_checked": f"What was checked for audit {audit_id}",
        "execution": execution,
        "result": result,
        "priority": priority,
        "confidence": "1.00",
        "data_source": "LibreCrawl",
        "actual_state": "Fixture state: checked scope showed the recorded "
                        "condition.",
        "diagnosis": "Normal" if result == "PASS" else "Actionable finding",
        "evidence": f"https://demo-client.example/p{audit_id} — evidence",
        "affected_urls": affected,
        "representative": representative or [],
        "seo_impact": "Impact on crawl/indexing and user experience.",
        "fix": ("No remediation required." if result == "PASS"
                else "Apply the rule remediation."),
        "owner": "SEO",
        "acceptance": "Acceptance criteria for this rule are met.",
        "limitations": limitations,
        "observed": "",
        "manual": {},
        "is_pass": result == "PASS",
        "action_required": "None" if result == "PASS" else "Fix",
    }


def _build_items() -> list[dict]:
    items = [_item(i + 1) for i in range(80)]
    # Generic demo findings (no client-specific content).
    items[5]["result"] = "FAIL"
    items[5]["priority"] = "Critical"
    items[5]["affected_urls"] = 12
    items[5]["representative"] = [
        "https://demo-client.example/old-product-a",
        "https://demo-client.example/old-product-b",
    ]
    items[9]["result"] = "WARNING"
    items[9]["affected_urls"] = 30
    items[14]["result"] = "OPPORTUNITY"
    items[14]["affected_urls"] = 199
    items[19]["execution"] = "NOT_CHECKED"
    items[19]["result"] = "UNKNOWN"
    items[19]["limitations"] = "Data source unavailable: GSC"
    items[24]["execution"] = "NOT_APPLICABLE"
    items[24]["result"] = "UNKNOWN"
    items[24]["limitations"] = "WordPress-specific rule"
    return items


def _tasks() -> list[dict]:
    return [
        {
            "task_type": "REMEDIATION", "audit_id": 6, "rule_id": "r6",
            "priority": "Critical", "severity": "Error",
            "url": "https://demo-client.example/old-product-a",
            "finding": "Old URLs return 404 instead of 301",
            "evidence": "404 detected", "remediation": "Add 301 redirects",
            "owner": "Developer",
            "acceptance_criteria": "All old URLs return 301",
            "confidence": "1.0", "affected_url_count": 12,
            "affected_urls_sample": "https://demo-client.example/old-product-a",
            "status": "Open",
        },
        {
            "task_type": "OPTIMIZATION", "audit_id": 29, "rule_id": "r29",
            "priority": "Medium", "severity": "Opportunity",
            "url": "https://demo-client.example/es/",
            "finding": "Add hreflang x-default",
            "evidence": "hreflang missing", "remediation": "Add x-default",
            "owner": "SEO",
            "acceptance_criteria": "x-default present on all language pages",
            "confidence": "0.9", "affected_url_count": 199,
            "affected_urls_sample": "https://demo-client.example/es/",
            "status": "Open",
        },
    ]


def _metrics() -> dict:
    return {
        "audit_rows": 80, "matrix_rows": 80, "coverage_rows": 80,
        "finding_rows": 2, "task_rows": 2, "manual_rows": 1,
        "performance_rows": 0, "pdf_pages": 0,
        "confirmed_remediation": 1, "optimization": 1,
        "data_required": 3, "manual_review_actions": 1,
        "p0": 1, "p1": 0, "p2": 1, "p3": 0,
        "score": 88.08, "coverage_pct": 61.25, "confidence_pct": 84.79,
    }


def _technology_profile() -> dict:
    return {
        "schema_version": "technology-profile-v1",
        "detector_version": "1.2.0",
        "signature_registry_version": "1.2.0",
        "source_url": "https://demo-client.example/",
        "detections": [
            {"category": "CMS", "technology_name": "WordPress",
             "status": "DETECTED", "confidence": "High",
             "confidence_score": 0.82, "version": "Unknown",
             "detection_sources": [], "limitations": []},
            {"category": "Ecommerce", "technology_name": "WooCommerce",
             "status": "UNKNOWN", "confidence": "Medium",
             "confidence_score": 0.55, "version": "Unknown",
             "detection_sources": [], "limitations": []},
            {"category": "SEO Technology", "technology_name": "Yoast SEO",
             "status": "UNKNOWN", "confidence": "Low",
             "confidence_score": 0.35, "version": "Unknown",
             "detection_sources": [], "limitations": []},
            {"category": "Analytics", "technology_name": "GA4",
             "status": "DETECTED", "confidence": "High",
             "confidence_score": 0.82, "version": "Unknown",
             "detection_sources": [], "limitations": []},
        ],
        "risk_correlations": [],
        "detection_status": "COMPLETE",
        "limitations": [],
    }


def main() -> None:
    from audit_rules.docx_report import build_universal_docx
    from audit_rules.report_view import build_report_view

    demo_date = os.environ.get("DEMO_DATE", date.today().isoformat())
    out = REPO / "reports" / f"universal-demo-{demo_date}"
    out.mkdir(parents=True, exist_ok=True)
    items = _build_items()
    tasks = _tasks()
    metrics = _metrics()
    tech = _technology_profile()
    view = build_report_view(
        items, tasks, metrics, manual_rows=[{"audit_id": 53}],
        technology_profile=tech, technology_risks=[],
        domain="https://demo-client.example/", audit_date=demo_date,
        pages_crawled=228,
        run_metadata={"run_id": "universal-demo", "replay_sha256": ""},
    )
    docx_path = out / "01_Master_SEO_Diagnostic_Report.docx"
    build_universal_docx(
        str(docx_path), view_model=view,
        items=items, task_rows=tasks, metrics=metrics,
        result_counts={"PASS": 36, "FAIL": 3, "WARNING": 4,
                       "OPPORTUNITY": 5, "MANUAL_REVIEW_REQUIRED": 8,
                       "UNKNOWN": 24},
        execution_counts={"EXECUTED_FULL": 38, "EXECUTED_PARTIAL": 11,
                          "NOT_CHECKED": 31, "NOT_APPLICABLE": 0},
        manual_rows=[{"audit_id": 53, "rule": "Search intent",
                      "scope": "SITE", "status": "PENDING"}],
        schema_distribution={},
        technology_profile=tech, technology_risks=[],
        domain="https://demo-client.example/", audit_date=demo_date,
        site_name="Demo Client", pages_crawled=228,
    )
    (out / "09_Technology_Profile.json").write_text(
        json.dumps(tech, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "07_Audit_Score.json").write_text(
        json.dumps({
            "schema_version": "audit-score-v1",
            "overall_score": metrics["score"],
            "coverage_pct": metrics["coverage_pct"],
            "confidence": {"label": "High", "pct": metrics["confidence_pct"]},
            "executed_rules": 49,
            "eligible_rules": 80,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "08_80_Rule_Coverage.csv").write_text(
        "audit_id,execution_status,result_status\n"
        + "\n".join(
            f"{i+1},{items[i]['execution']},{items[i]['result']}"
            for i in range(80)) + "\n",
        encoding="utf-8")
    (out / "04_Remediation_Tasks.csv").write_text(
        "task_type,audit_id,priority,finding,remediation,owner,"
        "acceptance_criteria,status\n"
        + "\n".join(
            f"{t['task_type']},{t['audit_id']},{t['priority']},"
            f"\"{t['finding']}\",\"{t['remediation']}\",{t['owner']},"
            f"\"{t['acceptance_criteria']}\",{t['status']}"
            for t in tasks) + "\n",
        encoding="utf-8")
    (out / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    (out / "README.txt").write_text(
        "Universal Master SEO Diagnostic Report — demo (offline fixture)\n"
        "Audit Date: " + demo_date + "\n"
        "Files:\n"
        "  01_Master_SEO_Diagnostic_Report.docx — client report (primary)\n"
        "  04_Remediation_Tasks.csv — remediation tasks\n"
        "  07_Audit_Score.json — score/coverage/confidence\n"
        "  08_80_Rule_Coverage.csv — 80-rule coverage\n"
        "  09_Technology_Profile.json — technology profile\n"
        "  metrics.json — FinalArtifactMetrics\n",
        encoding="utf-8")
    zip_path = out.with_name(f"universal-demo-{demo_date}.zip")
    files = sorted(p for p in out.rglob("*") if p.is_file())
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED,
                         compresslevel=6) as archive:
        for path in files:
            archive.write(path, path.relative_to(out).as_posix())
    print("demo dir:", out)
    print("zip:", zip_path)
    print("zip sha256:",
          hashlib.sha256(zip_path.read_bytes()).hexdigest())
    print("docx:", docx_path)


if __name__ == "__main__":
    main()
