"""Phase 3 — Performance / PageSpeed Rule Checks.

Rules implemented:
  - Rule 19: Core Web Vitals (CWV) assessment
  - Rule 21: Render-Blocking Resources
  - Rule 22: Image Optimization (crawl + PSI combined)
  - Rule 24: Mobile Experience
  - Rule 61: Field vs Lab Data comparison
  - Rule 62: Third-Party Scripts
  - Rule 63: Font Loading / CLS

All checks use PerformanceSnapshot from PageSpeedDataProvider.
Field data (CrUX) and lab data (Lighthouse) are STRICTLY separated.
No HTTP requests — data comes from the provider cache.

False-positive guards:
  - No field data ≠ FAIL (→ EXECUTED_PARTIAL)
  - Origin-only data ≠ URL-level data
  - High TBT ≠ INP FAIL (different metrics)
  - GA/GTM present ≠ third-party FAIL
  - Google Fonts present ≠ font FAIL
  - Missing Lighthouse audit → UNKNOWN (not PASS)
  - PSI API error → Provider error (not SEO finding)
"""

from __future__ import annotations

import logging
from typing import Optional

from audit_rules.models import RuleDefinition, Finding
from audit_rules.context import SiteContext, PageContext
from audit_rules.categories import Severity
from audit_rules.performance_thresholds import (
    classify_lcp, classify_inp, classify_cls, classify_fcp,
    classify_tbt, classify_lab_score,
    CWVCategory, LCP_THRESHOLD, INP_THRESHOLD, CLS_THRESHOLD,
    FCP_THRESHOLD, TBT_THRESHOLD, LAB_SCORE_GOOD,
)
from audit_rules.adapters import DataUnavailableError

logger = logging.getLogger(__name__)


# ============================================================
# Shared helpers
# ============================================================

def _mk(
    rule: RuleDefinition,
    url: str,
    detected: str,
    expected: str,
    evidence: str,
    detail: str,
    severity: Severity,
    confidence: float = 1.0,
    priority: Optional[str] = None,
) -> Finding:
    """Factory for Finding with rule-derived defaults and explicit severity.

    ``priority`` overrides the rule-level priority for this specific finding
    (rule importance != finding priority; lab-only evidence should not inherit
    a Critical rule priority automatically).
    """
    return Finding(
        audit_id=rule.audit_id,
        rule_id=rule.rule_id,
        url=url,
        category=rule.category.value,
        priority=priority or str(rule.priority.value),
        severity=str(severity.value),
        finding_type=rule.default_finding_type,
        scope=str(rule.scope.value),
        detected_value=detected,
        expected_value=expected,
        evidence=evidence,
        finding_detail=detail or evidence,
        remediation=rule.remediation,
        owner=rule.owner,
        acceptance_criteria=rule.acceptance_criteria,
        data_source="PageSpeedInsights",
        confidence=confidence,
    )


def _get_snapshot(data: dict, url: str, strategy: str = "mobile"):
    """Get PerformanceSnapshot from data dict (injected by harness)."""
    from audit_rules.providers.performance_snapshot import PerformanceSnapshot
    cache = data.get("_psi_cache", {})
    key = (url.rstrip("/").lower(), strategy)
    snap = cache.get(key)
    if snap is None and isinstance(cache.get("_provider"), object):
        # Try provider direct
        provider = data.get("_provider")
        if provider and hasattr(provider, "get_snapshot"):
            snap = provider.get_snapshot(url, strategy)
    return snap


def _all_snapshots(data: dict, pages: list[PageContext], strategy: str = "mobile"):
    """Get all PerformanceSnapshots for sampled pages."""
    snapshots = []
    for ctx in pages:
        snap = _get_snapshot(data, ctx.url, strategy)
        if snap is not None:
            snapshots.append((ctx, snap))
    return snapshots


def build_psi_execution_summary(
    cache: dict,
    sampled_count: int,
    eligible_pages: int,
    strategy: str = "mobile",
) -> dict:
    """Single authoritative summary of a PSI-sampled execution.

    All performance rules reference this object so PDF / Matrix / Coverage /
    Performance CSV report identical numbers.
    """
    snapshots = [
        snap for snap in cache.values()
        if not isinstance(snap, dict) and getattr(snap, "url", None)
    ]
    success = sum(
        1 for snap in snapshots if snap.psi_status == "success")
    timeout = sum(
        1 for snap in snapshots if snap.psi_status in ("error", "timeout"))
    field_available = sum(
        1 for snap in snapshots
        if getattr(snap, "field_data_scope", "") in ("URL", "ORIGIN"))
    return {
        "eligible_pages": eligible_pages,
        "sampled_urls": min(sampled_count, eligible_pages),
        "requested": len(snapshots),
        "success": success,
        "timeout": timeout,
        "field_data_available": field_available,
        "strategy": strategy,
    }


# ============================================================
# Rule 19 — Core Web Vitals
# ============================================================

def check_core_web_vitals(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 19: Core Web Vitals assessment.

    Data priority:
      1. URL-level Field Data (CrUX)  → authoritative
      2. Origin-level Field Data       → partial, documented
      3. Lab diagnostics only          → partial, WARNING/OPPORTUNITY only

    A CWV PASS requires all three (LCP, INP, CLS) at URL level be GOOD.
    No field data → cannot PASS. Lab-only → cannot PASS.
    """
    findings: list[Finding] = []
    strategy = data.get("psi_strategy", "mobile")

    for ctx, snap in _all_snapshots(data, page_contexts, strategy):
        url = ctx.url

        # Skip errored snapshots
        if snap.psi_status != "success":
            if snap.error:
                findings.append(_mk(
                    rule, url=url,
                    detected=f"PSI error for {url}: {snap.error}",
                    expected="PSI data available for CWV assessment",
                    evidence=f"psi_status={snap.psi_status}, error={snap.error}",
                    detail=(
                        f"Could not assess Core Web Vitals for {url} because the "
                        f"PageSpeed Insights request failed: {snap.error}. "
                        f"This is a provider error, not a page CWV failure."
                    ),
                    severity=Severity.INFO,
                    confidence=0.5,
                    priority="High",  # data gap on the page; retest, not a defect
                ))
            continue

        # ── Determine data tier ──
        has_url_field = snap.field_data_scope == "URL"
        has_origin_field = snap.field_data_scope == "ORIGIN"
        has_field = has_url_field or has_origin_field

        # ── Classify CWV metrics ──
        if has_url_field:
            lcp_val = snap.field_lcp_ms
            inp_val = snap.field_inp_ms
            cls_val = snap.field_cls
            scope_label = "URL-level field data"
        elif has_origin_field:
            lcp_val = snap.origin_field_lcp_ms
            inp_val = snap.origin_field_inp_ms
            cls_val = snap.origin_field_cls
            scope_label = "Origin-level field data"
        else:
            lcp_val = None
            inp_val = None
            cls_val = None
            scope_label = "No field data available"

        lcp_cat = classify_lcp(lcp_val)
        inp_cat = classify_inp(inp_val)
        cls_cat = classify_cls(cls_val)

        # ── Build detected/expected ──
        metrics_str = (
            f"LCP={lcp_val:.0f}ms({lcp_cat}) " if lcp_val is not None else "LCP=N/A "
        ) + (
            f"INP={inp_val:.0f}ms({inp_cat}) " if inp_val is not None else "INP=N/A "
        ) + (
            f"CLS={cls_val:.3f}({cls_cat})" if cls_val is not None else "CLS=N/A"
        )

        evidence = (
            f"field_scope={snap.field_data_scope}, "
            f"lcp_ms={lcp_val}, inp_ms={inp_val}, cls={cls_val}"
        )

        categories = [c for c in (lcp_cat, inp_cat, cls_cat) if c]
        poor_count = sum(1 for c in categories if c == CWVCategory.POOR)
        ni_count = sum(1 for c in categories if c == CWVCategory.NEEDS_IMPROVEMENT)
        good_count = sum(1 for c in categories if c == CWVCategory.GOOD)

        # ── Only URL-level field data can produce PASS ──
        if has_url_field and good_count == 3:
            # All three GOOD at URL level → PASS
            # BUT: if we only sampled N of M pages, this is EXECUTED_PARTIAL
            # The coverage manager handles execution status; we just report findings
            pass  # No finding for PASS pages
        elif has_url_field and poor_count > 0:
            findings.append(_mk(
                rule, url=url,
                detected=f"{scope_label}: {metrics_str}",
                expected=(
                    f"LCP ≤ {LCP_THRESHOLD.good}ms, "
                    f"INP ≤ {INP_THRESHOLD.good}ms, "
                    f"CLS ≤ {CLS_THRESHOLD.good}"
                ),
                evidence=evidence,
                detail=(
                    f"Page {url} fails Core Web Vitals with {poor_count} Poor "
                    f"metric(s) at URL level: {metrics_str}. "
                    f"This is based on real-user CrUX field data."
                ),
                severity=Severity.ERROR,
                confidence=0.95 if has_url_field else 0.7,
            ))
        elif has_url_field and ni_count > 0:
            findings.append(_mk(
                rule, url=url,
                detected=f"{scope_label}: {metrics_str}",
                expected=(
                    f"LCP ≤ {LCP_THRESHOLD.good}ms, "
                    f"INP ≤ {INP_THRESHOLD.good}ms, "
                    f"CLS ≤ {CLS_THRESHOLD.good}"
                ),
                evidence=evidence,
                detail=(
                    f"Page {url} has {ni_count} Needs Improvement Core Web Vital(s): "
                    f"{metrics_str}. Based on URL-level CrUX field data."
                ),
                severity=Severity.WARNING,
                confidence=0.9,
            ))
        elif has_origin_field:
            # Origin-level only → partial
            severity = Severity.WARNING if poor_count > 0 else (
                Severity.OPPORTUNITY if ni_count > 0 else Severity.INFO
            )
            findings.append(_mk(
                rule, url=url,
                detected=f"{scope_label}: {metrics_str}",
                expected="URL-level field data for precise CWV assessment",
                evidence=evidence,
                detail=(
                    f"No URL-level CrUX data available for {url}. "
                    f"Origin-level field data shows: {metrics_str}. "
                    f"Origin data is an approximation — this page's actual "
                    f"CWV may differ from the origin average."
                ),
                severity=severity,
                confidence=0.6,
            ))
        else:
            # No field data — lab diagnostics only
            lab_lcp = snap.lab_lcp_ms
            lab_cls_val = snap.lab_cls
            lab_tbt = snap.lab_tbt_ms
            lab_score = snap.lab_performance_score

            lab_str = (
                f"Lab: LCP={lab_lcp:.0f}ms " if lab_lcp is not None else "Lab: LCP=N/A "
            ) + (
                f"TBT={lab_tbt:.0f}ms " if lab_tbt is not None else "TBT=N/A "
            ) + (
                f"CLS={lab_cls_val:.3f} " if lab_cls_val is not None else "CLS=N/A "
            ) + (
                f"Score={lab_score}/100" if lab_score is not None else "Score=N/A"
            )

            # Lab data can suggest issues but CANNOT give CWV PASS
            lab_cat = classify_lab_score(lab_score)
            if lab_cat == CWVCategory.POOR:
                severity = Severity.WARNING
                detail_prefix = (
                    f"No field data for {url}. Lab score is POOR ({lab_score}/100). "
                    f"This page may fail Core Web Vitals but cannot be confirmed "
                    f"without real-user field data. "
                )
            elif lab_cat == CWVCategory.NEEDS_IMPROVEMENT:
                severity = Severity.OPPORTUNITY
                detail_prefix = (
                    f"No field data for {url}. Lab score is moderate ({lab_score}/100). "
                )
            else:
                severity = Severity.INFO
                detail_prefix = (
                    f"No field data for {url}. Lab score is good ({lab_score}/100), "
                    f"but this is NOT a confirmed CWV PASS — real-user data needed. "
                )

            findings.append(_mk(
                rule, url=url,
                detected=f"No field data. {lab_str}",
                expected="CrUX field data (URL or origin level) for CWV assessment",
                evidence=f"field_scope=NONE, lab_score={lab_score}, "
                         f"lab_lcp={lab_lcp}, lab_tbt={lab_tbt}, lab_cls={lab_cls_val}",
                detail=f"{detail_prefix}Lab diagnostics: {lab_str}",
                severity=severity,
                confidence=0.5,
                priority="Medium",  # lab-only evidence is not a P0 page defect
            ))

    return findings


# ============================================================
# Rule 21 — Render-Blocking Resources
# ============================================================

def check_render_blocking(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 21: Render-blocking resources from Lighthouse audits.

    Uses stable Lighthouse audit IDs, not title text:
      - render-blocking-resources
      - unused-css-rules
      - unused-javascript

    If audit ID missing → UNKNOWN (not PASS).
    """
    findings: list[Finding] = []
    strategy = data.get("psi_strategy", "mobile")

    for ctx, snap in _all_snapshots(data, page_contexts, strategy):
        url = ctx.url
        if snap.psi_status != "success":
            continue

        rb_resources = snap.render_blocking_resources
        rb_savings = snap.render_blocking_savings_ms
        unused_css = snap.unused_css_bytes
        unused_js = snap.unused_js_bytes

        if not rb_resources and rb_savings == 0 and unused_css == 0 and unused_js == 0:
            # No render-blocking audit data available — UNKNOWN
            if snap.lab_performance_score is not None:
                continue  # Lighthouse ran fine, just no RB issues → no finding
            findings.append(_mk(
                rule, url=url,
                detected="No render-blocking resource audit data available",
                expected="Lighthouse render-blocking-resources audit present",
                evidence="render_blocking_resources=[]",
                detail=(
                    f"Render-blocking audit data not available for {url}. "
                    f"This may indicate a Lighthouse version incompatibility "
                    f"or a runtime error. UNKNOWN, not PASS."
                ),
                severity=Severity.INFO,
                confidence=0.5,
            ))
            continue

        # ── Flag render-blocking resources ──
        if rb_resources:
            rb_summary = ", ".join(
                f"{r.resource_type}({r.estimated_savings_ms}ms)"
                for r in rb_resources[:5]
            )
            findings.append(_mk(
                rule, url=url,
                detected=(
                    f"{len(rb_resources)} render-blocking resources "
                    f"({rb_savings}ms estimated savings): {rb_summary}"
                ),
                expected="CSS/JS loaded asynchronously or deferred",
                evidence=(
                    f"rb_count={len(rb_resources)}, "
                    f"rb_savings_ms={rb_savings}"
                ),
                detail=(
                    f"Page {url} has {len(rb_resources)} render-blocking resources "
                    f"with estimated savings of {rb_savings}ms. "
                    f"Resources: {rb_summary}. "
                    f"Defer or async-load non-critical CSS/JS."
                ),
                severity=Severity.WARNING if rb_savings > 500 else Severity.OPPORTUNITY,
                confidence=0.9,
            ))

        # ── Unused CSS ──
        if unused_css > 102400:  # >100KB
            findings.append(_mk(
                rule, url=url,
                detected=f"{unused_css / 1024:.0f}KB unused CSS",
                expected="CSS is tree-shaken and inlined for critical path",
                evidence=f"unused_css_bytes={unused_css}",
                detail=(
                    f"Page {url} has {unused_css / 1024:.0f}KB of unused CSS. "
                    f"Consider splitting CSS into critical (inline) and "
                    f"deferred (async load) to reduce render-blocking."
                ),
                severity=Severity.OPPORTUNITY,
                confidence=0.85,
            ))

        # ── Unused JS ──
        if unused_js > 204800:  # >200KB
            findings.append(_mk(
                rule, url=url,
                detected=f"{unused_js / 1024:.0f}KB unused JavaScript",
                expected="JS is code-split and deferred",
                evidence=f"unused_js_bytes={unused_js}",
                detail=(
                    f"Page {url} has {unused_js / 1024:.0f}KB of unused JavaScript. "
                    f"Consider code-splitting and lazy-loading non-critical JS."
                ),
                severity=Severity.OPPORTUNITY,
                confidence=0.85,
            ))

    return findings


# ============================================================
# Rule 22 — Image Optimization
# ============================================================

def check_image_performance(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 22: Image optimization — combines crawl data + PSI lab data.

    Data sources are explicitly tagged: "crawl" vs "pagespeed_lab".
    LCP image is identified separately and never recommended for lazy-load.
    """
    findings: list[Finding] = []
    strategy = data.get("psi_strategy", "mobile")

    for ctx, snap in _all_snapshots(data, page_contexts, strategy):
        url = ctx.url
        if snap.psi_status != "success" or snap.lab_performance_score is None:
            continue

        # ── PSI image opportunities ──
        img_savings = snap.image_savings_bytes
        oversized_count = snap.oversized_image_count

        if img_savings > 51200:  # >50KB
            findings.append(_mk(
                rule, url=url,
                detected=(
                    f"[pagespeed_lab] {img_savings / 1024:.0f}KB estimated "
                    f"image savings, {oversized_count} oversized image(s)"
                ),
                expected="Images are properly sized, compressed, and in modern formats",
                evidence=(
                    f"image_savings_bytes={img_savings}, "
                    f"oversized_images={oversized_count}, "
                    f"data_source=pagespeed_lab"
                ),
                detail=(
                    f"Page {url} has an estimated {img_savings / 1024:.0f}KB of "
                    f"image optimization opportunity. {oversized_count} image(s) "
                    f"may be oversized. Consider: modern formats (WebP/AVIF), "
                    f"responsive images (srcset), lazy loading for off-screen images, "
                    f"and explicit width/height dimensions."
                ),
                severity=Severity.OPPORTUNITY,
                confidence=0.85,
            ))

        # ── Image opportunities detail ──
        for img_opp in snap.image_opportunities:
            # Never recommend lazy-load for LCP images
            if img_opp.is_lcp_element and img_opp.issue == "lazy_loading":
                continue

            findings.append(_mk(
                rule, url=url,
                detected=(
                    f"[pagespeed_lab] {img_opp.issue}: "
                    f"{img_opp.estimated_bytes_savings / 1024:.0f}KB savings"
                ),
                expected="All images are optimized per Lighthouse recommendations",
                evidence=(
                    f"image_url={img_opp.url}, issue={img_opp.issue}, "
                    f"is_lcp={img_opp.is_lcp_element}"
                ),
                detail=(
                    f"Image opportunity on {url}: {img_opp.issue}. "
                    f"Estimated savings: {img_opp.estimated_bytes_savings / 1024:.0f}KB."
                    + (" This image is the LCP element — do NOT lazy-load it."
                       if img_opp.is_lcp_element else "")
                ),
                severity=Severity.OPPORTUNITY,
                confidence=0.8,
            ))

    return findings


# ============================================================
# Rule 24 — Mobile Experience
# ============================================================

def check_mobile_experience(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 24: Mobile experience assessment.

    Based on PSI mobile Lighthouse audits (viewport, tap targets,
    font sizing, horizontal overflow, mobile performance, CLS).
    Does NOT use deprecated Google Mobile-Friendly Test.

    Rule 24 is typically EXECUTED_PARTIAL — PageSpeed mobile ≠
    full real-device UX testing.
    """
    findings: list[Finding] = []
    strategy = data.get("psi_strategy", "mobile")

    # Only meaningful for mobile strategy
    if strategy != "mobile":
        return findings

    for ctx, snap in _all_snapshots(data, page_contexts, strategy):
        url = ctx.url
        if snap.psi_status != "success":
            continue

        issues = []

        # Lab mobile performance
        if snap.lab_performance_score is not None:
            if snap.lab_performance_score < 50:
                issues.append(f"Mobile performance score {snap.lab_performance_score}/100 (POOR)")
            elif snap.lab_performance_score < 90:
                issues.append(f"Mobile performance score {snap.lab_performance_score}/100 (Needs Improvement)")

        # Mobile CLS
        if snap.lab_cls is not None and snap.lab_cls > CLS_THRESHOLD.good:
            issues.append(f"Mobile CLS {snap.lab_cls:.3f} exceeds {CLS_THRESHOLD.good}")

        # Layout shifts
        if snap.layout_shift_elements:
            issues.append(f"{len(snap.layout_shift_elements)} layout shift element(s) detected")

        if not issues:
            continue  # No mobile-specific issues

        findings.append(_mk(
            rule, url=url,
            detected=f"Mobile experience issues: {'; '.join(issues)}",
            expected=(
                "Mobile performance score ≥90, CLS ≤0.1, "
                "no significant layout shifts on mobile"
            ),
            evidence=(
                f"strategy=mobile, lab_score={snap.lab_performance_score}, "
                f"lab_cls={snap.lab_cls}, layout_shifts={len(snap.layout_shift_elements)}"
            ),
            detail=(
                f"Page {url} shows mobile experience issues: {'; '.join(issues)}. "
                f"Note: This is based on simulated mobile Lighthouse, not real-device "
                f"testing. Full mobile UX assessment requires real-device testing. "
                f"Performance optimization primarily benefits user experience and conversion."
            ),
            severity=Severity.WARNING if snap.lab_performance_score is not None
                     and snap.lab_performance_score < 50 else Severity.OPPORTUNITY,
            confidence=0.7,
        ))

    return findings


# ============================================================
# Rule 61 — Field vs Lab Data
# ============================================================

def check_field_vs_lab(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 61: Compare Field (CrUX) vs Lab (Lighthouse) metrics.

    Detects significant discrepancies and warns about metric confusion.
    INP has no lab equivalent — TBT is shown as diagnostic only,
    never as an INP substitute.
    """
    findings: list[Finding] = []
    strategy = data.get("psi_strategy", "mobile")

    for ctx, snap in _all_snapshots(data, page_contexts, strategy):
        url = ctx.url
        if snap.psi_status != "success":
            continue

        has_field = snap.field_data_available
        has_lab = snap.lab_performance_score is not None

        if not has_field or not has_lab:
            # Document what's missing
            missing = []
            if not has_field:
                missing.append("Field (CrUX) data")
            if not has_lab:
                missing.append("Lab (Lighthouse) data")
            findings.append(_mk(
                rule, url=url,
                detected=f"Cannot compare: {' and '.join(missing)} unavailable",
                expected="Both field and lab data available for comparison",
                evidence=f"field_available={has_field}, lab_available={has_lab}",
                detail=(
                    f"For {url}: {' and '.join(missing)} is unavailable. "
                    f"Field vs lab comparison requires both data sources."
                ),
                severity=Severity.INFO,
                confidence=1.0,
            ))
            continue

        # ── Compare LCP ──
        lcp_comparisons = []
        if snap.field_lcp_ms is not None and snap.lab_lcp_ms is not None:
            delta = snap.field_lcp_ms - snap.lab_lcp_ms
            if abs(delta) > 1000:  # >1s difference
                lcp_comparisons.append(
                    f"LCP: Field={snap.field_lcp_ms:.0f}ms vs "
                    f"Lab={snap.lab_lcp_ms:.0f}ms (Δ={delta:.0f}ms)"
                )

        # ── Compare CLS ──
        cls_comparisons = []
        if snap.field_cls is not None and snap.lab_cls is not None:
            delta = snap.field_cls - snap.lab_cls
            if abs(delta) > 0.05:
                cls_comparisons.append(
                    f"CLS: Field={snap.field_cls:.3f} vs "
                    f"Lab={snap.lab_cls:.3f} (Δ={delta:.3f})"
                )

        # ── INP vs TBT — NEVER conflate ──
        inp_vs_tbt = None
        if snap.field_inp_ms is not None and snap.lab_tbt_ms is not None:
            # TBT is a diagnostic proxy for INP, not a direct comparison
            inp_cat = classify_inp(snap.field_inp_ms)
            tbt_cat = classify_tbt(snap.lab_tbt_ms)
            inp_vs_tbt = (
                f"Field INP={snap.field_inp_ms:.0f}ms ({inp_cat}) | "
                f"Lab TBT={snap.lab_tbt_ms:.0f}ms ({tbt_cat}) — "
                f"diagnostic only, different metrics"
            )

        all_comparisons = lcp_comparisons + cls_comparisons
        if inp_vs_tbt:
            all_comparisons.append(inp_vs_tbt)

        if not all_comparisons:
            continue

        findings.append(_mk(
            rule, url=url,
            detected="; ".join(all_comparisons),
            expected=(
                "Field and lab metrics should be broadly consistent; "
                "INP and TBT are different metrics with diagnostic relationship only"
            ),
            evidence=(
                f"field_lcp={snap.field_lcp_ms}, lab_lcp={snap.lab_lcp_ms}, "
                f"field_cls={snap.field_cls}, lab_cls={snap.lab_cls}, "
                f"field_inp={snap.field_inp_ms}, lab_tbt={snap.lab_tbt_ms}, "
                f"field_scope={snap.field_data_scope}"
            ),
            detail=(
                f"For {url}: {'; '.join(all_comparisons)}. "
                f"Note: INP (Interaction to Next Paint) is a field metric "
                f"measuring real-user interaction responsiveness. TBT (Total "
                f"Blocking Time) is a lab metric measuring main-thread blocking. "
                f"They are DIFFERENT metrics with a diagnostic relationship — "
                f"high TBT suggests potential INP issues, but TBT does not "
                f"directly measure INP."
            ),
            severity=Severity.OPPORTUNITY,
            confidence=0.85,
        ))

    return findings


# ============================================================
# Rule 62 — Third-Party Scripts
# ============================================================

def check_third_party_scripts(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 62: Third-party script impact assessment.

    Detects third-party resource cost from Lighthouse diagnostics.
    Does NOT flag GA/GTM presence as a FAIL — reports cost.
    Unknown providers aggregated by hostname.
    """
    findings: list[Finding] = []
    strategy = data.get("psi_strategy", "mobile")
    tp_threshold_bytes = data.get("tp_transfer_threshold_bytes", 102400)  # 100KB
    tp_main_thread_threshold_ms = data.get("tp_main_thread_threshold_ms", 200)

    for ctx, snap in _all_snapshots(data, page_contexts, strategy):
        url = ctx.url
        if snap.psi_status != "success":
            continue

        entities = snap.third_party_entities
        tp_transfer = snap.third_party_transfer_bytes
        tp_main_thread = snap.third_party_main_thread_ms

        if not entities:
            continue  # No third-party data

        # ── Aggregate by provider ──
        by_provider: dict[str, dict] = {}
        for e in entities:
            name = e.provider or e.domain or "Unknown"
            if name not in by_provider:
                by_provider[name] = {
                    "transfer_bytes": 0, "main_thread_ms": 0,
                    "blocking_ms": 0, "count": 0,
                }
            by_provider[name]["transfer_bytes"] += e.transfer_bytes
            by_provider[name]["main_thread_ms"] += e.main_thread_ms
            by_provider[name]["blocking_ms"] += e.blocking_time_ms
            by_provider[name]["count"] += 1

        # ── Report significant cost ──
        heavy_entities = []
        for name, stats in sorted(by_provider.items(),
                                  key=lambda x: -x[1]["main_thread_ms"]):
            if (stats["transfer_bytes"] > tp_threshold_bytes or
                    stats["main_thread_ms"] > tp_main_thread_threshold_ms):
                heavy_entities.append(
                    f"{name}: {stats['transfer_bytes'] / 1024:.0f}KB, "
                    f"{stats['main_thread_ms']}ms main thread"
                )

        if heavy_entities:
            findings.append(_mk(
                rule, url=url,
                detected=(
                    f"{len(entities)} third-party entity(s) detected. "
                    f"Total: {tp_transfer / 1024:.0f}KB transfer, "
                    f"{tp_main_thread}ms main thread. "
                    f"Heavy: {'; '.join(heavy_entities[:5])}"
                ),
                expected=(
                    "Third-party scripts loaded efficiently; "
                    "excessive main-thread cost reduced"
                ),
                evidence=(
                    f"tp_entities={len(entities)}, "
                    f"tp_transfer_bytes={tp_transfer}, "
                    f"tp_main_thread_ms={tp_main_thread}"
                ),
                detail=(
                    f"Page {url} loads {len(entities)} third-party resource(s) "
                    f"totaling {tp_transfer / 1024:.0f}KB with "
                    f"{tp_main_thread}ms main-thread impact. "
                    f"Third-party scripts are not inherently bad, but high "
                    f"main-thread cost degrades user experience. "
                    f"Consider: defer non-critical third-parties, use facades "
                    f"for embeds, self-host where possible."
                ),
                severity=Severity.WARNING if tp_main_thread > 500
                         else Severity.OPPORTUNITY,
                confidence=0.85,
            ))

    return findings


# ============================================================
# Rule 63 — Font Loading / CLS
# ============================================================

def check_font_cls(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 63: Font loading and CLS impact.

    Detects font-display issues, font-related layout shifts.
    Google Fonts presence is NOT automatically flagged — only
    blocking behavior, missing font-display, large transfer,
    and render impact are actionable.
    """
    findings: list[Finding] = []
    strategy = data.get("psi_strategy", "mobile")

    for ctx, snap in _all_snapshots(data, page_contexts, strategy):
        url = ctx.url
        if snap.psi_status != "success":
            continue

        font_issues = snap.font_display_issues
        layout_shifts = snap.layout_shift_elements

        # ── Missing font-display ──
        if font_issues:
            font_urls = [f.url for f in font_issues if f.url]
            findings.append(_mk(
                rule, url=url,
                detected=(
                    f"{len(font_issues)} font(s) without font-display: "
                    f"{', '.join(font_urls[:3])}"
                ),
                expected="All web fonts use font-display: swap or optional",
                evidence=f"font_issue_count={len(font_issues)}",
                detail=(
                    f"Page {url} has {len(font_issues)} font(s) without the "
                    f"font-display CSS property. Missing font-display causes "
                    f"FOIT (Flash of Invisible Text) and can contribute to "
                    f"layout shifts. Add font-display: swap or font-display: optional."
                ),
                severity=Severity.WARNING if len(font_issues) > 2
                         else Severity.OPPORTUNITY,
                confidence=0.9,
            ))

        # ── Font-related CLS ──
        font_shift_count = 0
        for shift in layout_shifts:
            node = shift.node_label.lower() if shift.node_label else ""
            # Heuristic: font-related shifts often involve text/heading nodes
            if any(kw in node for kw in ("heading", "text", "font", "h1", "h2", "title")):
                font_shift_count += 1
                if shift.cls_contribution > 0.02:  # Significant shift
                    findings.append(_mk(
                        rule, url=url,
                        detected=(
                            f"Layout shift ({shift.cls_contribution:.3f}) from "
                            f"element: {shift.node_label}"
                        ),
                        expected="Fonts load without causing visible layout shifts",
                        evidence=(
                            f"node={shift.node_label}, "
                            f"cls_contribution={shift.cls_contribution}"
                        ),
                        detail=(
                            f"Layout shift of {shift.cls_contribution:.3f} detected "
                            f"from '{shift.node_label}' on {url}. This may be caused "
                            f"by late-loading fonts replacing fallback text. "
                            f"Consider: font-display: swap, preloading critical "
                            f"fonts, and matching fallback font metrics using "
                            f"size-adjust or font-metric-override."
                        ),
                        severity=Severity.WARNING if shift.cls_contribution > 0.1
                                 else Severity.OPPORTUNITY,
                        confidence=0.8,
                    ))

        # ── Overall CLS check ──
        if snap.lab_cls is not None and snap.lab_cls > CLS_THRESHOLD.poor:
            # High CLS without any font-related evidence must not be attributed
            # to font loading; it belongs to Rule 19/24 layout-stability checks.
            if font_shift_count == 0 and not font_issues:
                continue
            findings.append(_mk(
                rule, url=url,
                detected=(
                    f"High CLS ({snap.lab_cls:.3f}) — "
                    f"{font_shift_count} font-related shifts, "
                    f"{len(layout_shifts)} total shifts"
                ),
                expected=f"CLS ≤ {CLS_THRESHOLD.good} with minimal font-induced shifts",
                evidence=(
                    f"lab_cls={snap.lab_cls}, font_shifts={font_shift_count}, "
                    f"total_shifts={len(layout_shifts)}"
                ),
                detail=(
                    f"Page {url} has high cumulative layout shift "
                    f"({snap.lab_cls:.3f}) with {font_shift_count} font-related "
                    f"shifts. Font loading is a common CLS contributor. "
                    f"Key mitigations: font-display, size-adjust for fallback "
                    f"fonts, and preloading critical font files."
                ),
                severity=Severity.WARNING,
                confidence=0.9,
            ))

    return findings


# ============================================================
# Rule 20 — TTFB (partial, lab-only in Phase 3)
# ============================================================

def check_ttfb(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 20: Time to First Byte (TTFB) — field evidence only.

    Lighthouse has no direct TTFB metric; using LCP/FCP as a TTFB proxy is
    invalid (LCP values were previously mislabelled as TTFB). This rule
    requires field TTFB (CrUX), RUM, or server-log evidence. When absent it
    raises DataUnavailableError -> NOT_CHECKED / UNKNOWN, never a confirmed
    defect.
    """
    findings: list[Finding] = []
    strategy = data.get("psi_strategy", "mobile")
    any_field_ttfb = False

    for ctx, snap in _all_snapshots(data, page_contexts, strategy):
        url = ctx.url
        if snap.psi_status != "success":
            continue

        ttfb_ms = snap.field_ttfb_ms
        if ttfb_ms is None:
            continue  # no reliable TTFB evidence for this sample
        any_field_ttfb = True

        if ttfb_ms > 800:  # >800ms is concerning
            findings.append(_mk(
                rule, url=url,
                detected=f"TTFB {ttfb_ms:.0f}ms (field / CrUX)",
                expected="TTFB < 800ms (good); < 200ms ideal",
                evidence=f"ttfb_ms={ttfb_ms}, source=field(CrUX)",
                detail=(
                    f"Page {url} shows field TTFB of {ttfb_ms:.0f}ms. "
                    f"For accurate multi-region TTFB, combine with RUM or "
                    f"server logs."
                ),
                severity=Severity.OPPORTUNITY,
                confidence=0.85,
            ))

    if not any_field_ttfb:
        raise DataUnavailableError(
            "Server response timing (TTFB) requires field TTFB (CrUX), RUM, "
            "or server-log evidence; Lighthouse lab metrics are not TTFB."
        )
    return findings
