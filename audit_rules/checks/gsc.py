"""Google Search Console backed audit checks."""

from __future__ import annotations

from collections import defaultdict

from audit_rules.adapters import DataUnavailableError, PartialExecutionError
from audit_rules.context import PageContext, SiteContext
from audit_rules.models import Finding, RuleDefinition


def _gsc(data: dict, family: str) -> dict:
    payload = data.get("gsc")
    if not isinstance(payload, dict):
        raise DataUnavailableError("GSC API evidence unavailable")
    if f"{family}:GSCAPIError" in (payload.get("errors") or []):
        raise DataUnavailableError(f"GSC API {family} unavailable")
    return payload


def _finding(rule: RuleDefinition, *, url: str, detected: str,
             expected: str, evidence: str, severity: str | None = None) -> Finding:
    return Finding(
        audit_id=rule.audit_id, rule_id=rule.rule_id, url=url,
        category=rule.category.value, priority=rule.priority.value,
        severity=severity or rule.severity.value,
        finding_type=rule.default_finding_type, scope=rule.scope.value,
        detected_value=detected, expected_value=expected, evidence=evidence,
        finding_detail=f"{detected}. {evidence}", remediation=rule.remediation,
        owner=rule.owner, acceptance_criteria=rule.acceptance_criteria,
        data_source="GSC API", confidence=1.0,
    )


def check_google_selected_canonical(rule: RuleDefinition, site_ctx: SiteContext,
                                    page_contexts: list[PageContext], data: dict) -> list[Finding]:
    payload = _gsc(data, "url_inspection")
    attempted = int(payload.get("inspection_attempted", 0) or 0)
    succeeded = int(payload.get("inspection_succeeded", 0) or 0)
    eligible = int(payload.get("inspection_eligible", attempted) or attempted)
    if attempted <= 0 or succeeded <= 0:
        raise DataUnavailableError("GSC URL Inspection evidence unavailable")

    findings: list[Finding] = []
    for page in page_contexts:
        inspection = (page.gsc_data or {}).get("inspection") or {}
        google = (inspection.get("googleCanonical") or "").rstrip("/")
        declared = (inspection.get("userCanonical") or page.canonical_url or "").rstrip("/")
        if google and declared and google != declared:
            findings.append(_finding(
                rule, url=page.url,
                detected=f"Google canonical: {inspection.get('googleCanonical')}",
                expected=f"Declared canonical: {inspection.get('userCanonical') or page.canonical_url}",
                evidence=f"verdict={inspection.get('verdict', 'UNKNOWN')}",
                severity="Error"))
    if succeeded < eligible:
        raise PartialExecutionError(
            f"GSC URL Inspection completed for {succeeded}/{eligible} eligible URLs",
            findings)
    return findings


def check_keyword_cannibalization(rule: RuleDefinition, site_ctx: SiteContext,
                                  page_contexts: list[PageContext], data: dict) -> list[Finding]:
    rows = _gsc(data, "search_analytics").get("current_rows")
    if not isinstance(rows, list):
        raise DataUnavailableError("GSC Search Analytics rows unavailable")
    pages_by_query: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in rows:
        query, page = str(row.get("query") or ""), str(row.get("page") or "")
        impressions = float(row.get("impressions", 0) or 0)
        if query and page and impressions >= 10:
            pages_by_query[query][page] += impressions
    findings: list[Finding] = []
    for query, pages in sorted(pages_by_query.items()):
        if len(pages) < 2:
            continue
        ordered = sorted(pages.items(), key=lambda item: (-item[1], item[0]))
        findings.append(_finding(
            rule, url=ordered[0][0],
            detected=f"{len(pages)} ranking pages for query '{query}'",
            expected="One primary landing page per search intent",
            evidence="; ".join(f"{url} ({impressions:g} impressions)" for url, impressions in ordered),
            severity="Error"))
    return findings


def _dimension_positions(rows: list[dict], dimension: str) -> dict[str, float]:
    totals: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for row in rows:
        key = str(row.get(dimension) or "")
        impressions = float(row.get("impressions", 0) or 0)
        position = float(row.get("position", 0) or 0)
        if key and impressions > 0 and position > 0:
            totals[key][0] += position * impressions
            totals[key][1] += impressions
    return {key: weighted / impressions for key, (weighted, impressions) in totals.items()
            if impressions >= 20}


def check_device_country_ranking(rule: RuleDefinition, site_ctx: SiteContext,
                                 page_contexts: list[PageContext], data: dict) -> list[Finding]:
    rows = _gsc(data, "search_analytics").get("current_rows")
    if not isinstance(rows, list):
        raise DataUnavailableError("GSC Search Analytics rows unavailable")
    findings: list[Finding] = []
    for dimension in ("device", "country"):
        positions = _dimension_positions(rows, dimension)
        if len(positions) < 2:
            continue
        best = min(positions.items(), key=lambda item: (item[1], item[0]))
        worst = max(positions.items(), key=lambda item: (item[1], item[0]))
        gap = worst[1] - best[1]
        if gap >= 3.0:
            findings.append(_finding(
                rule, url=site_ctx.base_url or "SITE",
                detected=f"{dimension} average-position gap: {gap:.1f}",
                expected=f"Comparable {dimension} performance (gap < 3 positions)",
                evidence=f"best={best[0]} ({best[1]:.1f}); worst={worst[0]} ({worst[1]:.1f})",
                severity="Opportunity"))
    return findings


def check_declining_page_keyword_map(rule: RuleDefinition, site_ctx: SiteContext,
                                     page_contexts: list[PageContext], data: dict) -> list[Finding]:
    payload = _gsc(data, "search_analytics")
    current = payload.get("current_rows")
    previous = payload.get("previous_rows")
    if not isinstance(current, list) or not isinstance(previous, list):
        raise DataUnavailableError("Comparable GSC Search Analytics windows unavailable")

    def aggregate(rows: list[dict]) -> dict[tuple[str, str], dict[str, float]]:
        result: dict[tuple[str, str], dict[str, float]] = defaultdict(
            lambda: {"clicks": 0.0, "impressions": 0.0})
        for row in rows:
            key = (str(row.get("page") or ""), str(row.get("query") or ""))
            if not all(key):
                continue
            result[key]["clicks"] += float(row.get("clicks", 0) or 0)
            result[key]["impressions"] += float(row.get("impressions", 0) or 0)
        return result

    current_map, previous_map = aggregate(current), aggregate(previous)
    findings: list[Finding] = []
    for (page, query), old in sorted(previous_map.items()):
        new = current_map.get((page, query), {"clicks": 0.0, "impressions": 0.0})
        old_clicks = old["clicks"]
        if old["impressions"] < 20 or old_clicks <= 0:
            continue
        decline = (old_clicks - new["clicks"]) / old_clicks
        if decline >= 0.30:
            findings.append(_finding(
                rule, url=page,
                detected=f"Query '{query}' clicks declined {decline * 100:.1f}%",
                expected="No unexplained >=30% click decline between comparable 28-day windows",
                evidence=f"previous_clicks={old_clicks:g}; current_clicks={new['clicks']:g}; "
                         f"previous_impressions={old['impressions']:g}; current_impressions={new['impressions']:g}",
                severity="Error"))
    return findings
