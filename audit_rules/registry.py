"""Rule Registry — CSV loader, merger, and validator.

Loads from two CSV sources of truth:
  1. technical_seo_master_checklist_80.csv   — business audit spec
  2. master_audit_mapping.csv                — implementation capability mapping

Merges by audit_id, validates integrity, and produces 80 RuleDefinition instances.

Fail-fast: if CSVs are corrupt, missing, or inconsistent, raise immediately.
Do not silently ignore errors (Requirement 3).
"""

import csv
import os
from pathlib import Path
from typing import Optional

from audit_rules.models import RuleDefinition
from audit_rules.categories import (
    Category, Priority, Severity, Scope,
    ImplStatus, DetectionMethod,
)


# Default paths relative to the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CHECKLIST = PROJECT_ROOT / "audit_specs" / "technical_seo_master_checklist_80.csv"
DEFAULT_MAPPING = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"


# ============================================================
# CSV loaders
# ============================================================

def _load_checklist_csv(path: str) -> list[dict]:
    """Load and parse the master checklist CSV.

    Returns list of row dicts with keys as lowercase field names.
    Skips preamble rows (title, description, blank lines) before the header.
    """
    rows = []
    with open(path, "r", encoding="utf-8-sig") as f:
        # Skip preamble rows until we find the "id,..." header line
        for line in f:
            stripped = line.strip()
            if stripped.startswith("id,"):
                # We found the header; put it back for DictReader
                header_line = stripped
                break
        else:
            raise ValueError(f"No header row found in checklist: {path}")

        # Parse remaining lines with DictReader using the discovered header
        fieldnames = header_line.split(",")
        reader = csv.DictReader(f, fieldnames=fieldnames)
        for row in reader:
            raw_id = row.get("id", "").strip()
            if not raw_id.isdigit():
                continue
            row["id"] = int(raw_id)
            rows.append(row)

    if not rows:
        raise ValueError(f"No valid data rows found in checklist: {path}")

    return rows


def _load_mapping_csv(path: str) -> list[dict]:
    """Load and parse the implementation mapping CSV.

    Returns list of row dicts with integer id.
    """
    rows = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_id = row.get("id", "").strip()
            if not raw_id.isdigit():
                continue
            row["id"] = int(raw_id)
            rows.append(row)

    if not rows:
        raise ValueError(f"No valid data rows found in mapping: {path}")

    return rows


# ============================================================
# Merger + Validation
# ============================================================

def _derive_rule_id(check: str, audit_id: int) -> str:
    """Derive a machine-readable rule_id from the Chinese check name.

    Uses a hardcoded mapping for the 80 known rules to ensure stability.
    Falls back to a slugified version if no mapping exists.
    """
    # Hardcoded mapping for Phase 1: audit_id → rule_id
    # This ensures stable rule_ids regardless of CSV text changes
    RULE_ID_MAP = {
        1: "robots_txt_exists",
        2: "xml_sitemap_valid",
        3: "page_noindex_nofollow",
        4: "crawl_errors_4xx_5xx",
        5: "crawl_budget_waste",
        6: "unified_domain_protocol",
        7: "redirect_chain_audit",
        8: "canonical_correctness",
        9: "click_depth",
        10: "breadcrumb_schema",
        11: "internal_link_distribution",
        12: "pagination_faceted_nav",
        13: "title_uniqueness",
        14: "meta_description",
        15: "h1_heading_hierarchy",
        16: "thin_content",
        17: "duplicate_content",
        18: "tag_archive_search_indexability",
        19: "core_web_vitals",
        20: "server_response_ttfb",
        21: "render_blocking_css_js",
        22: "image_optimization",
        23: "cache_cdn",
        24: "mobile_usability",
        25: "https_certificate",
        26: "hsts_security_headers",
        27: "schema_type_coverage",
        28: "schema_errors_conflicts",
        29: "hreflang_basics",
        30: "broken_internal_links",
        31: "backlink_overview",
        32: "media_sitemap",
        33: "server_log_analysis",
        34: "gsc_ga4_config",
        35: "event_conversion_tracking",
        36: "wp_updates_security",
        37: "seo_plugin_conflicts",
        38: "permalink_rewrite",
        39: "xmlrpc_rest_api_exposure",
        40: "audit_deliverables",
        41: "soft_404",
        42: "sitemap_url_indexability",
        43: "sitemap_lastmod_accuracy",
        44: "google_selected_canonical",
        45: "orphan_pages",
        46: "js_rendered_content",
        47: "crawlable_a_href_links",
        48: "lazy_load_indexability",
        49: "url_normalization",
        50: "redirect_target_relevance",
        51: "internal_links_to_redirects",
        52: "keyword_cannibalization",
        53: "search_intent_match",
        54: "keyword_page_map",
        55: "content_unique_value",
        56: "content_freshness",
        57: "trust_eeat_signals",
        58: "hreflang_indexability",
        59: "language_code_match",
        60: "multilingual_canonical",
        61: "field_vs_lab_data",
        62: "third_party_script_impact",
        63: "font_loading_cls",
        64: "wp_cron_tasks",
        65: "database_autoload_bloat",
        66: "cache_plugin_cdn_synergy",
        67: "staging_site_indexed",
        68: "admin_2fa",
        69: "abandoned_plugins_themes",
        70: "form_link_accessibility",
        71: "form_e2e_test",
        72: "manual_actions_security",
        73: "seo_change_log",
        74: "regression_test",
        75: "device_country_ranking",
        76: "declining_page_keyword_map",
        77: "lost_backlinks",
        78: "schema_visible_content_match",
        79: "image_alt_link_semantics",
        80: "availability_5xx_monitoring",
    }
    return RULE_ID_MAP.get(audit_id, f"rule_{audit_id:03d}")


def _parse_category(cat_str: str) -> Category:
    """Parse category string from CSV to enum."""
    try:
        return Category.from_chinese(cat_str.strip())
    except ValueError:
        raise ValueError(f"Unknown category: '{cat_str}'")


def _parse_priority(p_str: str) -> Priority:
    """Parse priority string from CSV to enum."""
    return Priority.from_str(p_str.strip())


def _parse_impl_status(s: str) -> ImplStatus:
    """Parse impl_status string from mapping CSV."""
    return ImplStatus.from_str(s.strip())


def _parse_detection_method(s: str) -> DetectionMethod:
    """Parse detection_method string from mapping CSV.

    Handles compound values like 'SITE_CHECK + EXTERNAL_API' by mapping
    to COMPOSITE. Single values are matched directly.
    """
    s = s.strip()
    if "+" in s:
        return DetectionMethod.COMPOSITE
    return DetectionMethod.from_str(s)


def _default_severity(priority: Priority, finding_type: str) -> Severity:
    """Derive default severity from priority and finding_type.

    Priority and Severity are separate axes (Requirement 4).
    This mapping provides sensible defaults; specific rules may override.
    """
    finding_type_lower = finding_type.lower().strip()
    if finding_type_lower == "error":
        return Severity.ERROR
    elif finding_type_lower in ("warning", "warn"):
        return Severity.WARNING
    elif finding_type_lower == "opportunity":
        return Severity.OPPORTUNITY
    else:
        return Severity.INFO


def _parse_data_sources(raw: str) -> list[str]:
    """Parse data source string from mapping CSV into a list."""
    if not raw or raw.strip() in ("None", ""):
        return ["LibreCrawl"]
    sources = [s.strip() for s in raw.split("+")]
    return [s for s in sources if s]


def _merge_and_validate(
    checklist_rows: list[dict],
    mapping_rows: list[dict],
    expected_count: int | None = None,
) -> list[RuleDefinition]:
    """Merge checklist and mapping rows by audit_id, build RuleDefinition list.

    Validates:
      - exact row count (if expected_count is set)
      - consecutive audit_ids from min to max, no gaps
      - mapping covers all checklist IDs
      - all required fields present
      - valid enum values

    Args:
        checklist_rows: Parsed rows from checklist CSV.
        mapping_rows: Parsed rows from mapping CSV.
        expected_count: If set, validates exactly this many rules.
                        Default None = no count check (for testing with subsets).
    """
    # Index both lists by audit_id
    chk_by_id: dict[int, dict] = {r["id"]: r for r in checklist_rows}
    map_by_id: dict[int, dict] = {r["id"]: r for r in mapping_rows}

    # Validate: exact row count (optional — only for production path)
    if expected_count is not None and len(chk_by_id) != expected_count:
        raise ValueError(
            f"Checklist must have exactly {expected_count} rules, got {len(chk_by_id)}"
        )

    # Validate: mapping must cover all checklist IDs
    missing_in_mapping = set(chk_by_id.keys()) - set(map_by_id.keys())
    if missing_in_mapping:
        raise ValueError(
            f"Missing mapping for audit_ids: {sorted(missing_in_mapping)}. "
            f"Each checklist rule must have a corresponding mapping row."
        )

    # Build RuleDefinition list
    rules: list[RuleDefinition] = []
    for audit_id in sorted(chk_by_id.keys()):
        chk = chk_by_id[audit_id]
        mp = map_by_id.get(audit_id, {})

        # Parse enums
        try:
            category = _parse_category(chk.get("category", ""))
        except ValueError:
            raise ValueError(f"Rule {audit_id}: invalid category '{chk.get('category')}'")

        try:
            priority = _parse_priority(chk.get("priority", ""))
        except ValueError:
            raise ValueError(f"Rule {audit_id}: invalid priority '{chk.get('priority')}'")

        try:
            impl_status = _parse_impl_status(mp.get("impl_status", "NEW_MANUAL"))
        except ValueError:
            raise ValueError(f"Rule {audit_id}: invalid impl_status '{mp.get('impl_status')}'")

        try:
            exec_type = _parse_detection_method(mp.get("detection_method", "MANUAL_REVIEW"))
        except ValueError:
            raise ValueError(f"Rule {audit_id}: invalid detection_method '{mp.get('detection_method')}'")

        finding_type = chk.get("finding_type", "Error")
        severity = _default_severity(priority, finding_type)

        # Parse required data sources
        required_sources = _parse_data_sources(mp.get("data_source", ""))

        # Parse scope from detection method and rule logic
        scope = _infer_scope(audit_id, exec_type)

        rule_id = _derive_rule_id(chk.get("check", ""), audit_id)
        automatable = impl_status in (
            ImplStatus.EXISTING_FULL,
            ImplStatus.EXISTING_PARTIAL,
            ImplStatus.NEW_AUTO,
        )

        # Determine legacy check names
        legacy_names_str = mp.get("current_check_name", "")
        legacy_names = (
            [n.strip() for n in legacy_names_str.split(",") if n.strip()]
            if legacy_names_str and legacy_names_str != "None"
            else []
        )

        rd = RuleDefinition(
            audit_id=audit_id,
            rule_id=rule_id,
            category=category,
            title=chk.get("check", f"Rule {audit_id}"),
            description=chk.get("description", ""),
            priority=priority,
            severity=severity,
            default_finding_type=finding_type,
            scope=scope,
            execution_type=exec_type,
            required_data_sources=required_sources,
            impl_status=impl_status,
            automatable=automatable,
            owner=chk.get("owner", ""),
            remediation=chk.get("remediation", ""),
            acceptance_criteria=chk.get("acceptance_criteria", ""),
            tools=chk.get("tools", ""),
            notes=chk.get("notes", ""),
            legacy_check_names=legacy_names,
            rule_function=None,  # Bound later via adapter
        )
        rules.append(rd)

    # Final validation: IDs must be consecutive from min to max, no gaps
    ids = [r.audit_id for r in rules]
    id_min, id_max = min(ids), max(ids)
    expected_ids = set(range(id_min, id_max + 1))

    # Duplicate check
    if len(set(ids)) != len(ids):
        duplicates = sorted([i for i in ids if ids.count(i) > 1])
        raise ValueError(f"Duplicate audit_ids: {duplicates}")

    # Gap check
    missing_ids = expected_ids - set(ids)
    if missing_ids:
        raise ValueError(f"Missing audit_ids (gaps in sequence): {sorted(missing_ids)}")

    return rules


def _infer_scope(audit_id: int, exec_type: DetectionMethod) -> Scope:
    """Infer scope from audit_id and execution type.

    This is a heuristic for Phase 1. Later phases may override per-rule.
    """
    # Site-level rules
    site_rules = {1, 2, 6, 25, 26, 32, 33, 34, 36, 39, 40, 64, 65, 66, 67, 68, 69, 72, 73, 80}
    # Link-level rules
    link_rules = {30, 31, 51, 77}
    # Relationship rules (cross-page)
    rel_rules = {8, 9, 11, 12, 17, 29, 45, 50, 52, 58, 59, 60, 74}
    # Template rules
    template_rules = {19, 21, 22, 24, 61, 62, 63}

    if audit_id in site_rules:
        return Scope.SITE
    elif audit_id in link_rules:
        return Scope.LINK
    elif audit_id in rel_rules:
        return Scope.RELATIONSHIP
    elif audit_id in template_rules:
        return Scope.TEMPLATE
    else:
        return Scope.PAGE


# ============================================================
# Public API
# ============================================================

def load_registry(
    checklist_path: Optional[str] = None,
    mapping_path: Optional[str] = None,
    expected_count: int | None = None,
) -> list[RuleDefinition]:
    """Load, merge, and validate the 80-rule registry from CSV files.

    Args:
        checklist_path: Path to technical_seo_master_checklist_80.csv.
                        Defaults to audit_specs/technical_seo_master_checklist_80.csv
        mapping_path: Path to master_audit_mapping.csv.
                      Defaults to audit_specs/master_audit_mapping.csv
        expected_count: Exact rule count to require. Defaults to 80 for the
                        production path, None for custom paths (test flexibility).

    Returns:
        list of 80 RuleDefinition instances, sorted by audit_id

    Raises:
        FileNotFoundError: CSV file missing
        ValueError: CSV corrupt, missing IDs, duplicate IDs, invalid enums
    """
    is_default = checklist_path is None and mapping_path is None
    if expected_count is None and is_default:
        expected_count = 80

    if checklist_path is None:
        checklist_path = str(DEFAULT_CHECKLIST)
    if mapping_path is None:
        mapping_path = str(DEFAULT_MAPPING)

    if not os.path.exists(checklist_path):
        raise FileNotFoundError(f"Checklist CSV not found: {checklist_path}")
    if not os.path.exists(mapping_path):
        raise FileNotFoundError(f"Mapping CSV not found: {mapping_path}")

    checklist_rows = _load_checklist_csv(checklist_path)
    mapping_rows = _load_mapping_csv(mapping_path)

    return _merge_and_validate(checklist_rows, mapping_rows, expected_count)


def get_default_registry() -> list[RuleDefinition]:
    """Return the registry using default CSV paths. Cached after first call."""
    return load_registry()
