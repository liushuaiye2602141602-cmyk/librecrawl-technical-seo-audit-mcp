"""Core Web Vitals thresholds — centralized, single source of truth.

Google-recommended thresholds (as of 2024). Used by all Phase 3 performance
rule checks (19, 61) and the PerformanceSnapshot classifier.

Imports should reference these constants — NEVER hardcode threshold values
in rule implementations.
"""

from dataclasses import dataclass


# ============================================================
# LCP (Largest Contentful Paint)
# ============================================================

LCP_GOOD_MS = 2500        # ≤ 2500 ms → Good
LCP_POOR_MS = 4000        # > 4000 ms → Poor
                           # 2500 < x ≤ 4000 → Needs Improvement

# ============================================================
# INP (Interaction to Next Paint) — replaces FID March 2024
# ============================================================

INP_GOOD_MS = 200         # ≤ 200 ms → Good
INP_POOR_MS = 500         # > 500 ms → Poor
                           # 200 < x ≤ 500 → Needs Improvement

# ============================================================
# CLS (Cumulative Layout Shift)
# ============================================================

CLS_GOOD = 0.1            # ≤ 0.10 → Good
CLS_POOR = 0.25           # > 0.25 → Poor
                           # 0.10 < x ≤ 0.25 → Needs Improvement

# ============================================================
# FCP (First Contentful Paint) — not a Core Web Vital, but useful
# ============================================================

FCP_GOOD_MS = 1800        # ≤ 1800 ms → Good
FCP_POOR_MS = 3000        # > 3000 ms → Poor

# ============================================================
# TBT (Total Blocking Time) — lab-only, not a CWV
# ============================================================

TBT_GOOD_MS = 200         # ≤ 200 ms → Good
TBT_POOR_MS = 600         # > 600 ms → Poor

# ============================================================
# Speed Index — lab-only
# ============================================================

SPEED_INDEX_GOOD_MS = 3400
SPEED_INDEX_POOR_MS = 5800

# ============================================================
# Lab Performance Score (Lighthouse 0-100)
# ============================================================

LAB_SCORE_GOOD = 90
LAB_SCORE_POOR = 50

# ============================================================
# Category helpers
# ============================================================

class CWVCategory:
    GOOD = "GOOD"
    NEEDS_IMPROVEMENT = "NEEDS_IMPROVEMENT"
    POOR = "POOR"


@dataclass(frozen=True)
class Threshold:
    good: float
    poor: float
    unit: str = "ms"


LCP_THRESHOLD = Threshold(good=LCP_GOOD_MS, poor=LCP_POOR_MS, unit="ms")
INP_THRESHOLD = Threshold(good=INP_GOOD_MS, poor=INP_POOR_MS, unit="ms")
CLS_THRESHOLD = Threshold(good=CLS_GOOD, poor=CLS_POOR, unit="")
FCP_THRESHOLD = Threshold(good=FCP_GOOD_MS, poor=FCP_POOR_MS, unit="ms")
TBT_THRESHOLD = Threshold(good=TBT_GOOD_MS, poor=TBT_POOR_MS, unit="ms")


def classify_metric(value: float | None, threshold: Threshold) -> CWVCategory | str:
    """Classify a metric value against its threshold.

    Returns:
        CWVCategory.GOOD / NEEDS_IMPROVEMENT / POOR, or "" if value is None.
    """
    if value is None:
        return ""
    if value <= threshold.good:
        return CWVCategory.GOOD
    if value > threshold.poor:
        return CWVCategory.POOR
    return CWVCategory.NEEDS_IMPROVEMENT


def classify_lcp(lcp_ms: float | None) -> CWVCategory | str:
    return classify_metric(lcp_ms, LCP_THRESHOLD)


def classify_inp(inp_ms: float | None) -> CWVCategory | str:
    return classify_metric(inp_ms, INP_THRESHOLD)


def classify_cls(cls_val: float | None) -> CWVCategory | str:
    return classify_metric(cls_val, CLS_THRESHOLD)


def classify_fcp(fcp_ms: float | None) -> CWVCategory | str:
    return classify_metric(fcp_ms, FCP_THRESHOLD)


def classify_tbt(tbt_ms: float | None) -> CWVCategory | str:
    return classify_metric(tbt_ms, TBT_THRESHOLD)


def classify_lab_score(score: float | None) -> CWVCategory | str:
    """Classify Lighthouse 0-100 performance score."""
    if score is None:
        return ""
    if score >= LAB_SCORE_GOOD:
        return CWVCategory.GOOD
    if score < LAB_SCORE_POOR:
        return CWVCategory.POOR
    return CWVCategory.NEEDS_IMPROVEMENT
