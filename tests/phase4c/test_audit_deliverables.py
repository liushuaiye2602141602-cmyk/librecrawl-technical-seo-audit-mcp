"""Rule 40 actionable task artifact contract."""

from __future__ import annotations

import csv
import io

import pytest

from audit_rules.context import PageContext, SiteContext
from audit_rules.models import Finding


def _finding(*, detail: str = "Fix the canonical") -> Finding:
    return Finding(
        audit_id=8,
        rule_id="canonical_correctness",
        url="https://example.com/page",
        category="Canonical",
        priority="Critical",
        severity="Error",
        finding_type="Error",
        scope="PAGE",
        detected_value="Wrong canonical",
        expected_value="Self canonical",
        evidence="canonical=/other",
        finding_detail=detail,
        remediation="Correct the canonical",
        owner="SEO/Dev",
        acceptance_criteria="Self canonical",
    )


def test_task_csv_uses_real_finding_fields_and_action_columns():
    from audit_rules.checks.audit_deliverables import (
        TASK_CSV_COLUMNS,
        generate_task_csv,
    )
    from audit_rules.registry import load_registry

    output = generate_task_csv([_finding()], load_registry())
    reader = csv.DictReader(io.StringIO(output))
    row = next(reader)

    assert reader.fieldnames == TASK_CSV_COLUMNS
    assert row["finding"] == "Fix the canonical"
    assert row["assignee"] == "SEO/Dev"
    assert row["due_date"] == ""
    assert row["status"] == "open"
    assert row["verification_status"] == "pending"


def test_task_csv_neutralizes_spreadsheet_formulas():
    from audit_rules.checks.audit_deliverables import generate_task_csv
    from audit_rules.registry import load_registry

    output = generate_task_csv(
        [_finding(detail='=HYPERLINK("https://evil.invalid")')],
        load_registry(),
    )
    row = next(csv.DictReader(io.StringIO(output)))

    assert row["finding"].startswith("'=")


def test_task_csv_emits_header_even_when_audit_has_no_findings():
    from audit_rules.checks.audit_deliverables import (
        TASK_CSV_COLUMNS, generate_task_csv,
    )
    from audit_rules.registry import load_registry

    output = generate_task_csv([], load_registry())
    assert output.strip().split(",") == TASK_CSV_COLUMNS


def test_deliverable_adapter_requires_pipeline_marker():
    from audit_rules.adapters import DataUnavailableError
    from audit_rules.checks.audit_deliverables import check_audit_deliverables
    from audit_rules.registry import load_registry

    rule = next(rule for rule in load_registry() if rule.audit_id == 40)
    with pytest.raises(DataUnavailableError, match="Deliverable pipeline"):
        check_audit_deliverables(
            rule,
            SiteContext(base_url="https://example.com"),
            [PageContext(url="https://example.com", status_code=200)],
            {},
        )

    assert check_audit_deliverables(
        rule,
        SiteContext(base_url="https://example.com"),
        [PageContext(url="https://example.com", status_code=200)],
        {"deliverable_pipeline_available": True},
    ) == []


def test_v3_pipeline_marks_deliverable_stage_available():
    from audit_rules import integration

    class CapturingRunner:
        def __init__(self):
            self.existing_data = None

        def run_from_export(self, export_data, base_url, existing_data=None):
            self.existing_data = existing_data
            return [], []

    fake = CapturingRunner()
    integration.enable_v3()
    original = integration._runner_cache
    integration._runner_cache = fake
    try:
        integration.run_v3_pipeline(
            export_data={"site_check": {}, "pages": [], "links": []},
            base_url="https://example.com",
        )
    finally:
        integration._runner_cache = original
        integration.disable_v3()

    assert fake.existing_data["deliverable_pipeline_available"] is True
