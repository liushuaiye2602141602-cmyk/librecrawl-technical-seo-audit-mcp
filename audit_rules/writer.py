"""coverage.csv writer — produces the 9th file in the audit zip.

Requirement 10: Exactly 80 CoverageRows per audit.
Requirement 9: Existing 8-file zip preserved; only coverage.csv added.

CSV columns:
  audit_id, rule_id, category, check, priority, scope, impl_status,
  execution_status, result_status, eligible_count, evaluated_count,
  coverage_pct, finding_count, data_source, required_source,
  not_checked_reason, owner, remediation, acceptance_criteria
"""

import csv
import io
from typing import Optional, TextIO

from audit_rules.models import CoverageRow


# Canonical column order for the coverage.csv
COVERAGE_COLUMNS = [
    "audit_id",
    "rule_id",
    "category",
    "check",
    "priority",
    "scope",
    "impl_status",
    "execution_status",
    "result_status",
    "eligible_count",
    "evaluated_count",
    "coverage_pct",
    "finding_count",
    "data_source",
    "required_source",
    "not_checked_reason",
    "owner",
    "remediation",
    "acceptance_criteria",
]


def write_coverage_csv(rows: list[CoverageRow], path: str) -> int:
    """Write CoverageRow list to a CSV file.

    Args:
        rows: CoverageRow list (caller ensures exactly 80 for production)
        path: Output file path (e.g. 'output/coverage.csv')

    Returns:
        Number of rows written

    Raises:
        ValueError: If rows is empty
    """
    if not rows:
        raise ValueError("Cannot write empty coverage")

    with open(path, "w", encoding="utf-8", newline="") as f:
        return _write_rows(rows, f)


def write_coverage_csv_to_string(rows: list[CoverageRow]) -> str:
    """Write CoverageRow list to an in-memory string (for zip packaging).

    Args:
        rows: CoverageRow list (should be exactly 80)

    Returns:
        CSV content as a string
    """
    buf = io.StringIO()
    _write_rows(rows, buf)
    return buf.getvalue()


def _write_rows(rows: list[CoverageRow], f: TextIO) -> int:
    """Write rows to a text stream, return count."""
    writer = csv.DictWriter(f, fieldnames=COVERAGE_COLUMNS, extrasaction="ignore")
    writer.writeheader()

    count = 0
    for row in rows:
        writer.writerow(_row_to_dict(row))
        count += 1

    return count


def _row_to_dict(row: CoverageRow) -> dict:
    """Convert a CoverageRow to a flat dict for CSV writing."""
    return {
        "audit_id": row.audit_id,
        "rule_id": row.rule_id,
        "category": row.category,
        "check": row.check,
        "priority": str(row.priority.value) if hasattr(row.priority, "value") else str(row.priority),
        "scope": str(row.scope.value) if hasattr(row.scope, "value") else str(row.scope),
        "impl_status": str(row.impl_status.value) if hasattr(row.impl_status, "value") else str(row.impl_status),
        "execution_status": str(row.execution_status.value) if hasattr(row.execution_status, "value") else str(row.execution_status),
        "result_status": str(row.result_status.value) if hasattr(row.result_status, "value") else str(row.result_status),
        "eligible_count": row.eligible_count,
        "evaluated_count": row.evaluated_count,
        "coverage_pct": row.coverage_pct,
        "finding_count": row.finding_count,
        "data_source": row.data_source,
        "required_source": row.required_source,
        "not_checked_reason": row.not_checked_reason,
        "owner": row.owner,
        "remediation": row.remediation,
        "acceptance_criteria": row.acceptance_criteria,
    }
