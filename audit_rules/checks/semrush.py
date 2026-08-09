"""Semrush-backed backlink audit checks."""

from __future__ import annotations

from audit_rules.adapters import DataUnavailableError, PartialExecutionError
from audit_rules.context import PageContext, SiteContext
from audit_rules.models import Finding, RuleDefinition


def _payload(data: dict, family: str) -> dict:
    value = data.get("semrush")
    if not isinstance(value, dict):
        raise DataUnavailableError("Semrush API evidence unavailable")
    if any(str(error).startswith(f"{family}:") for error in value.get("errors", [])):
        raise DataUnavailableError(f"Semrush {family} evidence unavailable")
    return value


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
        data_source="Semrush API", confidence=1.0)


def check_backlink_overview(rule: RuleDefinition, site_ctx: SiteContext,
                            page_contexts: list[PageContext], data: dict) -> list[Finding]:
    overview = _payload(data, "overview").get("overview")
    if not isinstance(overview, dict):
        raise DataUnavailableError("Semrush backlink overview unavailable")
    domains = int(overview.get("domains_count", 0) or 0)
    backlinks = int(overview.get("backlinks_count", 0) or 0)
    score = int(overview.get("score", 0) or 0)
    severity = "Opportunity" if domains == 0 else "Info"
    return [_finding(
        rule, url=site_ctx.base_url or "SITE",
        detected=f"{domains} referring domains; {backlinks} backlinks; Authority Score {score}",
        expected="Backlink baseline recorded and monitored for material changes",
        evidence=(f"follow={int(overview.get('follows_count', 0) or 0)}; "
                  f"new_30d={int(overview.get('new_count', 0) or 0)}; "
                  f"lost_30d={int(overview.get('lost_count', 0) or 0)}"),
        severity=severity)]


def check_lost_backlinks(rule: RuleDefinition, site_ctx: SiteContext,
                         page_contexts: list[PageContext], data: dict) -> list[Finding]:
    payload = _payload(data, "lost_links")
    links = payload.get("lost_links")
    if not isinstance(links, list):
        raise DataUnavailableError("Semrush lost backlink list unavailable")
    crawled = {page.url for page in page_contexts if page.status_code == 200}
    findings: list[Finding] = []
    for link in links:
        if not isinstance(link, dict) or link.get("is_lost") is not True:
            continue
        target = str(link.get("target_url") or "")
        domain_score = float(link.get("domain_score", 0) or 0)
        if target not in crawled or domain_score < 30 or link.get("is_nofollow") is True:
            continue
        findings.append(_finding(
            rule, url=target,
            detected=f"Lost followed backlink from Authority Score {domain_score:g} domain",
            expected="Important authoritative backlinks remain live or are intentionally replaced",
            evidence=(f"source={link.get('source_url', '')}; anchor={link.get('anchor', '')}; "
                      f"last_seen={link.get('last_seen_at', '')}"),
            severity="Warning"))
    if payload.get("lost_truncated"):
        raise PartialExecutionError(
            f"Semrush lost backlink result truncated at {len(links)}/{payload.get('lost_total', 0)} rows",
            findings)
    return findings
