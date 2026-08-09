"""Task 7: coverage.csv writer tests."""

import sys
import os
import pytest
import tempfile
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def sample_rows():
    """3 representative CoverageRow objects for writer testing."""
    from audit_rules.models import CoverageRow
    from audit_rules.categories import (
        ExecutionStatus, ResultStatus, Priority, Scope, ImplStatus,
    )
    return [
        CoverageRow(
            audit_id=1, rule_id="robots_txt_exists",
            category="抓取与索引", check="robots.txt 存在与规则",
            priority=Priority.CRITICAL, scope=Scope.SITE,
            impl_status=ImplStatus.EXISTING_FULL,
            execution_status=ExecutionStatus.EXECUTED_FULL,
            result_status=ResultStatus.PASS,
            eligible_count=1, evaluated_count=1, coverage_pct=100.0,
            finding_count=0, data_source="LibreCrawl",
            required_source="LibreCrawl", not_checked_reason="",
            owner="SEO/Dev", remediation="修正规则",
            acceptance_criteria="/robots.txt 返回 200",
        ),
        CoverageRow(
            audit_id=2, rule_id="xml_sitemap_valid",
            category="抓取与索引", check="XML Sitemap 提交与有效性",
            priority=Priority.CRITICAL, scope=Scope.SITE,
            impl_status=ImplStatus.EXISTING_PARTIAL,
            execution_status=ExecutionStatus.EXECUTED_FULL,
            result_status=ResultStatus.WARNING,
            eligible_count=1, evaluated_count=1, coverage_pct=100.0,
            finding_count=1, data_source="LibreCrawl",
            required_source="LibreCrawl + GSC", not_checked_reason="",
            owner="SEO", remediation="生成/修正 sitemap",
            acceptance_criteria="Sitemap 中 URL 均为 200 + Indexable",
        ),
        CoverageRow(
            audit_id=72, rule_id="manual_actions_security",
            category="安全与 Header", check="手动操作与安全问题",
            priority=Priority.CRITICAL, scope=Scope.SITE,
            impl_status=ImplStatus.NEW_MANUAL,
            execution_status=ExecutionStatus.NOT_CHECKED,
            result_status=ResultStatus.UNKNOWN,
            eligible_count=0, evaluated_count=0, coverage_pct=0.0,
            finding_count=0, data_source="Manual Review",
            required_source="Manual Review",
            not_checked_reason="Manual review required: SEO",
            owner="SEO", remediation="手动审查",
            acceptance_criteria="无安全问题",
        ),
    ]


@pytest.fixture
def full_coverage_rows():
    """Generate 80 coverage rows from the real registry."""
    from audit_rules.registry import load_registry
    from audit_rules.coverage import CoverageManager
    from audit_rules.context import SiteContext, PageContext

    checklist = PROJECT_ROOT / "audit_specs" / "technical_seo_master_checklist_80.csv"
    mapping = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
    if not checklist.exists() or not mapping.exists():
        pytest.skip("Real CSV files not found")

    registry = load_registry(str(checklist), str(mapping))
    site_ctx = SiteContext(base_url="https://example.com")
    pages = [PageContext(url="https://example.com", status_code=200)]

    mgr = CoverageManager(registry)
    return mgr.compute(site_ctx, pages, [], providers_available={"LibreCrawl"})


# ============================================================
# Test: CSV writing basics
# ============================================================

class TestCoverageWriter:
    """Verify coverage.csv output."""

    def test_write_to_file(self, sample_rows):
        from audit_rules.writer import write_coverage_csv

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("")  # placeholder
            path = f.name

        try:
            count = write_coverage_csv(sample_rows, path)
            assert count == 3
            assert os.path.exists(path)

            # Verify content
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                written = list(reader)
                assert len(written) == 3
                assert written[0]["audit_id"] == "1"
                assert written[0]["rule_id"] == "robots_txt_exists"
                assert written[0]["execution_status"] == "EXECUTED_FULL"
                assert written[0]["result_status"] == "PASS"
                assert written[2]["audit_id"] == "72"
                assert written[2]["execution_status"] == "NOT_CHECKED"
        finally:
            os.unlink(path)

    def test_write_to_string(self, sample_rows):
        from audit_rules.writer import write_coverage_csv_to_string

        csv_str = write_coverage_csv_to_string(sample_rows)
        assert "audit_id" in csv_str
        assert "robots_txt_exists" in csv_str
        assert "NOT_CHECKED" in csv_str

        # Parse back and verify
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 3
        assert rows[0]["priority"] == "Critical"
        assert rows[1]["result_status"] == "WARNING"

    def test_column_order(self, sample_rows):
        from audit_rules.writer import write_coverage_csv_to_string, COVERAGE_COLUMNS

        csv_str = write_coverage_csv_to_string(sample_rows)
        header_line = csv_str.split("\n")[0].rstrip("\r")
        assert header_line == ",".join(COVERAGE_COLUMNS)

    def test_all_19_columns_present(self, sample_rows):
        from audit_rules.writer import write_coverage_csv_to_string
        from audit_rules.writer import COVERAGE_COLUMNS

        csv_str = write_coverage_csv_to_string(sample_rows)
        reader = csv.DictReader(io.StringIO(csv_str))
        for row in reader:
            for col in COVERAGE_COLUMNS:
                assert col in row, f"Missing column: {col}"

    def test_write_full_80_rows(self, full_coverage_rows):
        from audit_rules.writer import write_coverage_csv

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            path = f.name

        try:
            count = write_coverage_csv(full_coverage_rows, path)
            assert count == 80

            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                written = list(reader)
                assert len(written) == 80
                ids = [int(r["audit_id"]) for r in written]
                assert set(ids) == set(range(1, 81))
        finally:
            os.unlink(path)

    def test_write_empty_raises_error(self):
        from audit_rules.writer import write_coverage_csv
        with pytest.raises(ValueError, match="empty"):
            write_coverage_csv([], "/tmp/test.csv")

    def test_write_any_count_succeeds(self, sample_rows):
        """Writer accepts any non-empty count (80-rule enforcement is caller's job)."""
        from audit_rules.writer import write_coverage_csv

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            path = f.name
        try:
            count = write_coverage_csv(sample_rows, path)
            assert count == 3  # 3 rows written successfully
        finally:
            os.unlink(path)

    def test_write_to_string_full_80(self, full_coverage_rows):
        from audit_rules.writer import write_coverage_csv_to_string

        csv_str = write_coverage_csv_to_string(full_coverage_rows)
        lines = csv_str.strip().split("\n")
        # Header + 80 data rows
        assert len(lines) == 81
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 80

    def test_csv_roundtrip(self, sample_rows):
        """Write → read → values match original."""
        from audit_rules.writer import write_coverage_csv_to_string

        csv_str = write_coverage_csv_to_string(sample_rows)
        reader = csv.DictReader(io.StringIO(csv_str))
        parsed = list(reader)
        assert parsed[0]["rule_id"] == "robots_txt_exists"
        assert int(parsed[0]["eligible_count"]) == 1
        assert float(parsed[0]["coverage_pct"]) == 100.0
        assert int(parsed[1]["finding_count"]) == 1
        assert parsed[2]["not_checked_reason"] == "Manual review required: SEO"

    def test_utf8_output_handles_chinese(self, sample_rows):
        from audit_rules.writer import write_coverage_csv_to_string

        csv_str = write_coverage_csv_to_string(sample_rows)
        # Categories are in Chinese
        assert "抓取与索引" in csv_str
        assert "安全与 Header" in csv_str


# Need StringIO
import io
