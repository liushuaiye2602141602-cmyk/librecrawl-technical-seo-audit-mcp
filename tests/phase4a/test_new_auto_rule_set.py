"""Phase 4A — NEW_AUTO Rule Set Verification.

Programmatically verifies the NEW_AUTO rule set from the CSV source of truth.

Phase 4A target (8 rules):  {18, 32, 39, 43, 47, 51, 60, 67}
Phase 4B deferred (1 rule): {74}
"""

import csv
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

PHASE4A_RULE_IDS = {18, 32, 39, 43, 47, 51, 60, 67}
PHASE4B_RULE_IDS = {74}
ALL_NEW_AUTO_IDS = PHASE4A_RULE_IDS | PHASE4B_RULE_IDS


def _load_csv() -> dict[int, dict]:
    csv_path = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
    rows = {}
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            aid = row.get("id", "").strip()
            if aid.isdigit():
                rows[int(aid)] = row
    return rows


class TestNEWAUTORuleSet:
    """Verify the NEW_AUTO rule set matches expectations."""

    def test_new_auto_count_is_1(self):
        """CSV has exactly 1 NEW_AUTO rule (Rule 74, deferred to Phase 4B)."""
        rows = _load_csv()
        new_auto = {aid for aid, r in rows.items()
                    if r["impl_status"] == "NEW_AUTO"}
        assert len(new_auto) == 1, (
            f"Expected 1 NEW_AUTO (Rule 74), got {len(new_auto)}: {sorted(new_auto)}"
        )

    def test_new_auto_ids_match_expected(self):
        """NEW_AUTO IDs are exactly {74} (Phase 4B deferred only)."""
        rows = _load_csv()
        new_auto = {aid for aid, r in rows.items()
                    if r["impl_status"] == "NEW_AUTO"}
        assert new_auto == PHASE4B_RULE_IDS, (
            f"Mismatch: extra={new_auto - PHASE4B_RULE_IDS}, "
            f"missing={PHASE4B_RULE_IDS - new_auto}"
        )

    def test_phase4a_rules_now_existing_partial(self):
        """All 8 Phase 4A rules are now EXISTING_PARTIAL in CSV."""
        rows = _load_csv()
        for aid in sorted(PHASE4A_RULE_IDS):
            assert rows[aid]["impl_status"] == "EXISTING_PARTIAL", (
                f"Rule {aid} expected EXISTING_PARTIAL after Phase 4A migration, "
                f"got {rows[aid]['impl_status']}"
            )

    def test_phase4b_rule_74_is_new_auto(self):
        """Rule 74 is NEW_AUTO and deferred to Phase 4B."""
        rows = _load_csv()
        assert rows[74]["impl_status"] == "NEW_AUTO"

    def test_phase4a_and_phase4b_disjoint(self):
        """Phase 4A and 4B sets are disjoint."""
        assert PHASE4A_RULE_IDS.isdisjoint(PHASE4B_RULE_IDS)

    def test_phase4a_rules_no_longer_new_auto(self):
        """Phase 4A rules are no longer NEW_AUTO — they're EXISTING_PARTIAL."""
        rows = _load_csv()
        still_new_auto = {aid for aid in PHASE4A_RULE_IDS
                         if rows[aid]["impl_status"] == "NEW_AUTO"}
        assert not still_new_auto, (
            f"Phase 4A rules still NEW_AUTO: {still_new_auto}"
        )

    def test_no_phase4a_rules_excluded(self):
        """None of the 8 Phase 4A rules are missing from CSV."""
        rows = _load_csv()
        csv_ids = set(rows.keys())
        missing = PHASE4A_RULE_IDS - csv_ids
        assert not missing, f"Phase 4A IDs missing from CSV: {missing}"

    def test_phase4a_rule_descriptions(self):
        """Spot-check rule descriptions for Phase 4A rules."""
        rows = _load_csv()
        checks = {aid: rows[aid]["check"] for aid in PHASE4A_RULE_IDS}
        # All 8 rules should have non-empty check descriptions
        for aid, check in checks.items():
            assert check.strip(), f"Rule {aid} has empty check description"
        # All 8 should now have current_check_name populated
        for aid in PHASE4A_RULE_IDS:
            ccn = rows[aid].get("current_check_name", "").strip()
            assert ccn and ccn != "None", (
                f"Rule {aid} current_check_name not populated after Phase 4A"
            )
