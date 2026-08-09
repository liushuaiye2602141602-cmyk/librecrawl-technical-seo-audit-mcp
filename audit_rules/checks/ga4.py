"""GA4-backed configuration and conversion tracking checks."""

from __future__ import annotations

from audit_rules.adapters import DataUnavailableError, PartialExecutionError
from audit_rules.context import PageContext, SiteContext
from audit_rules.models import Finding, RuleDefinition


def _source(data: dict, key: str, family: str) -> dict:
    payload = data.get(key)
    if not isinstance(payload, dict):
        raise DataUnavailableError(f"{key.upper()} API evidence unavailable")
    if any(str(error).startswith(f"{family}:") for error in payload.get("errors", [])):
        raise DataUnavailableError(f"{key.upper()} {family} evidence unavailable")
    return payload


def _finding(rule: RuleDefinition, *, detected: str, expected: str,
             evidence: str, severity: str = "Error") -> Finding:
    return Finding(
        audit_id=rule.audit_id, rule_id=rule.rule_id, url="SITE",
        category=rule.category.value, priority=rule.priority.value,
        severity=severity, finding_type=rule.default_finding_type,
        scope=rule.scope.value, detected_value=detected,
        expected_value=expected, evidence=evidence,
        finding_detail=f"{detected}. {evidence}", remediation=rule.remediation,
        owner=rule.owner, acceptance_criteria=rule.acceptance_criteria,
        data_source="GA4 API", confidence=1.0)


def check_gsc_ga4_config(rule: RuleDefinition, site_ctx: SiteContext,
                         page_contexts: list[PageContext], data: dict) -> list[Finding]:
    ga4 = _source(data, "ga4", "property")
    _source(data, "ga4", "daily_activity")
    _source(data, "gsc", "search_analytics")
    prop = ga4.get("property")
    daily = ga4.get("daily_activity")
    if not isinstance(prop, dict) or not isinstance(daily, list):
        raise DataUnavailableError("GA4 property or daily activity evidence unavailable")
    findings: list[Finding] = []
    if prop.get("deleteTime"):
        findings.append(_finding(
            rule, detected="GA4 property is trashed",
            expected="An active GA4 property for the production domain",
            evidence=f"property={prop.get('name', '')}; deleteTime present"))
    sessions = sum(int(row.get("sessions", 0) or 0) for row in daily if isinstance(row, dict))
    if sessions <= 0:
        findings.append(_finding(
            rule, detected="No sessions observed in the finalized 28-day GA4 window",
            expected="Continuous production analytics data",
            evidence=f"days_with_rows={len(daily)}; sessions={sessions}"))
    elif len(daily) < 20:
        findings.append(_finding(
            rule, detected=f"GA4 activity appears on only {len(daily)} days",
            expected="Continuous daily activity or an explained low-traffic pattern",
            evidence=f"sessions={sessions}", severity="Warning"))
    raise PartialExecutionError(
        "GA4/GSC APIs checked; Bing verification and duplicate browser tag detection remain manual",
        findings)


def check_event_conversion_tracking(rule: RuleDefinition, site_ctx: SiteContext,
                                    page_contexts: list[PageContext], data: dict) -> list[Finding]:
    ga4 = _source(data, "ga4", "key_events")
    _source(data, "ga4", "event_counts")
    key_events = ga4.get("key_events")
    counts = ga4.get("event_counts")
    if not isinstance(key_events, list) or not isinstance(counts, dict):
        raise DataUnavailableError("GA4 key-event evidence unavailable")
    findings: list[Finding] = []
    names = sorted({str(item.get("eventName") or "") for item in key_events
                    if isinstance(item, dict) and item.get("eventName")})
    if not names:
        findings.append(_finding(
            rule, detected="No GA4 key events are configured",
            expected="Business-critical lead or purchase events configured as GA4 key events",
            evidence=f"observed_event_names={len(counts)}"))
    for name in names:
        count = int(counts.get(name, 0) or 0)
        if count <= 0:
            findings.append(_finding(
                rule, detected=f"GA4 key event '{name}' has zero observed events",
                expected="Configured key events receive verified production events",
                evidence=f"eventName={name}; eventCount={count}", severity="Warning"))
    raise PartialExecutionError(
        "GA4 configuration and counts checked; GTM preview and end-to-end submissions remain manual",
        findings)
