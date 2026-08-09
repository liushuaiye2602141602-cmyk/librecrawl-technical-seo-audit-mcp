"""PageContext and SiteContext — enriched data for rule evaluation.

Design (Requirement 6):
  - LIGHTWEIGHT fields: retained for ALL pages across the crawl lifecycle.
    These are small (~2KB per page) and support cross-page analysis.
  - HEAVY fields: lazy-loaded on demand, released after page-level rule
    evaluation. These are large (~5MB per page on large sites) and must
    never be pre-populated for all pages simultaneously.

Phase 1 (Requirement 7):
  - Uses EXISTING crawl export data ONLY. No HTTP re-fetch.
  - If data is not in the export, it stays None → NOT_CHECKED.
"""

from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class PageContext:
    """Per-page enriched context for rule evaluation.

    Populated from LibreCrawl's export data (30+ fields) in Phase 1.
    Heavy fields are lazy-loaded and released after evaluation.
    """

    # ============================================================
    # LIGHTWEIGHT FIELDS — retained for all pages
    # ============================================================

    url: str
    status_code: int = 0
    title: Optional[str] = None
    meta_description: Optional[str] = None
    h1: Optional[str] = None
    canonical_url: Optional[str] = None
    robots: Optional[str] = None            # meta robots content
    word_count: int = 0
    response_time_ms: int = 0
    depth: int = 0
    lang: Optional[str] = None
    viewport: Optional[str] = None
    charset: Optional[str] = None

    # Summaries (not the full raw data)
    image_summary: Optional[dict] = None    # {count, broken, missing_alt, oversized}
    hreflang_summary: Optional[list[dict]] = None  # [{lang, url}] — compact
    json_ld_types: Optional[list[str]] = None      # ["Organization", "BreadcrumbList", ...]

    # Link graph references (lightweight: url + metadata, not full HTML)
    links_detailed: Optional[list[dict]] = None   # [{url, anchor, is_internal, rel}]
    linked_from_count: int = 0
    internal_links_count: int = 0
    external_links_count: int = 0

    # Minhash for near-duplicate detection (32-bit, not full text)
    content_hash: Optional[str] = None

    # Original export data reference (for adapter compatibility)
    _raw_export: Optional[dict] = field(default=None, repr=False)

    # ============================================================
    # HEAVY FIELDS — lazy, bounded, released after page-level rules
    # ============================================================

    _body_html: Optional[str] = field(default=None, repr=False, init=False)
    _body_text: Optional[str] = field(default=None, repr=False, init=False)
    _response_headers: Optional[dict] = field(default=None, repr=False, init=False)
    _html_loaded: bool = field(default=False, repr=False, init=False)

    # ============================================================
    # External data providers (lazy, None = not available)
    # ============================================================

    pagespeed_data: Optional[dict] = None   # Phase 3+
    gsc_data: Optional[dict] = None         # Phase 5+

    # ============================================================
    # Heavy field lifecycle
    # ============================================================

    @property
    def body_html(self) -> Optional[str]:
        """Full HTML body — lazy-loaded from export data, NOT via HTTP."""
        if not self._html_loaded and self._raw_export is not None:
            self._load_heavy_from_export()
        return self._body_html

    @property
    def body_text(self) -> Optional[str]:
        """Stripped text content — lazy-loaded."""
        if not self._html_loaded and self._raw_export is not None:
            self._load_heavy_from_export()
        return self._body_text

    @property
    def response_headers(self) -> Optional[dict]:
        """HTTP response headers — lazy-loaded."""
        if not self._html_loaded and self._raw_export is not None:
            self._load_heavy_from_export()
        return self._response_headers

    def _load_heavy_from_export(self) -> None:
        """Extract heavy fields from raw LibreCrawl export data.

        Phase 1: LibreCrawl exports contain extractable data but not raw HTML.
        Heavy fields may remain None if the export doesn't include them.
        This is expected — the provider enriches what it can from existing data.
        """
        raw = self._raw_export or {}
        self._body_html = raw.get("body_html") or raw.get("html")
        self._body_text = raw.get("body_text") or raw.get("text")
        self._response_headers = raw.get("response_headers") or raw.get("headers")
        self._html_loaded = True

    def release_heavy(self) -> None:
        """Release heavy fields from memory after page-level evaluation."""
        self._body_html = None
        self._body_text = None
        self._response_headers = None
        self._html_loaded = False

    @classmethod
    def from_export(cls, page_dict: dict) -> "PageContext":
        """Create PageContext from a single LibreCrawl export page dict.

        Extracts lightweight fields eagerly. Heavy fields are lazy-loaded
        via _raw_export reference (NO copy — memory efficient).

        Args:
            page_dict: One dict from LibreCrawl's export (30+ keys per EXPORT_FIELDS).

        Returns:
            PageContext with lightweight fields populated and heavy fields lazy.
        """
        images = page_dict.get("images") or []
        image_summary = {
            "count": len(images),
            "broken": sum(1 for img in images if img.get("broken") or img.get("status", 0) >= 400) if images else 0,
            "missing_alt": sum(1 for img in images if not img.get("alt")) if images else 0,
        } if images else {"count": 0, "broken": 0, "missing_alt": 0}

        hreflang = page_dict.get("hreflang") or []
        hreflang_summary = [
            {"lang": h.get("lang", h.get("hreflang", "")), "url": h.get("url", h.get("href", ""))}
            for h in hreflang
        ] if isinstance(hreflang, list) else []

        json_ld = page_dict.get("json_ld") or page_dict.get("structured_data") or []
        if isinstance(json_ld, str):
            json_ld_types = ["parse_error"]
        elif isinstance(json_ld, list):
            json_ld_types = []
            for item in json_ld:
                if isinstance(item, dict):
                    t = item.get("@type", "Unknown")
                    json_ld_types.append(t)
        else:
            json_ld_types = []

        links = page_dict.get("links_detailed") or []
        if links:
            internal_count = sum(1 for l in links if l.get("is_internal", True))
            external_count = len(links) - internal_count
        else:
            # Current LibreCrawl production exports expose aggregate integer
            # counts even when the optional detailed link rows are unavailable.
            internal_count = int(page_dict.get("internal_links", 0) or 0)
            external_count = int(page_dict.get("external_links", 0) or 0)

        ctx = cls(
            url=page_dict.get("url", ""),
            status_code=int(page_dict.get("status_code", 0) or 0),
            title=page_dict.get("title"),
            meta_description=page_dict.get("meta_description"),
            h1=page_dict.get("h1"),
            canonical_url=page_dict.get("canonical_url"),
            robots=page_dict.get("robots"),
            word_count=int(page_dict.get("word_count", 0) or 0),
            response_time_ms=int(page_dict.get("response_time_ms", 0) or 0),
            depth=int(page_dict.get("depth", 0) or 0),
            lang=page_dict.get("lang"),
            viewport=page_dict.get("viewport"),
            charset=page_dict.get("charset"),
            image_summary=image_summary,
            hreflang_summary=hreflang_summary,
            json_ld_types=json_ld_types,
            links_detailed=links,
            linked_from_count=len(page_dict.get("linked_from") or []),
            internal_links_count=internal_count,
            external_links_count=external_count,
            _raw_export=page_dict,  # Reference, not copy — heavy fields loaded on demand
        )
        return ctx

    def __repr__(self) -> str:
        return f"PageContext(url={self.url!r}, status={self.status_code}, words={self.word_count})"


@dataclass
class SiteContext:
    """Site-level context for rule evaluation.

    Populated from site_data (robots.txt, sitemap, HTTPS/www redirect),
    sitemap reconciliation, and crawl completeness metrics.
    """

    base_url: str = ""

    # Site-level checks (from _site_check)
    robots_txt_found: bool = False
    robots_txt_disallow_count: int = 0
    robots_txt_has_sitemap_declaration: bool = False
    sitemap_found: bool = False
    sitemap_url: Optional[str] = None
    sitemap_url_count: int = 0
    https_redirects: bool = False
    www_redirects: bool = False

    # Crawl completeness
    pages_crawled: int = 0
    sitemap_total: int = 0
    sitemap_only_count: int = 0
    sitemap_coverage_pct: float = 0.0
    audit_complete: bool = False
    incomplete_reasons: str = ""

    # Site profile (for NOT_APPLICABLE determination)
    site_profile: str = "generic"  # "generic" / "wordpress" / "shopify" / etc.

    # Raw data references (for adapter compatibility)
    _site_data: Optional[dict] = field(default=None, repr=False)
    _sitemap_urls: Optional[list[str]] = field(default=None, repr=False)
    _robots_txt_content: Optional[str] = field(default=None, repr=False)

    @classmethod
    def from_site_check(cls, site_data: dict, base_url: str = "") -> "SiteContext":
        """Create SiteContext from _site_check() result."""
        robots = site_data.get("robots_txt", {}) or {}
        sitemap = site_data.get("sitemap", {}) or {}
        https = site_data.get("https_redirect", {}) or {}
        www = site_data.get("www_redirect", {}) or {}

        return cls(
            base_url=base_url,
            robots_txt_found=robots.get("found", False),
            robots_txt_disallow_count=robots.get("disallow_count", 0),
            robots_txt_has_sitemap_declaration=bool(robots.get("sitemap_url")),
            sitemap_found=sitemap.get("found", False),
            sitemap_url=sitemap.get("url"),
            sitemap_url_count=sitemap.get("url_count", 0),
            https_redirects=https.get(
                "redirects", https.get("http_redirects_to_https", False)
            ),
            www_redirects=www.get(
                "redirects",
                (not www["alt_redirects_properly"])
                if "alt_redirects_properly" in www else False,
            ),
            _site_data=site_data,
        )
