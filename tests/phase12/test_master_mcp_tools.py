"""Aggregate master-audit MCP result surfaces."""

import csv
import json


def test_master_status_helper_aggregates_score_coverage_tasks_and_providers(tmp_path):
    from audit_rules.mcp_status import build_master_audit_status

    coverage = tmp_path / "coverage.csv"
    with coverage.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "audit_id", "impl_status", "execution_status", "result_status",
            "not_checked_reason"])
        writer.writeheader()
        writer.writerow({"audit_id": 53, "impl_status": "NEW_MANUAL",
                         "execution_status": "EXECUTED_FULL", "result_status": "PASS"})
        writer.writerow({"audit_id": 75, "impl_status": "EXISTING_PARTIAL",
                         "execution_status": "NOT_CHECKED", "result_status": "UNKNOWN",
                         "not_checked_reason": "Data source unavailable: GSC API"})
    score = tmp_path / "score.json"
    score.write_text(json.dumps({"overall_score": 88, "coverage_pct": 50}), encoding="utf-8")
    tasks = tmp_path / "tasks.csv"
    tasks.write_text("audit_id,status\n1,open\n", encoding="utf-8")
    artifacts = [
        {"kind": "coverage_csv", "path": str(coverage)},
        {"kind": "audit_score_json", "path": str(score)},
        {"kind": "task_csv", "path": str(tasks)},
        {"kind": "search_performance_csv", "path": str(tmp_path / "gsc.csv")},
    ]

    result = build_master_audit_status(
        {"id": "s1", "status": "done", "url": "https://example.com"},
        artifacts, [])

    assert result["score"]["overall_score"] == 88
    assert result["coverage"]["total_rules"] == 2
    assert result["coverage"]["not_checked_rules"] == 1
    assert result["manual_review"] == {"total": 1, "completed": 1, "pending": 0}
    assert result["task_count"] == 1
    assert result["providers"]["GSC API"] == "EVIDENCE_COLLECTED"
    assert result["artifacts_complete"] is False
