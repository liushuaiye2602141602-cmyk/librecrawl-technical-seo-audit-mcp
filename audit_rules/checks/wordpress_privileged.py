"""WordPress administrator-snapshot checks for Rules 36, 64, 65, 68, 69."""

from __future__ import annotations

from audit_rules.adapters import DataUnavailableError, PartialExecutionError
from audit_rules.context import PageContext, SiteContext
from audit_rules.models import Finding, RuleDefinition


def _source(data: dict) -> dict:
    payload = data.get("wordpress_privileged")
    if not isinstance(payload, dict) or payload.get("errors"):
        raise DataUnavailableError("WordPress privileged snapshot unavailable")
    return payload


def _finding(rule: RuleDefinition, *, detected: str, expected: str,
             evidence: str, severity: str | None = None) -> Finding:
    return Finding(
        audit_id=rule.audit_id, rule_id=rule.rule_id, url="SITE",
        category=rule.category.value, priority=rule.priority.value,
        severity=severity or rule.severity.value,
        finding_type=rule.default_finding_type, scope=rule.scope.value,
        detected_value=detected, expected_value=expected, evidence=evidence,
        finding_detail=f"{detected}. {evidence}", remediation=rule.remediation,
        owner=rule.owner, acceptance_criteria=rule.acceptance_criteria,
        data_source="WordPress Privileged", confidence=1.0,
    )


def check_wp_updates_security(rule: RuleDefinition, site_ctx: SiteContext,
                              page_contexts: list[PageContext], data: dict) -> list[Finding]:
    wp = _source(data)
    findings: list[Finding] = []
    core = wp.get("core") or {}
    if core.get("update_available"):
        findings.append(_finding(
            rule, detected="WordPress core update is available",
            expected="Supported WordPress core with planned security updates",
            evidence=f"installed_version={core.get('version', 'unknown')}", severity="Warning"))
    if core.get("vulnerable"):
        findings.append(_finding(
            rule, detected="WordPress core is reported vulnerable",
            expected="No known vulnerable production core",
            evidence=f"installed_version={core.get('version', 'unknown')}"))
    for family in ("plugins", "themes"):
        for item in wp.get(family, []):
            label = f"{family[:-1]} {item.get('slug', 'unknown')}"
            if item.get("update_available"):
                findings.append(_finding(
                    rule, detected=f"Update available for {label}",
                    expected="Necessary components remain supported and updated",
                    evidence=f"version={item.get('version', 'unknown')}", severity="Warning"))
            if item.get("vulnerable"):
                findings.append(_finding(
                    rule, detected=f"Vulnerability reported for {label}",
                    expected="No known vulnerable production components",
                    evidence=f"version={item.get('version', 'unknown')}"))
    raise PartialExecutionError(
        "Snapshot versions checked; advisory provenance, exploitability, backups, and staging regression remain manual",
        findings)


def check_wp_cron_tasks(rule: RuleDefinition, site_ctx: SiteContext,
                        page_contexts: list[PageContext], data: dict) -> list[Finding]:
    wp = _source(data)
    findings: list[Finding] = []
    for event in wp.get("cron_events", []):
        hook = event.get("hook", "unknown")
        overdue = int(event.get("overdue_seconds", 0) or 0)
        interval = int(event.get("interval_seconds", 0) or 0)
        if overdue >= 300:
            findings.append(_finding(
                rule, detected=f"WP-Cron hook {hook} is overdue by {overdue} seconds",
                expected="Scheduled tasks run without material backlog",
                evidence=f"hook={hook}; overdue_seconds={overdue}"))
        if 0 < interval < 60:
            findings.append(_finding(
                rule, detected=f"WP-Cron hook {hook} repeats every {interval} seconds",
                expected="No unexplained sub-minute recurring WordPress jobs",
                evidence=f"hook={hook}; interval_seconds={interval}", severity="Warning"))
    raise PartialExecutionError(
        "WP-Cron inventory checked; server-log duration, job ownership, and business necessity remain manual",
        findings)


def check_database_autoload_bloat(rule: RuleDefinition, site_ctx: SiteContext,
                                  page_contexts: list[PageContext], data: dict) -> list[Finding]:
    wp = _source(data)
    autoload = wp.get("autoload") or {}
    total = int(autoload.get("total_bytes", 0) or 0)
    findings: list[Finding] = []
    if total > 800 * 1024:
        findings.append(_finding(
            rule, detected=f"Autoload total is {total} bytes",
            expected="Autoload total at or below 800 KiB unless explicitly justified",
            evidence=f"total_bytes={total}", severity="Warning"))
    for option in autoload.get("largest_options", []):
        size = int(option.get("bytes", 0) or 0)
        if size > 100 * 1024:
            findings.append(_finding(
                rule, detected=f"Autoload option {option.get('name', 'unknown')} is {size} bytes",
                expected="Individual autoload options at or below 100 KiB unless justified",
                evidence=f"option={option.get('name', 'unknown')}; bytes={size}", severity="Warning"))
    raise PartialExecutionError(
        "Autoload size checked; slow-query attribution and safe deletion require DBA review and backups",
        findings)


def check_admin_2fa(rule: RuleDefinition, site_ctx: SiteContext,
                    page_contexts: list[PageContext], data: dict) -> list[Finding]:
    wp = _source(data)
    total = int(wp.get("admin_total", 0) or 0)
    without = int(wp.get("admin_without_2fa", 0) or 0)
    findings = []
    if without:
        findings.append(_finding(
            rule, detected=f"{without} of {total} administrators lack confirmed 2FA",
            expected="All privileged WordPress accounts use enforced 2FA",
            evidence=f"admin_total={total}; admin_without_2fa={without}"))
    raise PartialExecutionError(
        "Administrator 2FA coverage checked; WAF, rate limits, recovery, and login-event review remain manual",
        findings)


def check_abandoned_plugins_themes(rule: RuleDefinition, site_ctx: SiteContext,
                                   page_contexts: list[PageContext], data: dict) -> list[Finding]:
    wp = _source(data)
    findings: list[Finding] = []
    for family in ("plugins", "themes"):
        for item in wp.get(family, []):
            slug = item.get("slug", "unknown")
            reasons = []
            if item.get("status") == "inactive":
                reasons.append("retained but inactive")
            if item.get("abandoned"):
                reasons.append("reported abandoned")
            age = int(item.get("last_updated_days", 0) or 0)
            if age >= 730:
                reasons.append(f"not updated for {age} days")
            if reasons:
                findings.append(_finding(
                    rule, detected=f"{family[:-1]} {slug}: {', '.join(reasons)}",
                    expected="Only necessary and actively maintained production components",
                    evidence=f"status={item.get('status')}; last_updated_days={age}"))
    raise PartialExecutionError(
        "Inventory heuristics checked; collector maintenance-status provenance and replacement risk remain manual",
        findings)
