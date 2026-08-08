"""Phase 2 — Local Check Implementations for EXISTING_PARTIAL Rules.

Each module in this package provides pure functions that implement
enhanced checks for previously partial rules using only existing
LibreCrawl export data.

Checks follow the adapter pattern:
    check_<rule>(rule, site_ctx, page_contexts, data) -> list[Finding]

Rules implemented:
    site_architecture.py  — Rules 12 (pagination), 38 (permalink), 49 (URL norm), 50 (redirect)
    content_metadata.py   — Rules 16 (thin content), 17 (near-duplicate)
    structured_data.py    — Rules 10 (breadcrumb), 28 (schema conflict), 78 (schema vs visible)
    media.py              — Rule 79 (image ALT quality)
    international.py      — Rule 59 (language/hreflang)
    wordpress.py          — Rule 37 (SEO plugin conflicts)
    form_accessibility.py — Rule 70 (form accessibility) — minimal
    audit_deliverables.py — Rule 40 (task CSV generation)
"""

# Lazy imports — modules are created incrementally during Phase 2 development.
# Each try/except allows the package to load even when not all modules exist yet.

def _lazy_import(module_name: str, names: list[str]) -> dict:
    """Import names from a submodule, returning None for missing modules."""
    try:
        mod = __import__(f"audit_rules.checks.{module_name}", fromlist=names)
        return {name: getattr(mod, name) for name in names}
    except (ImportError, AttributeError):
        return {name: None for name in names}


# These are eagerly populated by _import_all(); use ALIASES dict for safe access.
_IMPORTS: dict[str, object] = {}


def _import_all():
    """Populate _IMPORTS dict with available check functions."""
    global _IMPORTS
    modules = {
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
        "audit_deliverables": ["generate_task_csv"],
    }
    for mod, names in modules.items():
        _IMPORTS.update(_lazy_import(mod, names))


_import_all()


def get_check(name: str):
    """Get a check function by name, or None if not available."""
    return _IMPORTS.get(name)


__all__ = [
    "check_pagination", "check_permalink", "check_url_normalization",
    "check_redirect_relevance", "check_thin_content", "check_near_duplicate",
    "check_breadcrumb", "check_schema_conflict", "check_schema_vs_visible",
    "check_image_alt_quality", "check_language_hreflang_match",
    "check_seo_plugin_conflict", "check_form_accessibility", "generate_task_csv",
    "get_check",
]
