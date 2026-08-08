"""Phase 1+2+3 — Master Audit ID → Adapter Binding Verification.

Verifies that the 47 adapter rule_ids (18 P1 EXISTING_FULL + 13 P2 local
checks + 8 P3 performance + 8 P4A NEW_AUTO) in compatibility harness exactly
correspond to the approved Master Audit IDs, and that the mapping is consistent
across CSV source of truth, registry RULE_ID_MAP, and adapters.

Phase 1 (18):  {1,3,4,6,7,8,9,11,14,15,26,27,29,30,41,42,45,58}
Phase 2 (13):  {10,12,16,17,28,37,38,49,50,59,70,78,79}
Phase 3 (8):   {19,20,21,22,24,61,62,63}
Phase 4A (8):  {18,32,39,43,47,51,60,67}
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Approved Master Audit IDs — source of truth for this test
# ============================================================
EXISTING_FULL_MASTER_IDS = {
    1, 3, 4, 6, 7, 8, 9, 11, 14, 15, 26, 27, 29, 30, 41, 42, 45, 58,
}

# Expected rule_id for each Master Audit ID (from RULE_ID_MAP in registry.py)
MASTER_ID_RULE_ID_MAP = {
    1: "robots_txt_exists",
    3: "page_noindex_nofollow",
    4: "crawl_errors_4xx_5xx",
    6: "unified_domain_protocol",
    7: "redirect_chain_audit",
    8: "canonical_correctness",
    9: "click_depth",
    11: "internal_link_distribution",
    14: "meta_description",
    15: "h1_heading_hierarchy",
    26: "hsts_security_headers",
    27: "schema_type_coverage",
    29: "hreflang_basics",
    30: "broken_internal_links",
    41: "soft_404",
    42: "sitemap_url_indexability",
    45: "orphan_pages",
    58: "hreflang_indexability",
}

# Expected adapter function name for each Master Audit ID
MASTER_ID_ADAPTER_MAP = {
    # Phase 1 (18 EXISTING_FULL — adapter functions in adapters.py)
    1: "_adapter_robots_txt",
    3: "_adapter_noindex_nofollow",
    4: "_adapter_crawl_errors",
    6: "_adapter_domain_protocol",
    7: "_adapter_redirect_chains",
    8: "_adapter_canonical",
    9: "_adapter_click_depth",
    11: "_adapter_internal_links",
    14: "_adapter_meta_description",
    15: "_adapter_h1_headings",
    26: "_adapter_security_headers",
    27: "_adapter_schema_coverage",
    29: "_adapter_hreflang_basics",
    30: "_adapter_broken_links",
    41: "_adapter_soft_404",
    42: "_adapter_sitemap_indexability",
    45: "_adapter_orphan_pages",
    58: "_adapter_hreflang_indexability",
    # Phase 2 (13 local checks — functions in audit_rules.checks/)
    10: "check_breadcrumb",
    12: "check_pagination",
    16: "check_thin_content",
    17: "check_near_duplicate",
    28: "check_schema_conflict",
    37: "check_seo_plugin_conflict",
    38: "check_permalink",
    49: "check_url_normalization",
    50: "check_redirect_relevance",
    59: "check_language_hreflang_match",
    70: "check_form_accessibility",
    78: "check_schema_vs_visible",
    79: "check_image_alt_quality",
    # Phase 3 (8 performance checks — audit_rules.checks.performance)
    19: "check_core_web_vitals",
    20: "check_ttfb",
    21: "check_render_blocking",
    22: "check_image_performance",
    24: "check_mobile_experience",
    61: "check_field_vs_lab",
    62: "check_third_party_scripts",
    63: "check_font_cls",
    # Phase 4A (8 NEW_AUTO stateless checks — audit_rules.checks.phase4a_rules)
    18: "check_archive_search_indexability",
    32: "check_media_sitemap",
    39: "check_wordpress_api_exposure",
    43: "check_sitemap_lastmod",
    47: "check_crawlable_links",
    51: "check_internal_redirect_links",
    60: "check_multilang_canonical",
    67: "check_staging_indexability",
    # Phase 4B (portable snapshot comparison)
    74: "check_regression_test",
}


# ============================================================
# Test: CSV Source of Truth
# ============================================================

class TestCSVSourceOfTruth:
    """Verify the mapping CSV contains exactly 18 EXISTING_FULL rules."""

    def test_csv_has_exactly_18_existing_full(self):
        """The master_audit_mapping.csv must have exactly 18 EXISTING_FULL rows."""
        import csv

        mapping_path = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        assert mapping_path.exists(), f"Mapping CSV missing: {mapping_path}"

        existing_full_ids = []
        with open(mapping_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_id = row.get("id", "").strip()
                if not raw_id.isdigit():
                    continue
                if row.get("impl_status", "").strip() == "EXISTING_FULL":
                    existing_full_ids.append(int(raw_id))

        assert len(existing_full_ids) == 18, (
            f"Expected 18 EXISTING_FULL, got {len(existing_full_ids)}: {existing_full_ids}"
        )
        assert set(existing_full_ids) == EXISTING_FULL_MASTER_IDS, (
            f"Mismatch: extra={set(existing_full_ids) - EXISTING_FULL_MASTER_IDS}, "
            f"missing={EXISTING_FULL_MASTER_IDS - set(existing_full_ids)}"
        )

    def test_rule_2_is_existing_partial_not_full(self):
        """Rule 2 (XML Sitemap) must be EXISTING_PARTIAL, not EXISTING_FULL."""
        import csv

        mapping_path = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        with open(mapping_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("id", "").strip() == "2":
                    assert row.get("impl_status", "").strip() == "EXISTING_PARTIAL", (
                        "Rule 2 must be EXISTING_PARTIAL — sitemap detection alone "
                        "does not make the full Master Rule 2 EXISTING_FULL"
                    )
                    return
        pytest.fail("Rule 2 not found in mapping CSV")

    def test_rule_72_is_new_manual(self):
        """Rule 72 (Manual Actions) must be NEW_MANUAL, not NEW_EXTERNAL_DATA."""
        import csv

        mapping_path = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        with open(mapping_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("id", "").strip() == "72":
                    impl = row.get("impl_status", "").strip()
                    assert impl == "NEW_MANUAL", (
                        f"Rule 72 must be NEW_MANUAL (GSC API does not expose "
                        f"Manual Actions), got {impl}. Data source: "
                        f"{row.get('data_source', '').strip()}"
                    )
                    # Verify: data_source must reference GSC_UI, not GSC API
                    ds = row.get("data_source", "").strip()
                    assert "GSC_UI" in ds or "Manual" in ds, (
                        f"Rule 72 data_source must be GSC_UI or Manual, got '{ds}'"
                    )
                    return
        pytest.fail("Rule 72 not found in mapping CSV")

    def test_rule_55_is_new_manual_not_existing_full(self):
        """Rule 55 (Content Value) must not be EXISTING_FULL — requires human judgment."""
        import csv

        mapping_path = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        with open(mapping_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("id", "").strip() == "55":
                    impl = row.get("impl_status", "").strip()
                    assert impl == "NEW_MANUAL", (
                        f"Rule 55 must be NEW_MANUAL (content value requires human "
                        f"judgment), got {impl}"
                    )
                    return
        pytest.fail("Rule 55 not found in mapping CSV")


# ============================================================
# Test: Rule ID Mapping in Registry
# ============================================================

class TestRegistryRuleIDMapping:
    """Verify the RULE_ID_MAP in registry.py correctly maps Master Audit IDs."""

    def test_rule_id_map_matches_expected(self):
        """Every Master Audit ID → rule_id mapping must match."""
        from audit_rules.registry import _derive_rule_id

        for audit_id, expected_rule_id in MASTER_ID_RULE_ID_MAP.items():
            actual = _derive_rule_id("dummy check name", audit_id)
            assert actual == expected_rule_id, (
                f"Master ID {audit_id}: expected rule_id '{expected_rule_id}', "
                f"got '{actual}'"
            )

    def test_all_80_rule_ids_are_unique(self):
        """All 80 rule_ids in RULE_ID_MAP must be unique."""
        from audit_rules.registry import _derive_rule_id

        seen = set()
        for audit_id in range(1, 81):
            rule_id = _derive_rule_id("", audit_id)
            assert rule_id not in seen, f"Duplicate rule_id: '{rule_id}' (ID {audit_id})"
            seen.add(rule_id)


# ============================================================
# Test: Adapter Registration
# ============================================================

class TestAdapterRegistration:
    """Verify the CompatibilityHarness adapters match Master Audit IDs."""

    def test_all_18_adapters_match_master_ids(self):
        """Every adapter in the harness must correspond to an approved Master ID."""
        from audit_rules.adapters import CompatibilityHarness
        from audit_rules.registry import load_registry

        checklist = PROJECT_ROOT / "audit_specs" / "technical_seo_master_checklist_80.csv"
        mapping = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        if not checklist.exists() or not mapping.exists():
            pytest.skip("Real CSV files not found")

        registry = load_registry()
        harness = CompatibilityHarness(registry)

        # Expected set: 18 P1 + 13 P2 + 8 P3 + 8 P4A + 1 P4B = 48
        ALL_ADAPTER_MASTER_IDS = EXISTING_FULL_MASTER_IDS | {
            10, 12, 16, 17, 28, 37, 38, 49, 50, 59, 70, 78, 79,
        } | {
            19, 20, 21, 22, 24, 61, 62, 63,
        } | {
            18, 32, 39, 43, 47, 51, 60, 67,
        } | {
            74,
        }

        # Get all registered adapter rule_ids
        adapter_rule_ids = set(harness._adapters.keys())
        assert len(adapter_rule_ids) == 48, (
            f"Expected 48 adapters (18 P1 + 13 P2 + 8 P3 + 8 P4A + 1 P4B), "
            f"got {len(adapter_rule_ids)}: {adapter_rule_ids}"
        )

        # Map to Master Audit IDs by finding each rule_id in the registry
        rule_id_to_audit_id = {r.rule_id: r.audit_id for r in registry}
        adapted_master_ids = set()
        for rule_id in adapter_rule_ids:
            assert rule_id in rule_id_to_audit_id, (
                f"Adapter rule_id '{rule_id}' not found in registry"
            )
            adapted_master_ids.add(rule_id_to_audit_id[rule_id])

        assert adapted_master_ids == ALL_ADAPTER_MASTER_IDS, (
            f"Adapter Master ID mismatch:\n"
            f"  In harness, not in expected: {adapted_master_ids - ALL_ADAPTER_MASTER_IDS}\n"
            f"  Expected, not in harness: {ALL_ADAPTER_MASTER_IDS - adapted_master_ids}"
        )

    def test_registry_existing_full_matches_harness(self):
        """The registry's EXISTING_FULL rules must exactly match the harness."""
        from audit_rules.adapters import CompatibilityHarness
        from audit_rules.registry import load_registry

        checklist = PROJECT_ROOT / "audit_specs" / "technical_seo_master_checklist_80.csv"
        mapping = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        if not checklist.exists() or not mapping.exists():
            pytest.skip("Real CSV files not found")

        registry = load_registry()
        harness = CompatibilityHarness(registry)

        # Registry EXISTING_FULL rule_ids
        registry_full_ids = {
            r.audit_id for r in registry if r.impl_status.value == "EXISTING_FULL"
        }
        assert registry_full_ids == EXISTING_FULL_MASTER_IDS, (
            f"Registry EXISTING_FULL mismatch with expected Master IDs"
        )

        # Harness must have adapters for all EXISTING_FULL rules
        for r in registry:
            if r.impl_status.value == "EXISTING_FULL":
                assert r.rule_id in harness._adapters, (
                    f"Rule {r.audit_id} ({r.rule_id}) is EXISTING_FULL but "
                    f"has no adapter registered"
                )

    def test_each_adapter_is_unique_function(self):
        """No adapter function is reused for multiple rules — each is distinct."""
        from audit_rules.adapters import CompatibilityHarness
        from audit_rules.registry import load_registry

        checklist = PROJECT_ROOT / "audit_specs" / "technical_seo_master_checklist_80.csv"
        mapping = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        if not checklist.exists() or not mapping.exists():
            pytest.skip("Real CSV files not found")

        registry = load_registry()
        harness = CompatibilityHarness(registry)

        func_ids = {id(f) for f in harness._adapters.values()}
        assert len(func_ids) == 48, (
            f"Expected 48 unique adapter functions through Phase 4B, "
            f"got {len(func_ids)}"
        )

    def test_adapter_functions_match_expected_names(self):
        """Each adapter function name should match the expected mapping."""
        from audit_rules.adapters import CompatibilityHarness
        from audit_rules.registry import load_registry

        checklist = PROJECT_ROOT / "audit_specs" / "technical_seo_master_checklist_80.csv"
        mapping = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        if not checklist.exists() or not mapping.exists():
            pytest.skip("Real CSV files not found")

        registry = load_registry()
        harness = CompatibilityHarness(registry)

        rule_id_to_audit_id = {r.rule_id: r.audit_id for r in registry}
        for rule_id, func in harness._adapters.items():
            audit_id = rule_id_to_audit_id[rule_id]
            expected_func_name = MASTER_ID_ADAPTER_MAP.get(audit_id)
            assert expected_func_name is not None, (
                f"No expected adapter name for Master ID {audit_id}"
            )
            assert func.__name__ == expected_func_name, (
                f"Master ID {audit_id}: expected adapter '{expected_func_name}', "
                f"got '{func.__name__}'"
            )


# ============================================================
# Test: Classification Cross-Check
# ============================================================

class TestClassificationCrossCheck:
    """Verify impl_status counts are internally consistent."""

    def test_existing_full_count_is_exactly_18(self):
        """The registry must contain exactly 18 EXISTING_FULL rules."""
        from audit_rules.registry import load_registry

        checklist = PROJECT_ROOT / "audit_specs" / "technical_seo_master_checklist_80.csv"
        mapping = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        if not checklist.exists() or not mapping.exists():
            pytest.skip("Real CSV files not found")

        registry = load_registry()
        full = [r for r in registry if r.impl_status.value == "EXISTING_FULL"]
        assert len(full) == 18, (
            f"Registry EXISTING_FULL count: {len(full)} (expected 18)\n"
            f"IDs: {sorted(r.audit_id for r in full)}"
        )

    def test_all_classifications_sum_to_80(self):
        """All classification counts must sum to exactly 80."""
        from audit_rules.registry import load_registry

        checklist = PROJECT_ROOT / "audit_specs" / "technical_seo_master_checklist_80.csv"
        mapping = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        if not checklist.exists() or not mapping.exists():
            pytest.skip("Real CSV files not found")

        registry = load_registry()
        assert len(registry) == 80

        from collections import Counter
        counts = Counter(r.impl_status.value for r in registry)
        assert sum(counts.values()) == 80

    def test_classification_counts_match_expected_distribution(self):
        """Verify the post-Phase-4B implementation distribution totals 80."""
        from audit_rules.registry import load_registry
        from collections import Counter

        checklist = PROJECT_ROOT / "audit_specs" / "technical_seo_master_checklist_80.csv"
        mapping = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        if not checklist.exists() or not mapping.exists():
            pytest.skip("Real CSV files not found")

        registry = load_registry()
        counts = Counter(r.impl_status.value for r in registry)

        assert counts.get("EXISTING_FULL", 0) == 18
        assert counts.get("EXISTING_PARTIAL", 0) == 33
        assert counts.get("NEW_AUTO", 0) == 0
        assert counts.get("NEW_EXTERNAL_DATA", 0) == 16
        assert counts.get("NEW_MANUAL", 0) == 13
