"""Server access-log audit checks."""

from __future__ import annotations

from audit_rules.adapters import DataUnavailableError, PartialExecutionError
from audit_rules.context import PageContext, SiteContext
from audit_rules.models import Finding, RuleDefinition


def _finding(rule: RuleDefinition, *, url: str, detected: str, expected: str,
             evidence: str, severity: str) -> Finding:
    return Finding(
        audit_id=rule.audit_id, rule_id=rule.rule_id, url=url,
        category=rule.category.value, priority=rule.priority.value,
        severity=severity, finding_type=rule.default_finding_type,
        scope=rule.scope.value, detected_value=detected,
        expected_value=expected, evidence=evidence,
        finding_detail=f"{detected}. {evidence}", remediation=rule.remediation,
        owner=rule.owner, acceptance_criteria=rule.acceptance_criteria,
        data_source="Server Logs", confidence=1.0)


def check_server_log_analysis(rule: RuleDefinition, site_ctx: SiteContext,
                              page_contexts: list[PageContext], data: dict) -> list[Finding]:
    logs = data.get("server_logs")
    if not isinstance(logs, dict) or int(logs.get("valid_lines", 0) or 0) <= 0:
        raise DataUnavailableError("Server log evidence unavailable")
    valid = int(logs.get("valid_lines", 0) or 0)
    bots = sum(int(value or 0) for value in (logs.get("bot_counts") or {}).values())
    statuses = logs.get("status_counts") or {}
    errors_5xx = sum(int(value or 0) for key, value in statuses.items()
                     if str(key).startswith("5"))
    waste = sum(int(value or 0) for value in (logs.get("waste_bot_counts") or {}).values())
    findings = [_finding(
        rule, url=site_ctx.base_url or "SITE",
        detected=f"{bots} bot requests across {valid} valid log lines",
        expected="Search-engine crawl activity is measured and reviewed",
        evidence=(f"bots={logs.get('bot_counts', {})}; statuses={statuses}; "
                  f"response_time_p95_ms={logs.get('response_time_p95_ms')}"),
        severity="Info")]
    if valid and errors_5xx / valid >= 0.02:
        findings.append(_finding(
            rule, url=site_ctx.base_url or "SITE",
            detected=f"5xx log ratio {errors_5xx / valid * 100:.1f}%",
            expected="Sustained 5xx ratio below 2%",
            evidence=f"5xx={errors_5xx}; valid_lines={valid}", severity="Error"))
    if bots and waste / bots >= 0.20:
        findings.append(_finding(
            rule, url=site_ctx.base_url or "SITE",
            detected=f"Potential crawl-waste bot ratio {waste / bots * 100:.1f}%",
            expected="Bots spend most requests on intentional canonical URLs",
            evidence=f"waste_bot_hits={waste}; bot_requests={bots}", severity="Warning"))
    malformed = int(logs.get("malformed_lines", 0) or 0)
    processed = int(logs.get("processed_lines", 0) or 0)
    if logs.get("truncated") or (processed and malformed / processed > 0.10):
        reasons = []
        if logs.get("truncated"):
            reasons.append("input truncated at configured line limit")
        if processed and malformed / processed > 0.10:
            reasons.append(f"malformed ratio {malformed / processed * 100:.1f}%")
        raise PartialExecutionError("Server log evidence partial: " + "; ".join(reasons), findings)
    return findings
