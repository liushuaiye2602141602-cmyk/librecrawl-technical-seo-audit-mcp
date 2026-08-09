"""Phase 3 — Performance CSV Artifact Writer.

Generates a performance.csv summary from PerformanceSnapshot cache.
One row per (URL, strategy) pair in the session cache.

This is an OUTPUT artifact, not a rule check — it is called after
all findings are collected, from _finalize_session().

Usage:
    from audit_rules.checks.performance_csv import generate_performance_csv
    csv_bytes = generate_performance_csv(psi_cache, strategy)
"""

from __future__ import annotations

import csv
import io
from typing import Optional


# Column order for performance.csv
_PERFORMANCE_COLUMNS = [
    "url",
    "strategy",
    "psi_status",
    "error",
    "field_data_scope",
    # Field metrics (CrUX)
    "field_lcp_ms",
    "field_lcp_category",
    "field_inp_ms",
    "field_inp_category",
    "field_cls",
    "field_cls_category",
    "field_ttfb_ms",
    "field_fcp_ms",
    # Origin field metrics
    "origin_field_lcp_ms",
    "origin_field_lcp_category",
    "origin_field_inp_ms",
    "origin_field_inp_category",
    "origin_field_cls",
    "origin_field_cls_category",
    # Lab scores (Lighthouse)
    "lab_performance_score",
    "lab_seo_score",
    "lab_accessibility_score",
    "lab_best_practices_score",
    # Lab metrics
    "lab_lcp_ms",
    "lab_fcp_ms",
    "lab_tbt_ms",
    "lab_cls",
    "lab_speed_index_ms",
    "lab_tti_ms",
    "lighthouse_version",
    # Opportunities
    "render_blocking_savings_ms",
    "render_blocking_count",
    "unused_css_bytes",
    "unused_js_bytes",
    "image_savings_bytes",
    "oversized_image_count",
    # Third-party
    "third_party_transfer_bytes",
    "third_party_main_thread_ms",
    "third_party_entity_count",
    # Font/CLS
    "font_display_issue_count",
    "layout_shift_element_count",
    "run_warnings",
]


def _snapshot_to_row(
    snap, strategy: str
) -> dict[str, str]:
    """Convert one PerformanceSnapshot to a CSV row dict.

    Args:
        snap: PerformanceSnapshot instance.
        strategy: The strategy used for this snapshot.

    Returns:
        Dict mapping column name to string value.
    """
    return {
        "url": snap.url or snap.requested_url or "",
        "strategy": snap.strategy or strategy,
        "psi_status": snap.psi_status or "",
        "error": snap.error or "",
        "field_data_scope": snap.field_data_scope or "NONE",
        # Field metrics
        "field_lcp_ms": f"{snap.field_lcp_ms:.0f}" if snap.field_lcp_ms is not None else "",
        "field_lcp_category": snap.field_lcp_category or "",
        "field_inp_ms": f"{snap.field_inp_ms:.0f}" if snap.field_inp_ms is not None else "",
        "field_inp_category": snap.field_inp_category or "",
        "field_cls": f"{snap.field_cls:.3f}" if snap.field_cls is not None else "",
        "field_cls_category": snap.field_cls_category or "",
        "field_ttfb_ms": f"{snap.field_ttfb_ms:.0f}" if snap.field_ttfb_ms is not None else "",
        "field_fcp_ms": f"{snap.field_fcp_ms:.0f}" if snap.field_fcp_ms is not None else "",
        # Origin field metrics
        "origin_field_lcp_ms": f"{snap.origin_field_lcp_ms:.0f}" if snap.origin_field_lcp_ms is not None else "",
        "origin_field_lcp_category": snap.origin_field_lcp_category or "",
        "origin_field_inp_ms": f"{snap.origin_field_inp_ms:.0f}" if snap.origin_field_inp_ms is not None else "",
        "origin_field_inp_category": snap.origin_field_inp_category or "",
        "origin_field_cls": f"{snap.origin_field_cls:.3f}" if snap.origin_field_cls is not None else "",
        "origin_field_cls_category": snap.origin_field_cls_category or "",
        # Lab scores
        "lab_performance_score": str(snap.lab_performance_score) if snap.lab_performance_score is not None else "",
        "lab_seo_score": str(snap.lab_seo_score) if snap.lab_seo_score is not None else "",
        "lab_accessibility_score": str(snap.lab_accessibility_score) if snap.lab_accessibility_score is not None else "",
        "lab_best_practices_score": str(snap.lab_best_practices_score) if snap.lab_best_practices_score is not None else "",
        # Lab metrics
        "lab_lcp_ms": f"{snap.lab_lcp_ms:.0f}" if snap.lab_lcp_ms is not None else "",
        "lab_fcp_ms": f"{snap.lab_fcp_ms:.0f}" if snap.lab_fcp_ms is not None else "",
        "lab_tbt_ms": f"{snap.lab_tbt_ms:.0f}" if snap.lab_tbt_ms is not None else "",
        "lab_cls": f"{snap.lab_cls:.3f}" if snap.lab_cls is not None else "",
        "lab_speed_index_ms": f"{snap.lab_speed_index_ms:.0f}" if snap.lab_speed_index_ms is not None else "",
        "lab_tti_ms": f"{snap.lab_tti_ms:.0f}" if snap.lab_tti_ms is not None else "",
        "lighthouse_version": snap.lighthouse_version or "",
        # Opportunities
        "render_blocking_savings_ms": str(snap.render_blocking_savings_ms),
        "render_blocking_count": str(len(snap.render_blocking_resources)),
        "unused_css_bytes": str(snap.unused_css_bytes),
        "unused_js_bytes": str(snap.unused_js_bytes),
        "image_savings_bytes": str(snap.image_savings_bytes),
        "oversized_image_count": str(snap.oversized_image_count),
        # Third-party
        "third_party_transfer_bytes": str(snap.third_party_transfer_bytes),
        "third_party_main_thread_ms": str(snap.third_party_main_thread_ms),
        "third_party_entity_count": str(len(snap.third_party_entities)),
        # Font/CLS
        "font_display_issue_count": str(len(snap.font_display_issues)),
        "layout_shift_element_count": str(len(snap.layout_shift_elements)),
        "run_warnings": "; ".join(snap.run_warnings) if snap.run_warnings else "",
    }


def generate_performance_csv(
    psi_cache: dict, strategy: str = "mobile"
) -> str:
    """Generate a performance.csv artifact from the PSI session cache.

    One row per (URL, strategy) pair. Each PerformanceSnapshot in the
    cache becomes one CSV row.

    Args:
        psi_cache: Dict of {(url, strategy): PerformanceSnapshot} from provider.
        strategy: Primary strategy used for the audit.

    Returns:
        CSV string content (UTF-8 with BOM).
    """
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=_PERFORMANCE_COLUMNS,
        extrasaction="ignore",
    )
    writer.writeheader()

    for (url, snap_strategy), snap in psi_cache.items():
        if isinstance(snap, dict):
            # Skip non-snapshot items (e.g., _provider ref)
            continue
        if not hasattr(snap, "url"):
            continue
        row = _snapshot_to_row(snap, snap_strategy)
        writer.writerow(row)

    return output.getvalue()
