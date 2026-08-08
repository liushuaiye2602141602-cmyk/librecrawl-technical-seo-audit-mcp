"""PerformanceSnapshot — unified model for PageSpeed/Lighthouse results.

One snapshot = one (URL, strategy) pair. All fields are Optional — PSI API
responses vary; missing keys must never cause crashes.

Design principles (Phase 3):
  - Field data (CrUX) and lab data (Lighthouse) are STRICTLY separated.
  - URL-level vs Origin-level field data scopes are explicit.
  - This model is provider-agnostic (wraps existing _fetch_psi output).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RenderBlockingResource:
    """A single render-blocking resource from Lighthouse audits."""
    url: str = ""
    resource_type: str = ""   # "CSS", "JS", "Font"
    transfer_size_bytes: int = 0
    estimated_savings_ms: int = 0


@dataclass
class ImageOpportunity:
    """Image optimization opportunity from PSI lab data."""
    url: str = ""
    issue: str = ""           # "oversized", "modern_format", "missing_dimensions",
                              # "lazy_loading", "srcset_missing"
    estimated_bytes_savings: int = 0
    is_lcp_element: bool = False


@dataclass
class ThirdPartyEntity:
    """Aggregated third-party script/resource entity."""
    domain: str = ""
    provider: str = ""        # "Google Analytics", "Meta", or hostname for unknown
    transfer_bytes: int = 0
    main_thread_ms: int = 0
    blocking_time_ms: int = 0
    request_count: int = 0


@dataclass
class FontIssue:
    """Font-related performance/CLS issue."""
    url: str = ""
    issue: str = ""           # "missing_font_display", "layout_shift",
                              # "large_transfer", "blocking"
    detail: str = ""


@dataclass
class LayoutShiftElement:
    """Element contributing to CLS."""
    node_label: str = ""      # Human-readable element description from LH
    cls_contribution: float = 0.0


@dataclass
class PerformanceSnapshot:
    """Complete performance snapshot for one (URL, strategy) pair.

    Wraps the output of _fetch_psi() (server.py:2287) into a structured
    model. All fields are Optional — missing data MUST NOT crash consumers.

    Field data vs Lab data:
      - Field (CrUX): real-user metrics — LCP, INP, CLS categories
      - Lab (Lighthouse): single-session simulated metrics — LCP, TBT, CLS, scores
    """

    # ── Identity ──────────────────────────────────────────────────────
    url: str = ""
    requested_url: str = ""
    final_url: str = ""       # Post-redirect URL, if different
    strategy: str = "mobile"  # "mobile" | "desktop"
    fetch_timestamp: str = "" # ISO-8601

    # ── Source ────────────────────────────────────────────────────────
    source: str = "pagespeed_insights"   # provider identifier

    # ── Field Data (CrUX) ─────────────────────────────────────────────
    field_data_available: bool = False
    field_data_scope: str = ""           # "URL" | "ORIGIN" | "NONE"

    # URL-level field metrics (from loadingExperience)
    field_lcp_ms: Optional[float] = None
    field_lcp_category: str = ""         # "FAST" | "AVERAGE" | "SLOW"
    field_inp_ms: Optional[float] = None
    field_inp_category: str = ""
    field_cls: Optional[float] = None
    field_cls_category: str = ""
    field_fcp_ms: Optional[float] = None
    field_fcp_category: str = ""
    field_ttfb_ms: Optional[float] = None
    field_ttfb_category: str = ""

    # Origin-level field metrics (from originLoadingExperience, if different)
    origin_field_lcp_ms: Optional[float] = None
    origin_field_lcp_category: str = ""
    origin_field_inp_ms: Optional[float] = None
    origin_field_inp_category: str = ""
    origin_field_cls: Optional[float] = None
    origin_field_cls_category: str = ""

    # ── Lab Data (Lighthouse) ─────────────────────────────────────────
    lab_performance_score: Optional[int] = None   # 0-100
    lab_seo_score: Optional[int] = None
    lab_accessibility_score: Optional[int] = None
    lab_best_practices_score: Optional[int] = None

    lab_lcp_ms: Optional[float] = None
    lab_fcp_ms: Optional[float] = None
    lab_tbt_ms: Optional[float] = None
    lab_cls: Optional[float] = None
    lab_speed_index_ms: Optional[float] = None
    lab_tti_ms: Optional[float] = None

    lighthouse_version: str = ""

    # ── Opportunities ─────────────────────────────────────────────────
    render_blocking_savings_ms: int = 0
    render_blocking_resources: list[RenderBlockingResource] = field(default_factory=list)

    unused_css_bytes: int = 0
    unused_js_bytes: int = 0

    image_savings_bytes: int = 0
    image_opportunities: list[ImageOpportunity] = field(default_factory=list)

    oversized_image_count: int = 0

    # ── Third-Party ───────────────────────────────────────────────────
    third_party_transfer_bytes: int = 0
    third_party_main_thread_ms: int = 0
    third_party_entities: list[ThirdPartyEntity] = field(default_factory=list)

    # ── Font / CLS ────────────────────────────────────────────────────
    font_display_issues: list[FontIssue] = field(default_factory=list)
    layout_shift_elements: list[LayoutShiftElement] = field(default_factory=list)

    # ── Diagnostics ───────────────────────────────────────────────────
    run_warnings: list[str] = field(default_factory=list)
    error: str = ""
    psi_status: str = ""      # "success" | "error" | "timeout" | "rate_limited" | "no_key"
