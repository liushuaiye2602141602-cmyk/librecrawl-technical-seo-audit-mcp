"""Report consistency validator — one diagnostic source of truth.

Before a client DOCX is exported, every number and statement must reconcile
with the same ReportViewModel.audit_items and task set that rendered the
80-row summary. Client mode fails closed (raises) on any contradiction;
internal mode may expose the diagnostics instead.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


_ALLOWED_TASK_RESULT = {
    "REMEDIATION": {"FAIL", "WARNING"},
    "OPTIMIZATION": {"OPPORTUNITY"},
    "DATA_REQUIRED": {"UNKNOWN", "NOT_CHECKED"},
    "MANUAL_REVIEW": {"MANUAL_REVIEW_REQUIRED", "UNKNOWN", "WARNING"},
    "MONITORING": {"PASS", "WARNING"},
}


def validate_report_consistency(
    view_model: Any,
    items: list[dict],
    task_rows: list[dict],
) -> list[str]:
    """Return violations; empty means the report is consistent."""
    violations: list[str] = []
    audit_items = view_model.audit_items

    # 1/2. Distributions must match the same audit items rendered in the
    # 80-row summary, and totals must equal 80.
    actual_result = Counter(str(item.get("result") or "UNKNOWN")
                            for item in audit_items)
    actual_execution = Counter(str(item.get("execution") or "NOT_CHECKED")
                               for item in audit_items)
    if dict(view_model.result_distribution) != dict(actual_result):
        violations.append(
            "result_distribution does not match audit item rows")
    if dict(view_model.execution_distribution) != dict(actual_execution):
        violations.append(
            "execution_distribution does not match audit item rows")
    if len(audit_items) != 80:
        violations.append(f"audit item count is {len(audit_items)}, not 80")

    # 3. Finding/action invariants and acceptance semantics.
    for item in audit_items:
        result = str(item.get("result") or "UNKNOWN")
        execution = str(item.get("execution") or "NOT_CHECKED")
        action = str(item.get("what_to_do") or "")
        acceptance = str(item.get("how_to_verify") or "")
        summary_action = str(item.get("summary_action") or "")
        if execution == "NOT_APPLICABLE":
            if summary_action == "Fix" or "Fix" == str(
                    item.get("action_priority") or ""):
                violations.append(
                    f"audit #{item.get('audit_id')} N/A summary action is Fix")
            if item.get("required_data") or item.get("how_to_complete"):
                violations.append(
                    f"audit #{item.get('audit_id')} NOT_APPLICABLE "
                    "requests data like a data gap")
            if "not yet verified" in acceptance.lower() or "未验证" in acceptance:
                violations.append(
                    f"audit #{item.get('audit_id')} N/A says Not yet verified")
            if "remediation" in action.lower() or "hreflang" in action.lower():
                violations.append(
                    f"audit #{item.get('audit_id')} N/A contains "
                    "remediation instructions")
        if execution == "NOT_CHECKED":
            if "provide" not in action.lower() and "re-run" not in action.lower():
                if "optimize" in action.lower() or "fix" in action.lower():
                    violations.append(
                        f"audit #{item.get('audit_id')} NOT_CHECKED primary "
                        "action is a speculative fix")
        if result == "MANUAL_REVIEW_REQUIRED":
            if "complete the manual review" not in action.lower():
                violations.append(
                    f"audit #{item.get('audit_id')} MANUAL_REVIEW primary "
                    "action is not the review")
            if "confirm" in action.lower() and "mismatch" in action.lower():
                pass  # conditional phrasing allowed
        if result in ("FAIL", "WARNING", "OPPORTUNITY"):
            if not action:
                violations.append(
                    f"audit #{item.get('audit_id')} {result} has no action")
            if "no remediation required" in action.lower():
                violations.append(
                    f"audit #{item.get('audit_id')} {result} says "
                    "no remediation required")
            if _claims_acceptance_met(acceptance):
                violations.append(
                    f"audit #{item.get('audit_id')} {result} claims "
                    "acceptance currently met")
        if result == "UNKNOWN" and item.get("not_verified"):
            if _claims_acceptance_met(acceptance):
                violations.append(
                    f"audit #{item.get('audit_id')} UNKNOWN claims "
                    "acceptance met")
            if not item.get("required_data") or not item.get("how_to_complete"):
                violations.append(
                    f"audit #{item.get('audit_id')} UNKNOWN lacks "
                    "required data / completion guidance")
        if result == "NOT_APPLICABLE":
            if item.get("required_data") or item.get("how_to_complete"):
                violations.append(
                    f"audit #{item.get('audit_id')} NOT_APPLICABLE "
                    "requests data like a data gap")
            if not item.get("why_not_applicable"):
                violations.append(
                    f"audit #{item.get('audit_id')} NOT_APPLICABLE "
                    "lacks a reason")
            if item.get("action_priority") != "N/A":
                violations.append(
                    f"audit #{item.get('audit_id')} NOT_APPLICABLE "
                    "action priority is not N/A")
    # 7. Displayed technology evidence must be non-empty.
    for observation in view_model.technology_observations:
        if not observation.get("evidence"):
            violations.append(
                f"technology {observation.get('technology')} has blank "
                "client evidence")
    # 8. Internal scope tokens must not reach client output.
    for row in view_model.manual_review_rows:
        scope = str(row.get("scope") or "")
        if scope.strip().upper() == "SITE":
            violations.append("internal SITE token reached client output")
    # 9. Crawl-only #02 must not claim GSC/Bing verification.
    for item in audit_items:
        if int(item.get("audit_id") or 0) == 2:
            data_source = str(item.get("data_source") or "")
            acceptance = str(item.get("how_to_verify") or "").lower()
            if "librecrawl" in data_source.lower() and (
                    "gsc" in acceptance or "bing" in acceptance) and (
                    "not checked" not in acceptance
                    and "not verified" not in acceptance):
                violations.append(
                    "crawl-only #02 claims GSC/Bing verification")

    # 4. Task -> audit result reconciliation.
    by_id = {item.get("audit_id"): item for item in audit_items}
    for row in task_rows:
        audit_id = int(row.get("audit_id") or 0)
        task_type = str(row.get("task_type") or "MONITORING")
        audit = by_id.get(audit_id)
        allowed = _ALLOWED_TASK_RESULT.get(task_type, set())
        if audit is None:
            violations.append(f"task #{audit_id} has no audit row")
            continue
        result = str(audit.get("result") or "UNKNOWN")
        if result not in allowed:
            violations.append(
                f"task {task_type} for audit #{audit_id} ({result}) is "
                "not an allowed combination")

    # 5. Key Findings actions must agree with the Full Audit actions.
    finding_actions = {
        f.get("audit_id"): str(f.get("recommended_action") or "")
        for f in view_model.key_findings
    }
    for audit_id, action in finding_actions.items():
        audit = by_id.get(audit_id)
        if audit and action != str(audit.get("what_to_do") or ""):
            violations.append(
                f"key finding #{audit_id} action differs from full audit")

    # 6. Checklist must match the remediation plan (same task set).
    plan_keys = {
        (row.get("audit_id"), row.get("problem"), row.get("action"))
        for row in view_model.remediation_plan
    }
    checklist_keys = {
        (row.get("audit_id"), row.get("problem"), row.get("action"))
        for row in view_model.checklist_rows
    }
    if plan_keys != checklist_keys:
        violations.append("checklist does not match remediation plan")
    return violations


def _claims_acceptance_met(text: str) -> bool:
    lowered = text.lower()
    if "not yet verified" in lowered or "未验证" in lowered:
        return False
    return ("met" in lowered or "满足" in lowered
            or "已满足" in lowered or "达标" in lowered)


def assert_client_consistent(
    view_model: Any, items: list[dict], task_rows: list[dict],
) -> None:
    """Fail closed for client export on any consistency violation."""
    violations = validate_report_consistency(view_model, items, task_rows)
    if violations:
        raise ValueError(
            "client report consistency check failed: " + "; ".join(violations))
