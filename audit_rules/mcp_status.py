"""Aggregate registered audit artifacts for the MCP status surface."""

import csv
import json
from pathlib import Path


_REQUIRED = {
    "coverage_csv", "task_csv", "manual_review_md", "audit_score_json",
    "audit_snapshot", "master_report_md", "master_report_pdf",
}
_PROVIDER_ARTIFACTS = {
    "PageSpeed API": "performance_csv",
    "GSC API": "search_performance_csv",
    "Semrush API": "backlinks_csv",
    "GA4 API": "ga4_audit_json",
    "Server Logs": "server_log_analysis_csv",
    "WordPress Privileged": "wordpress_audit_json",
    "Rendered DOM Snapshot": "render_audit_json",
    "Availability Monitor": "availability_audit_json",
}


def _read_json(path: str) -> dict | None:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def _read_csv(path: str) -> list[dict]:
    try:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))
    except (OSError, csv.Error):
        return []


def build_master_audit_status(session: dict, artifacts: list[dict],
                              events: list[dict]) -> dict:
    """Build a bounded, JSON-safe status view from registered artifacts only."""
    by_kind = {item["kind"]: item["path"] for item in artifacts}
    coverage_rows = _read_csv(by_kind["coverage_csv"]) if "coverage_csv" in by_kind else []
    manual_rows = [row for row in coverage_rows if row.get("impl_status") == "NEW_MANUAL"]
    manual_completed = sum(1 for row in manual_rows
                           if row.get("execution_status") != "NOT_CHECKED")
    task_rows = _read_csv(by_kind["task_csv"]) if "task_csv" in by_kind else []
    partial = any(event.get("kind") in {"v3_artifact_failed", "v3_artifacts_partial",
                                        "v3_pipeline_failed"} for event in events)
    kinds = set(by_kind)
    return {
        "success": True,
        "session_id": session.get("id"),
        "status": session.get("status"),
        "url": session.get("url"),
        "score": (_read_json(by_kind["audit_score_json"])
                  if "audit_score_json" in by_kind else None),
        "coverage": {
            "total_rules": len(coverage_rows),
            "executed_rules": sum(row.get("execution_status") in {
                "EXECUTED_FULL", "EXECUTED_PARTIAL"} for row in coverage_rows),
            "not_checked_rules": sum(row.get("execution_status") == "NOT_CHECKED"
                                     for row in coverage_rows),
            "not_applicable_rules": sum(row.get("execution_status") == "NOT_APPLICABLE"
                                        for row in coverage_rows),
        },
        "manual_review": {"total": len(manual_rows), "completed": manual_completed,
                          "pending": len(manual_rows) - manual_completed},
        "task_count": len(task_rows),
        "providers": {name: ("EVIDENCE_COLLECTED" if kind in kinds
                              else "NO_EVIDENCE_ARTIFACT")
                      for name, kind in _PROVIDER_ARTIFACTS.items()},
        "snapshot": {"exported": "audit_snapshot" in kinds,
                     "baseline_diff_available": "crawl_diff_csv" in kinds},
        "artifacts_complete": _REQUIRED.issubset(kinds) and not partial,
        "artifact_status": ("PARTIAL" if partial or not _REQUIRED.issubset(kinds)
                            else "COMPLETE"),
        "missing_required_artifacts": sorted(_REQUIRED - kinds),
        "artifacts": by_kind,
    }
