"""Phase 2+3 — Local Check Implementations for EXISTING_PARTIAL and
NEW_EXTERNAL_DATA Rules.

Phase 2 (13 checks, crawl-only data):
    site_architecture.py  — Rules 12 (pagination), 38 (permalink), 49 (URL norm), 50 (redirect)
    content_metadata.py   — Rules 16 (thin content), 17 (near-duplicate)
    structured_data.py    — Rules 10 (breadcrumb), 28 (schema conflict), 78 (schema vs visible)
    media.py              — Rule 79 (image ALT quality)
    international.py      — Rule 59 (language/hreflang)
    wordpress.py          — Rule 37 (SEO plugin conflicts)
    form_accessibility.py — Rule 70 (form accessibility) — minimal
    audit_deliverables.py — Rule 40 (task CSV generation)

Phase 3 (8 checks, PageSpeed Insights data):
    performance.py        — Rules 19 (CWV), 20 (TTFB), 21 (render-blocking),
                             22 (image optimization), 24 (mobile experience),
                             61 (field vs lab), 62 (third-party scripts),
                             63 (font loading/CLS)

Phase 4A (8 checks, NEW_AUTO stateless rules, crawl data only):
    phase4a_rules.py      — Rules 18 (archive/search indexability),
                             32 (media sitemap),
                             39 (WordPress XML-RPC/REST API exposure),
                             43 (sitemap lastmod accuracy),
                             47 (crawlable <a href> links),
                             51 (internal links → redirect URLs),
                             60 (multi-language canonical),
                             67 (staging/dev indexability)

Phase 4B (1 check, portable crawl comparison):
    snapshot_diff.py       — Rule 74 (before/after regression test)

Checks follow the adapter pattern:
    check_<rule>(rule, site_ctx, page_contexts, data) -> list[Finding]
"""

# Lazy imports — modules are created incrementally during Phase 2/3 development.
# Each try/except allows the package to load even when not all modules exist yet.

def _lazy_import(module_name: str, names: list[str]) -> dict:
    """Import names from a submodule, returning None for missing modules."""
    try:
        mod = __import__(f"audit_rules.checks.{module_name}", fromlist=names)
        return {name: getattr(mod, name) for name in names}
    except (ImportError, AttributeError):
        return {name: None for name in names}


# These are eagerly populated by _import_all(); use get_check() for safe access.
_IMPORTS: dict[str, object] = {}


def _import_all():
    """Populate _IMPORTS dict with available check functions."""
    global _IMPORTS
    modules = {
        # Phase 2
        "site_architecture": [
            "check_pagination", "check_permalink",
            "check_url_normalization", "check_redirect_relevance",
        ],
        "content_metadata": [
            "check_thin_content", "check_near_duplicate",
        ],
        "structured_data": [
            "check_breadcrumb", "check_schema_conflict", "check_schema_vs_visible",
        ],
        "media": ["check_image_alt_quality"],
        "international": ["check_language_hreflang_match"],
        "wordpress": ["check_seo_plugin_conflict"],
        "form_accessibility": ["check_form_accessibility"],
        "audit_deliverables": ["generate_task_csv", "check_audit_deliverables"],
        # Phase 4C — previously unbound EXISTING_PARTIAL rules
        "foundation_gaps": [
            "check_xml_sitemap_valid",
            "check_crawl_budget_waste",
            "check_title_uniqueness",
            "check_cache_cdn",
            "check_https_certificate",
            "check_cache_plugin_cdn_synergy",
        ],
        # Phase 3
        "performance": [
            "check_core_web_vitals",
            "check_ttfb",
            "check_render_blocking",
            "check_image_performance",
            "check_mobile_experience",
            "check_field_vs_lab",
            "check_third_party_scripts",
            "check_font_cls",
        ],
        # Phase 4A
        "phase4a_rules": [
            "check_archive_search_indexability",
            "check_media_sitemap",
            "check_wordpress_api_exposure",
            "check_sitemap_lastmod",
            "check_crawlable_links",
            "check_internal_redirect_links",
            "check_multilang_canonical",
            "check_staging_indexability",
        ],
        # Phase 4B
        "snapshot_diff": ["check_regression_test"],
    }
    for mod, names in modules.items():
        _IMPORTS.update(_lazy_import(mod, names))


_import_all()


def get_check(name: str):
    """Get a check function by name, or None if not available."""
    return _IMPORTS.get(name)


__all__ = [
    # Phase 2
    "check_pagination", "check_permalink", "check_url_normalization",
    "check_redirect_relevance", "check_thin_content", "check_near_duplicate",
    "check_breadcrumb", "check_schema_conflict", "check_schema_vs_visible",
    "check_image_alt_quality", "check_language_hreflang_match",
    "check_seo_plugin_conflict", "check_form_accessibility", "generate_task_csv",
    "check_audit_deliverables",
    # Phase 4C
    "check_xml_sitemap_valid", "check_crawl_budget_waste",
    "check_title_uniqueness", "check_cache_cdn",
    "check_https_certificate", "check_cache_plugin_cdn_synergy",
    # Phase 3
    "check_core_web_vitals", "check_ttfb", "check_render_blocking",
    "check_image_performance", "check_mobile_experience",
    "check_field_vs_lab", "check_third_party_scripts", "check_font_cls",
    # Phase 4A
    "check_archive_search_indexability",
    "check_media_sitemap",
    "check_wordpress_api_exposure",
    "check_sitemap_lastmod",
    "check_crawlable_links",
    "check_internal_redirect_links",
    "check_multilang_canonical",
    "check_staging_indexability",
    # Phase 4B
    "check_regression_test",
    "get_check",
]
