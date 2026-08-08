"""Phase 3.1 — Classification Integrity Verification.

Programmatically verifies that the 80-rule classification is consistent
across CSV source of truth, registry, and docs.

CRITICAL: impl_status in CSV reflects Master Rule acceptance criteria
coverage, NOT whether code exists. Having an adapter does NOT mean the
rule should be upgraded to EXISTING_FULL.

Tests:
  - 80 unique IDs, 1-80 coverage
  - Classification counts sum to exactly 80
  - No rule belongs to >1 classification
  - Phase 2 13 enhanced rules still classified correctly
  - Phase 3 8 enhanced rules still classified correctly
  - Adapter registration ≠ classification upgrade
"""

import csv
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Helpers
# ============================================================

def _load_csv_rows() -> dict[int, dict]:
    """Load all 80 rows from master_audit_mapping.csv."""
    mapping = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
    rows = {}
    with open(mapping, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            aid = row.get("id", "").strip()
            if not aid.isdigit():
                continue
            rows[int(aid)] = row
    return rows


def _load_registry():
    from audit_rules.registry import load_registry
    return load_registry()


# ============================================================
# Constants
# ============================================================

PHASE2_ENHANCED_IDS = {10, 12, 16, 17, 28, 37, 38, 49, 50, 59, 70, 78, 79}
PHASE3_ENHANCED_IDS = {19, 20, 21, 22, 24, 61, 62, 63}

VALID_STATUSES = {
    "EXISTING_FULL", "EXISTING_PARTIAL", "NEW_AUTO",
    "NEW_EXTERNAL_DATA", "NEW_MANUAL",
}


# ============================================================
# Tests
# ============================================================

class TestClassificationTotals:
    """Classification counts must sum to exactly 80."""

    def test_csv_has_80_rows(self):
        rows = _load_csv_rows()
        assert len(rows) == 80, f"CSV has {len(rows)} rows, expected 80"
        assert len(set(rows.keys())) == 80, "Duplicate audit_ids found"

    def test_all_ids_1_to_80_present(self):
        rows = _load_csv_rows()
        ids = set(rows.keys())
        expected = set(range(1, 81))
        missing = expected - ids
        extra = ids - expected
        assert not missing, f"Missing IDs: {sorted(missing)}"
        assert not extra, f"Extra IDs: {sorted(extra)}"

    def test_classification_counts_sum_to_80(self):
        rows = _load_csv_rows()
        from collections import Counter
        counts = Counter(r["impl_status"] for r in rows.values())
        total = sum(counts.values())
        assert total == 80, f"Classification total is {total}, expected 80"

    def test_csv_and_registry_match(self):
        rows = _load_csv_rows()
        registry = _load_registry()
        mismatches = []
        for aid in range(1, 81):
            csv_s = rows[aid]["impl_status"]
            reg_s = registry[aid - 1].impl_status.value
            if csv_s != reg_s:
                mismatches.append((aid, csv_s, reg_s))
        assert not mismatches, f"CSV/registry mismatches: {mismatches}"

    def test_no_invalid_statuses(self):
        rows = _load_csv_rows()
        for aid, r in rows.items():
            assert r["impl_status"] in VALID_STATUSES, (
                f"Rule {aid} has invalid status: {r['impl_status']}"
            )

    def test_each_rule_one_classification(self):
        """No rule appears in >1 classification bucket."""
        rows = _load_csv_rows()
        for aid, r in rows.items():
            s = r["impl_status"]
            # Simple check: each row has exactly one impl_status
            assert s, f"Rule {aid} has empty impl_status"


class TestPhase2EnhancedClassification:
    """Phase 2 13 enhanced rules: adapter exists, classification unchanged."""

    def test_phase2_rules_are_existing_partial(self):
        """All 13 Phase 2 rules are still EXISTING_PARTIAL in CSV."""
        rows = _load_csv_rows()
        for aid in sorted(PHASE2_ENHANCED_IDS):
            assert rows[aid]["impl_status"] == "EXISTING_PARTIAL", (
                f"Phase 2 rule {aid} has impl_status={rows[aid]['impl_status']}, "
                f"expected EXISTING_PARTIAL"
            )

    def test_phase2_rules_have_adapters(self):
        """All 13 Phase 2 rules have adapters registered."""
        from audit_rules.adapters import CompatibilityHarness
        registry = _load_registry()
        harness = CompatibilityHarness(registry)
        adapter_rule_ids = set(harness._adapters.keys())
        for aid in sorted(PHASE2_ENHANCED_IDS):
            rule = next(r for r in registry if r.audit_id == aid)
            assert rule.rule_id in adapter_rule_ids, (
                f"Phase 2 rule {aid} ({rule.rule_id}) has no adapter"
            )

    def test_adapter_does_not_mean_full(self):
        """Having an adapter does NOT mean EXISTING_FULL classification."""
        rows = _load_csv_rows()
        from audit_rules.adapters import CompatibilityHarness
        registry = _load_registry()
        harness = CompatibilityHarness(registry)
        adapter_rule_ids = set(harness._adapters.keys())

        for aid in sorted(PHASE2_ENHANCED_IDS):
            rule = next(r for r in registry if r.audit_id == aid)
            if rule.rule_id in adapter_rule_ids:
                # Adapter exists, but CSV should remain EXISTING_PARTIAL
                assert rows[aid]["impl_status"] != "EXISTING_FULL", (
                    f"Phase 2 rule {aid} has adapter but CSV says EXISTING_FULL — "
                    f"should remain EXISTING_PARTIAL unless Master acceptance "
                    f"criteria are 100% covered"
                )

    def test_phase2_rule_ids_still_in_registry(self):
        """Every Phase 2 rule ID must be in the registry."""
        registry = _load_registry()
        reg_ids = {r.audit_id for r in registry}
        missing = PHASE2_ENHANCED_IDS - reg_ids
        assert not missing, f"Phase 2 IDs missing from registry: {sorted(missing)}"


class TestPhase3EnhancedClassification:
    """Phase 3 8 rules: adapter exists, classification unchanged from CSV."""

    def test_phase3_rules_have_expected_csv_status(self):
        """Verify each Phase 3 rule's CSV impl_status."""
        rows = _load_csv_rows()
        expected = {
            19: "EXISTING_PARTIAL",
            20: "EXISTING_PARTIAL",
            21: "NEW_EXTERNAL_DATA",
            22: "EXISTING_PARTIAL",
            24: "NEW_EXTERNAL_DATA",
            61: "EXISTING_PARTIAL",
            62: "NEW_EXTERNAL_DATA",
            63: "NEW_EXTERNAL_DATA",
        }
        for aid, exp_status in expected.items():
            actual = rows[aid]["impl_status"]
            assert actual == exp_status, (
                f"Rule {aid}: expected {exp_status}, got {actual}"
            )

    def test_phase3_rules_have_adapters(self):
        """All 8 Phase 3 rules have adapters registered."""
        from audit_rules.adapters import CompatibilityHarness
        registry = _load_registry()
        harness = CompatibilityHarness(registry)
        adapter_rule_ids = set(harness._adapters.keys())
        for aid in sorted(PHASE3_ENHANCED_IDS):
            rule = next(r for r in registry if r.audit_id == aid)
            assert rule.rule_id in adapter_rule_ids, (
                f"Phase 3 rule {aid} ({rule.rule_id}) has no adapter"
            )

    def test_new_external_data_have_external_api_dependency(self):
        """Rules 21,24,62,63 must have data_source mentioning PageSpeed API."""
        rows = _load_csv_rows()
        for aid in [21, 24, 62, 63]:
            ds = rows[aid].get("data_source", "")
            assert "PageSpeed" in ds or "PSI" in ds, (
                f"Rule {aid} data_source='{ds}' must mention PageSpeed API"
            )

    def test_existing_partial_rules_have_remaining_gaps(self):
        """Rules 19,20,22,61 (EXISTING_PARTIAL) must have documented gaps."""
        rows = _load_csv_rows()
        for aid in [19, 20, 22, 61]:
            gap = rows[aid].get("gap_description", "")
            assert gap.strip(), (
                f"Rule {aid} EXISTING_PARTIAL must have gap_description"
            )


class TestClassificationSemantics:
    """impl_status vs execution coverage are different concepts."""

    def test_impl_status_is_not_execution_coverage(self):
        """CSV impl_status reflects Master acceptance criteria, not code existence.

        A rule can have:
          - impl_status = EXISTING_PARTIAL (CSV, design-time)
          - adapter registered (code exists)
          - execution_status = EXECUTED_PARTIAL (runtime, sampling)
        These are three different layers.
        """
        from audit_rules.adapters import CompatibilityHarness
        registry = _load_registry()
        harness = CompatibilityHarness(registry)

        # Rules with adapters but EXISTING_PARTIAL in CSV
        adapter_ids = set()
        for rule in registry:
            if rule.rule_id in harness._adapters:
                adapter_ids.add(rule.audit_id)

        rows = _load_csv_rows()
        partial_with_adapter = [
            aid for aid in adapter_ids
            if rows[aid]["impl_status"] == "EXISTING_PARTIAL"
        ]
        # Should have at least the 13 (P2) + 4 (P3 existing_partial) = 17
        assert len(partial_with_adapter) >= 17, (
            f"Expected ≥17 EXISTING_PARTIAL rules with adapters "
            f"(13 P2 + 4 P3), got {len(partial_with_adapter)}: {partial_with_adapter}"
        )


class TestAdapterClassificationIntegrity:
    """Adapters exist for 39 rules, but CSV classifications remain diverse."""

    def test_adapters_span_multiple_csv_classifications(self):
        """Adapters should span EXISTING_FULL, EXISTING_PARTIAL, and NEW_EXTERNAL_DATA."""
        from audit_rules.adapters import CompatibilityHarness
        registry = _load_registry()
        harness = CompatibilityHarness(registry)
        rows = _load_csv_rows()
        adapter_rule_ids = set(harness._adapters.keys())

        statuses = set()
        for rule in registry:
            if rule.rule_id in adapter_rule_ids:
                aid = rule.audit_id
                statuses.add(rows[aid]["impl_status"])

        assert "EXISTING_FULL" in statuses, "Adapters should cover EXISTING_FULL rules"
        assert "EXISTING_PARTIAL" in statuses, "Adapters should cover EXISTING_PARTIAL rules"
        assert "NEW_EXTERNAL_DATA" in statuses, "Adapters should cover NEW_EXTERNAL_DATA rules"

    def test_no_adapter_for_new_manual(self):
        """NEW_MANUAL rules should NOT have adapters (require human review)."""
        from audit_rules.adapters import CompatibilityHarness
        registry = _load_registry()
        harness = CompatibilityHarness(registry)
        rows = _load_csv_rows()
        adapter_rule_ids = set(harness._adapters.keys())

        for rule in registry:
            if rule.rule_id in adapter_rule_ids:
                aid = rule.audit_id
                assert rows[aid]["impl_status"] != "NEW_MANUAL", (
                    f"Rule {aid} ({rule.rule_id}) is NEW_MANUAL but has adapter"
                )
