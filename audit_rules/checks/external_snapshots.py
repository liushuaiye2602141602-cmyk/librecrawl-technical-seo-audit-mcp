"""Rendered-DOM and availability snapshot checks for Rules 46, 48, and 80."""

from __future__ import annotations

from audit_rules.adapters import DataUnavailableError, PartialExecutionError
from audit_rules.context import PageContext, SiteContext
from audit_rules.models import Finding, RuleDefinition


def _source(data: dict, key: str, label: str) -> dict:
    payload = data.get(key)
    if not isinstance(payload, dict) or payload.get("errors"):
        raise DataUnavailableError(f"{label} evidence unavailable")
    return payload


def _finding(rule: RuleDefinition, *, url: str, detected: str, expected: str,
             evidence: str, source: str, severity: str | None = None) -> Finding:
    return Finding(
        audit_id=rule.audit_id, rule_id=rule.rule_id, url=url,
        category=rule.category.value, priority=rule.priority.value,
        severity=severity or rule.severity.value,
        finding_type=rule.default_finding_type, scope=rule.scope.value,
        detected_value=detected, expected_value=expected, evidence=evidence,
        finding_detail=f"{detected}. {evidence}", remediation=rule.remediation,
        owner=rule.owner, acceptance_criteria=rule.acceptance_criteria,
        data_source=source, confidence=1.0,
    )


def check_js_rendered_content(rule: RuleDefinition, site_ctx: SiteContext,
                              page_contexts: list[PageContext], data: dict) -> list[Finding]:
    snapshot = _source(data, "render_snapshot", "Rendered DOM snapshot")
    findings: list[Finding] = []
    for page in snapshot.get("pages", []):
        raw_text = int(page.get("raw_text_chars", 0) or 0)
        rendered_text = int(page.get("rendered_text_chars", 0) or 0)
        text_delta = rendered_text - raw_text
        if text_delta >= 500 and rendered_text > max(1, raw_text) * 1.3:
            findings.append(_finding(
                rule, url=page["url"],
                detected=f"{text_delta} render-only text characters",
                expected="Material indexable content is present in initial HTML",
                evidence=f"raw_text_chars={raw_text}; rendered_text_chars={rendered_text}",
                source="Rendered DOM Snapshot"))
        raw_links = int(page.get("raw_internal_links", 0) or 0)
        rendered_links = int(page.get("rendered_internal_links", 0) or 0)
        link_delta = rendered_links - raw_links
        if link_delta >= 5 and rendered_links > max(1, raw_links) * 1.2:
            findings.append(_finding(
                rule, url=page["url"],
                detected=f"{link_delta} render-only internal links",
                expected="Important discovery links are crawlable in initial HTML",
                evidence=f"raw_internal_links={raw_links}; rendered_internal_links={rendered_links}",
                source="Rendered DOM Snapshot"))
    raise PartialExecutionError(
        "Rendered comparison checked on a bounded sample; site-wide behavior and Google indexing remain unproven",
        findings)


def check_lazy_load_indexability(rule: RuleDefinition, site_ctx: SiteContext,
                                 page_contexts: list[PageContext], data: dict) -> list[Finding]:
    snapshot = _source(data, "render_snapshot", "Rendered DOM snapshot")
    findings: list[Finding] = []
    for page in snapshot.get("pages", []):
        initial = int(page.get("initial_items", 0) or 0)
        after = int(page.get("after_scroll_items", 0) or 0)
        interaction = bool(page.get("load_more_requires_interaction")) or after > initial
        fallback = bool(page.get("crawlable_pagination_fallback"))
        if interaction and after > initial and not fallback:
            findings.append(_finding(
                rule, url=page["url"],
                detected=f"{after - initial} additional items require interaction without crawlable fallback",
                expected="Lazy-loaded collections expose crawlable paginated URLs",
                evidence=f"initial_items={initial}; after_scroll_items={after}; pagination_fallback=false",
                source="Rendered DOM Snapshot"))
        images = int(page.get("lazy_images_without_fallback", 0) or 0)
        if images:
            findings.append(_finding(
                rule, url=page["url"],
                detected=f"{images} lazy images lack a static or noscript fallback",
                expected="Important lazy media has an indexable static fallback",
                evidence=f"lazy_images_without_fallback={images}",
                source="Rendered DOM Snapshot", severity="Warning"))
    raise PartialExecutionError(
        "Lazy-load behavior checked on a bounded sample; templates and interaction states outside the sample remain unproven",
        findings)


def check_availability_5xx_monitoring(rule: RuleDefinition, site_ctx: SiteContext,
                                      page_contexts: list[PageContext], data: dict) -> list[Finding]:
    snapshot = _source(data, "availability_snapshot", "Availability monitor")
    findings: list[Finding] = []
    endpoints = snapshot.get("endpoints", [])
    for endpoint in endpoints:
        url = endpoint["url"]
        five_xx = int(endpoint.get("five_xx_checks", 0) or 0)
        if five_xx:
            findings.append(_finding(
                rule, url=url, detected=f"{five_xx} monitored 5xx responses",
                expected="No unexplained 5xx responses in the monitoring window",
                evidence=f"total_checks={endpoint.get('total_checks')}; five_xx_checks={five_xx}",
                source="Availability Monitor"))
        availability = float(endpoint.get("availability_pct", 0) or 0)
        if availability < 99.9:
            findings.append(_finding(
                rule, url=url, detected=f"Availability was {availability:.3f}%",
                expected="Availability at or above 99.9%",
                evidence=f"failed_checks={endpoint.get('failed_checks')}; total_checks={endpoint.get('total_checks')}",
                source="Availability Monitor"))
        p95 = float(endpoint.get("p95_ms", 0) or 0)
        if p95 > 3000:
            findings.append(_finding(
                rule, url=url, detected=f"Monitored response-time p95 was {p95:.0f} ms",
                expected="Monitored p95 response time at or below 3000 ms",
                evidence=f"p95_ms={p95:.0f}", source="Availability Monitor",
                severity="Warning"))
    window = int(snapshot.get("window_hours", 0) or 0)
    min_locations = min((int(item.get("locations", 0) or 0) for item in endpoints), default=0)
    if window < 168 or min_locations < 2:
        raise PartialExecutionError(
            f"Monitoring evidence is partial: require at least 168 hours and 2 locations; got {window} hours and {min_locations} locations",
            findings)
    return findings
