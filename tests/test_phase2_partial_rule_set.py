"""Phase 2 — EXISTING_PARTIAL Rule Set Verification.

Verifies that the CSV source of truth contains exactly the expected
54 EXISTING_PARTIAL Master Audit IDs after all external-provider migrations,
and that none of them are misclassified as EXISTING_FULL or other statuses.

EXPECTED:
  PARTIAL_RULE_IDS includes the four GSC-backed rules 44, 52, 75, and 76.
"""

import csv
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ============================================================
# Expected 54 EXISTING_PARTIAL IDs after all provider migrations
# ============================================================
PARTIAL_RULE_IDS = {
    2, 5, 10, 12, 13, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25,
    28, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 43, 44, 46, 47, 48, 49, 50, 51, 52, 59, 60, 61,
    62, 63, 64, 65, 66, 67, 68, 69, 70, 74, 75, 76, 77, 78, 79, 80,
}


class TestPartialRuleSet:
    """Verify the 54 EXISTING_PARTIAL rule set from CSV source of truth."""

    def test_csv_has_exactly_42_existing_partial(self):
        """CSV must contain exactly 54 EXISTING_PARTIAL rows."""
        mapping_path = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        assert mapping_path.exists(), f"Missing: {mapping_path}"

        partial_ids = []
        with open(mapping_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_id = row.get("id", "").strip()
                if not raw_id.isdigit():
                    continue
                if row.get("impl_status", "").strip() == "EXISTING_PARTIAL":
                    partial_ids.append(int(raw_id))

        assert len(partial_ids) == 54, (
            f"Expected 54 EXISTING_PARTIAL, got {len(partial_ids)}: {partial_ids}"
        )
        assert set(partial_ids) == PARTIAL_RULE_IDS, (
            f"CSV PARTIAL set mismatch:\n"
            f"  Extra (CSV only):   {set(partial_ids) - PARTIAL_RULE_IDS}\n"
            f"  Missing (from CSV): {PARTIAL_RULE_IDS - set(partial_ids)}"
        )

    def test_partial_rule_ids_fixed_cardinality(self):
        """The expected set must have exactly 54 unique IDs."""
        assert len(PARTIAL_RULE_IDS) == 54

    def test_no_partial_is_also_existing_full(self):
        """No rule can be both EXISTING_PARTIAL and EXISTING_FULL."""
        EXISTING_FULL_IDS = {
            1, 3, 4, 6, 7, 8, 9, 11, 14, 15, 26, 27, 29, 30, 41, 42, 45, 58,
        }
        overlap = PARTIAL_RULE_IDS & EXISTING_FULL_IDS
        assert not overlap, (
            f"Rules classified as both EXISTING_FULL and EXISTING_PARTIAL: {overlap}"
        )

    def test_no_partial_is_new_auto(self):
        """EXISTING_PARTIAL and NEW_AUTO are disjoint — verified from CSV."""
        import csv

        mapping_path = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        new_auto_ids = set()
        with open(mapping_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_id = row.get("id", "").strip()
                if not raw_id.isdigit():
                    continue
                if row.get("impl_status", "").strip() == "NEW_AUTO":
                    new_auto_ids.add(int(raw_id))

        overlap = PARTIAL_RULE_IDS & new_auto_ids
        assert not overlap, (
            f"Rules classified as both EXISTING_PARTIAL and NEW_AUTO: "
            f"{overlap}. Each rule must have exactly one classification."
        )

    def test_no_partial_is_new_external_data(self):
        """EXISTING_PARTIAL and NEW_EXTERNAL_DATA are disjoint — verified from CSV."""
        # Load actual NEW_EXTERNAL_DATA IDs from CSV (not hardcoded)
        import csv

        mapping_path = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        new_ext_ids = set()
        with open(mapping_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_id = row.get("id", "").strip()
                if not raw_id.isdigit():
                    continue
                if row.get("impl_status", "").strip() == "NEW_EXTERNAL_DATA":
                    new_ext_ids.add(int(raw_id))

        overlap = PARTIAL_RULE_IDS & new_ext_ids
        assert not overlap, (
            f"Rules classified as both EXISTING_PARTIAL and NEW_EXTERNAL_DATA: "
            f"{overlap}. Each rule must have exactly one classification."
        )

    def test_no_partial_is_new_manual(self):
        """EXISTING_PARTIAL and NEW_MANUAL are disjoint — verified from CSV."""
        import csv

        mapping_path = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        new_man_ids = set()
        with open(mapping_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_id = row.get("id", "").strip()
                if not raw_id.isdigit():
                    continue
                if row.get("impl_status", "").strip() == "NEW_MANUAL":
                    new_man_ids.add(int(raw_id))

        overlap = PARTIAL_RULE_IDS & new_man_ids
        assert not overlap, (
            f"Rules classified as both EXISTING_PARTIAL and NEW_MANUAL: "
            f"{overlap}. Each rule must have exactly one classification."
        )

    def test_all_80_covered_by_classification(self):
        """Every ID 1..80 belongs to exactly one classification (from CSV)."""
        import csv
        from collections import Counter

        mapping_path = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        seen = {}
        with open(mapping_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_id = row.get("id", "").strip()
                if not raw_id.isdigit():
                    continue
                audit_id = int(raw_id)
                impl = row.get("impl_status", "").strip()
                if audit_id in seen:
                    pytest.fail(
                        f"Duplicate audit_id {audit_id}: {seen[audit_id]} and {impl}"
                    )
                seen[audit_id] = impl

        assert set(seen.keys()) == set(range(1, 81)), (
            f"Not all 80 IDs covered. Missing: {set(range(1,81)) - set(seen.keys())}"
        )

        # Verify expected counts
        counts = Counter(seen.values())
        assert counts.get("EXISTING_FULL", 0) == 18
        assert counts.get("EXISTING_PARTIAL", 0) == 54
        assert counts.get("NEW_AUTO", 0) == 0
        assert counts.get("NEW_EXTERNAL_DATA", 0) == 0
        assert counts.get("NEW_MANUAL", 0) == 8
        assert sum(counts.values()) == 80

    def test_registry_matches_csv_partial_set(self):
        """The registry must have the same 54 EXISTING_PARTIAL IDs as CSV."""
        from audit_rules.registry import load_registry

        checklist = PROJECT_ROOT / "audit_specs" / "technical_seo_master_checklist_80.csv"
        mapping = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        if not checklist.exists() or not mapping.exists():
            pytest.skip("Real CSV files not found")

        registry = load_registry()
        registry_partial = {
            r.audit_id for r in registry if r.impl_status.value == "EXISTING_PARTIAL"
        }
        assert registry_partial == PARTIAL_RULE_IDS, (
            f"Registry PARTIAL mismatch:\n"
            f"  Extra: {registry_partial - PARTIAL_RULE_IDS}\n"
            f"  Missing: {PARTIAL_RULE_IDS - registry_partial}"
        )
