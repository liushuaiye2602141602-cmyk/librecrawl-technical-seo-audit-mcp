"""Shared PageSpeed Insights API client — single implementation, used by
both the existing MCP tools (server.py) and the V3 PageSpeedDataProvider.

CRITICAL: This is the ONLY module that makes HTTP requests to the PSI API.
No other file should duplicate the HTTP call logic.

Usage:
    from audit_rules.providers.psi_client import fetch_pagespeed

    result = fetch_pagespeed("https://example.com", strategy="mobile")
"""

from __future__ import annotations

import os
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────
PSI_API_BASE = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
PSI_CATEGORIES = ["performance", "seo", "accessibility", "best-practices"]
DEFAULT_TIMEOUT = 30


def _get_api_key() -> str:
    """Read PAGESPEED_API_KEY from environment."""
    return os.getenv("PAGESPEED_API_KEY", "")


def fetch_pagespeed(
    url: str,
    strategy: str = "mobile",
    api_key: str = "",
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """Fetch Core Web Vitals + Lighthouse data from Google PSI API.

    This is the single canonical PSI HTTP request implementation.
    Both server.py MCP tools and PageSpeedDataProvider use this function.

    Args:
        url: Full URL to test.
        strategy: "mobile" (default) or "desktop".
        api_key: PAGESPEED_API_KEY. If empty, reads from env.
        timeout: HTTP timeout in seconds.

    Returns:
        Dict with keys:
          - On success: url, strategy, scores, field_data_cwv, lab_data,
            top_opportunities, lighthouse_result (raw)
          - On error: {"error": str}
    """
    api_key = api_key or _get_api_key()
    if not api_key:
        return {"error": "PAGESPEED_API_KEY not set."}
    if strategy not in {"mobile", "desktop"}:
        return {"error": f"Invalid PSI strategy: {strategy}"}

    params = {
        "url": url,
        "key": api_key,
        "strategy": strategy,
        "category": PSI_CATEGORIES,
    }

    try:
        r = httpx.get(PSI_API_BASE, params=params, timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 429:
            return {"error": f"PSI rate limit exceeded (HTTP {status})"}
        if status == 400:
            return {"error": f"PSI bad request (HTTP {status})"}
        if status >= 500:
            return {"error": f"PSI server error (HTTP {status})"}
        return {"error": f"PSI HTTP error ({status})"}
    except httpx.TimeoutException:
        return {"error": f"PSI request timed out after {timeout}s"}
    except Exception as e:
        return {"error": f"PSI request failed ({type(e).__name__})"}

    if not isinstance(data, dict):
        return {"error": "PSI returned an invalid JSON object"}

    # ── Normalize response ───────────────────────────────────────────
    lhr = data.get("lighthouseResult", {})
    cats = lhr.get("categories", {})
    audits = lhr.get("audits", {})

    # Loading experience (field data)
    field_metrics = data.get("loadingExperience", {}).get("metrics", {})
    origin_field = data.get("originLoadingExperience", {})

    def _score(cat: str) -> int:
        return round((cats.get(cat, {}).get("score") or 0) * 100)

    def _ms(audit_id: str) -> Optional[int]:
        v = audits.get(audit_id, {}).get("numericValue")
        return round(v) if v is not None else None

    def _num(audit_id: str) -> Optional[float]:
        v = audits.get(audit_id, {}).get("numericValue")
        return v if v is not None else None

    # ── Field data (CrUX) ──────────────────────────────────────────
    field: dict[str, dict] = {}
    metric_map = [
        ("LCP", "LARGEST_CONTENTFUL_PAINT_MS"),
        ("FID", "FIRST_INPUT_DELAY_MS"),
        ("CLS", "CUMULATIVE_LAYOUT_SHIFT_SCORE"),
        ("INP", "INTERACTION_TO_NEXT_PAINT"),
        ("FCP", "FIRST_CONTENTFUL_PAINT_MS"),
        ("TTFB", "EXPERIMENTAL_TIME_TO_FIRST_BYTE"),
    ]
    for metric, key in metric_map:
        m = field_metrics.get(key, {})
        if m:
            field[metric] = {"value": m.get("percentile"), "category": m.get("category")}

    # Field data scope
    field_data_scope = "NONE"
    if data.get("loadingExperience", {}).get("id", ""):
        # URL-level data present
        field_data_scope = "URL"
    elif origin_field.get("metrics"):
        # Only origin-level data
        field_data_scope = "ORIGIN"

    # Origin-level field data
    origin_metrics: dict[str, dict] = {}
    origin_raw = origin_field.get("metrics", {})
    for metric, key in metric_map:
        m = origin_raw.get(key, {})
        if m:
            origin_metrics[metric] = {"value": m.get("percentile"), "category": m.get("category")}

    # ── Lab data (Lighthouse) ───────────────────────────────────────
    lab = {}
    for lab_key, audit_id, extractor in [
        ("FCP_ms", "first-contentful-paint", _ms),
        ("LCP_ms", "largest-contentful-paint", _ms),
        ("TBT_ms", "total-blocking-time", _ms),
        ("CLS", "cumulative-layout-shift", _num),
        ("Speed_Index_ms", "speed-index", _ms),
        ("TTI_ms", "interactive", _ms),
    ]:
        val = extractor(audit_id)
        if val is not None:
            lab[lab_key] = val

    # ── Opportunities ───────────────────────────────────────────────
    opportunities = []
    for audit_id, audit in audits.items():
        if audit.get("details", {}).get("type") == "opportunity":
            savings = audit.get("details", {}).get("overallSavingsMs", 0) or 0
            if savings > 200:
                opportunities.append({
                    "id": audit_id,
                    "title": audit.get("title", ""),
                    "description": audit.get("description", ""),
                    "savings_ms": round(savings),
                    "details": audit.get("details", {}),
                })
    opportunities.sort(key=lambda x: -x["savings_ms"])

    # ── Render-blocking resources ───────────────────────────────────
    render_blocking = []
    rb_audit = audits.get("render-blocking-resources", {})
    rb_details = rb_audit.get("details", {})
    rb_items = rb_details.get("items", []) if rb_details else []
    total_rb_savings = rb_audit.get("details", {}).get("overallSavingsMs", 0) or 0
    for item in rb_items:
        render_blocking.append({
            "url": item.get("url", ""),
            "resource_type": _classify_resource_type(item.get("url", "")),
            "transfer_size_bytes": item.get("transferSize", 0) or 0,
            "estimated_savings_ms": item.get("wastedMs", 0) or 0,
        })

    # ── Unused CSS/JS ───────────────────────────────────────────────
    unused_css_bytes = 0
    unused_css = audits.get("unused-css-rules", {})
    if unused_css:
        unused_css_bytes = unused_css.get("details", {}).get("overallSavingsBytes", 0) or 0

    unused_js_bytes = 0
    unused_js = audits.get("unused-javascript", {})
    if unused_js:
        unused_js_bytes = unused_js.get("details", {}).get("overallSavingsBytes", 0) or 0

    # ── Image optimization ──────────────────────────────────────────
    image_savings_bytes = 0
    oversized_count = 0
    for img_audit_id in ["modern-image-formats", "uses-optimized-images",
                          "offscreen-images", "uses-responsive-images"]:
        img_audit = audits.get(img_audit_id, {})
        img_savings = img_audit.get("details", {}).get("overallSavingsBytes", 0) or 0
        image_savings_bytes += img_savings
        if img_audit_id == "uses-optimized-images":
            items = img_audit.get("details", {}).get("items", []) or []
            oversized_count = len(items)

    # ── Third-party scripts ─────────────────────────────────────────
    third_party_raw = audits.get("third-party-summary", {})
    tp_details = third_party_raw.get("details", {})
    tp_items = tp_details.get("items", []) if tp_details else []
    tp_transfer = 0
    tp_main_thread = 0
    tp_entities = []
    for item in tp_items:
        entity = item.get("entity", {}) or {}
        tp_transfer += item.get("transferSize", 0) or 0
        tp_main_thread += item.get("mainThreadTime", 0) or 0
        tp_entities.append({
            "domain": entity.get("domains", [""])[0] if entity.get("domains") else "",
            "provider": entity.get("text", ""),
            "transfer_bytes": item.get("transferSize", 0) or 0,
            "main_thread_ms": round(item.get("mainThreadTime", 0) or 0),
            "blocking_time_ms": item.get("blockingTime", 0) or 0,
            "request_count": 0,  # PSI doesn't expose per-entity request count
        })

    # ── Font display / CLS ──────────────────────────────────────────
    font_issues = []
    font_audit = audits.get("font-display", {})
    font_details = font_audit.get("details", {})
    font_items = font_details.get("items", []) if font_details else []
    for item in font_items:
        font_issues.append({
            "url": item.get("url", ""),
            "issue": "missing_font_display",
            "detail": f"Font {item.get('url', '')} does not use font-display CSS",
        })

    # Layout shift elements
    layout_shift_audit = audits.get("layout-shifts", {})
    ls_details = layout_shift_audit.get("details", {})
    ls_items = ls_details.get("items", []) if ls_details else []
    layout_shifts = []
    for item in ls_items:
        layout_shifts.append({
            "node_label": item.get("node", {}).get("nodeLabel", "")
                          if item.get("node") else "",
            "cls_contribution": item.get("score", 0) or 0,
        })

    # ── Warnings ────────────────────────────────────────────────────
    run_warnings = [w for w in (lhr.get("runWarnings") or [])]

    return {
        "url": url,
        "strategy": strategy,
        "final_url": lhr.get("finalUrl", lhr.get("requestedUrl", url)),
        "scores": {
            "performance": _score("performance"),
            "seo": _score("seo"),
            "accessibility": _score("accessibility"),
            "best_practices": _score("best-practices"),
        },
        "field_data_cwv": field,
        "field_data_scope": field_data_scope,
        "origin_field_data": origin_metrics,
        "lab_data": lab,
        "top_opportunities": opportunities[:5],
        "render_blocking_resources": render_blocking,
        "render_blocking_savings_ms": total_rb_savings,
        "unused_css_bytes": unused_css_bytes,
        "unused_js_bytes": unused_js_bytes,
        "image_savings_bytes": image_savings_bytes,
        "oversized_image_count": oversized_count,
        "third_party_transfer_bytes": tp_transfer,
        "third_party_main_thread_ms": tp_main_thread,
        "third_party_entities": tp_entities,
        "font_issues": font_issues,
        "layout_shift_elements": layout_shifts,
        "run_warnings": run_warnings,
        "lighthouse_version": lhr.get("lighthouseVersion", ""),
        "lighthouse_result": lhr,  # Raw — for debug (only stored when flag on)
    }


def _classify_resource_type(url: str) -> str:
    """Classify a resource URL as CSS, JS, or Font based on extension."""
    lower = url.lower()
    if lower.endswith((".css", ".scss", ".less")):
        return "CSS"
    if lower.endswith((".js", ".mjs", ".cjs")):
        return "JS"
    if any(ext in lower for ext in (".woff", ".woff2", ".ttf", ".otf", ".eot")):
        return "Font"
    # Check for font in path
    if "font" in lower:
        return "Font"
    return "Other"
