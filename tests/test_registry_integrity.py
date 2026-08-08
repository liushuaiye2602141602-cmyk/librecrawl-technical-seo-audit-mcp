"""Task 1: Registry schema + validation tests.

RUN:  pytest tests/test_registry_integrity.py -v
"""

import sys
import os
import pytest
import tempfile
import csv
from pathlib import Path

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def valid_checklist_csv():
    """Minimal valid checklist CSV with 3 rules (enough to test loader)."""
    return (
        "id,category,check,description,priority,detection_method,tools,remediation,"
        "owner,status,acceptance_criteria,finding_type,seo_impact,notes\n"
        "1,抓取与索引,robots.txt 存在与规则,Test desc 1,Critical,访问 /robots.txt,"
        "Browser,修正规则,SEO/Dev,Open,/robots.txt 返回 200,Error,Crawling/Indexing,Note 1\n"
        "2,抓取与索引,XML Sitemap 提交与有效性,Test desc 2,Critical,检查 sitemap,"
        "GSC,修正,SEO,Open,Sitemap 有效,Error,Indexing,Note 2\n"
        "3,抓取与索引,页面 noindex/nofollow 检查,Test desc 3,Critical,抓取 meta,"
        "Screaming Frog,移除误设置,SEO/Dev,Open,核心页面允许索引,Error,Indexing,Note 3\n"
    )


@pytest.fixture
def valid_mapping_csv():
    """Minimal valid mapping CSV matching the 3-rule checklist."""
    return (
        "id,category,check,priority,impl_status,current_check_name,current_module,"
        "gap_description,new_module,target_severity,data_source,external_dependency,"
        "detection_method,effort_level,cannot_auto_reason\n"
        "1,抓取与索引,robots.txt 存在与规则,Critical,EXISTING_FULL,robots_txt_found,"
        "server.py,完整实现,,Error,LibreCrawl,None,STATIC_ANALYSIS,None,\n"
        "2,抓取与索引,XML Sitemap 提交与有效性,Critical,EXISTING_PARTIAL,sitemap_found,"
        "server.py,缺少 GSC 验证,checks/crawl_index.py,Error,LibreCrawl + GSC,GSC API,SITE_CHECK,LOW,\n"
        "3,抓取与索引,页面 noindex/nofollow 检查,Critical,EXISTING_FULL,meta_robots,"
        "server.py,完整实现,,Error,LibreCrawl,None,STATIC_ANALYSIS,None,\n"
    )


@pytest.fixture
def temp_csv_dir(valid_checklist_csv, valid_mapping_csv):
    """Write valid CSV files to a temp directory."""
    d = tempfile.mkdtemp()
    checklist_path = os.path.join(d, "technical_seo_master_checklist_80.csv")
    mapping_path = os.path.join(d, "master_audit_mapping.csv")
    with open(checklist_path, "w", encoding="utf-8") as f:
        f.write(valid_checklist_csv)
    with open(mapping_path, "w", encoding="utf-8") as f:
        f.write(valid_mapping_csv)
    yield checklist_path, mapping_path
    # Cleanup
    os.unlink(checklist_path)
    os.unlink(mapping_path)
    os.rmdir(d)


# ============================================================
# Test: Categories and Enums
# ============================================================

class TestCategories:
    """Verify enums are well-defined and consistent."""

    def test_priority_enum_exists(self):
        from audit_rules.categories import Priority
        assert hasattr(Priority, "CRITICAL")
        assert hasattr(Priority, "HIGH")
        assert hasattr(Priority, "MEDIUM")
        assert hasattr(Priority, "LOW")

    def test_severity_enum_exists(self):
        from audit_rules.categories import Severity
        assert hasattr(Severity, "ERROR")
        assert hasattr(Severity, "WARNING")
        assert hasattr(Severity, "OPPORTUNITY")
        assert hasattr(Severity, "INFO")

    def test_priority_not_same_as_severity(self):
        """Requirement 4: Priority and Severity must not be conflated."""
        from audit_rules.categories import Priority, Severity
        # They are distinct types
        assert Priority != Severity
        assert Priority.CRITICAL != Severity.ERROR

    def test_scope_enum_exists(self):
        from audit_rules.categories import Scope
        assert hasattr(Scope, "SITE")
        assert hasattr(Scope, "PAGE")
        assert hasattr(Scope, "LINK")
        assert hasattr(Scope, "RELATIONSHIP")
        assert hasattr(Scope, "TEMPLATE")

    def test_execution_status_enum_exists(self):
        from audit_rules.categories import ExecutionStatus
        assert hasattr(ExecutionStatus, "EXECUTED_FULL")
        assert hasattr(ExecutionStatus, "EXECUTED_PARTIAL")
        assert hasattr(ExecutionStatus, "NOT_CHECKED")
        assert hasattr(ExecutionStatus, "NOT_APPLICABLE")

    def test_result_status_enum_exists(self):
        from audit_rules.categories import ResultStatus
        assert hasattr(ResultStatus, "PASS")
        assert hasattr(ResultStatus, "FAIL")
        assert hasattr(ResultStatus, "WARNING")
        assert hasattr(ResultStatus, "OPPORTUNITY")
        assert hasattr(ResultStatus, "INTENTIONAL")
        assert hasattr(ResultStatus, "UNKNOWN")

    def test_impl_status_enum_exists(self):
        from audit_rules.categories import ImplStatus
        assert hasattr(ImplStatus, "EXISTING_FULL")
        assert hasattr(ImplStatus, "EXISTING_PARTIAL")
        assert hasattr(ImplStatus, "NEW_AUTO")
        assert hasattr(ImplStatus, "NEW_EXTERNAL_DATA")
        assert hasattr(ImplStatus, "NEW_MANUAL")

    def test_execution_status_and_result_status_are_separate(self):
        """Requirement 0.3: two-axis model — execution ≠ result."""
        from audit_rules.categories import ExecutionStatus, ResultStatus
        assert ExecutionStatus != ResultStatus
        # EXECUTED_FULL is NOT a result
        assert ExecutionStatus.EXECUTED_FULL != ResultStatus.PASS


# ============================================================
# Test: RuleDefinition Model
# ============================================================

class TestRuleDefinition:
    """Verify RuleDefinition dataclass has all required fields."""

    def test_rule_definition_required_fields(self):
        from audit_rules.models import RuleDefinition
        from audit_rules.categories import (
            Category, Priority, Severity, Scope, ImplStatus, DetectionMethod
        )

        rd = RuleDefinition(
            audit_id=1,
            rule_id="robots_txt_exists",
            category=Category.CRAWL_INDEX,
            title="robots.txt 存在与规则",
            description="Test",
            priority=Priority.CRITICAL,
            severity=Severity.ERROR,
            default_finding_type="Error",
            scope=Scope.SITE,
            execution_type=DetectionMethod.STATIC_ANALYSIS,
            required_data_sources=["LibreCrawl"],
            impl_status=ImplStatus.EXISTING_FULL,
            automatable=True,
            owner="SEO/Dev",
            remediation="修正规则",
            acceptance_criteria="/robots.txt 返回 200",
            tools="Browser, GSC",
            notes="Note",
            legacy_check_names=["robots_txt_found"],
        )
        assert rd.audit_id == 1
        assert rd.rule_id == "robots_txt_exists"
        assert rd.priority == Priority.CRITICAL
        assert rd.severity == Severity.ERROR
        assert rd.scope == Scope.SITE


# ============================================================
# Test: Finding Model
# ============================================================

class TestFindingModel:
    """Verify Finding dataclass and backward compatibility."""

    def test_finding_has_legacy_fields(self):
        """Requirement 5: url, check_name, severity, finding_detail must remain."""
        from audit_rules.models import Finding

        f = Finding(
            audit_id=1,
            rule_id="robots_txt_exists",
            url="https://example.com",
            category="抓取与索引",
            priority="Critical",
            severity="Error",
            finding_type="Error",
            scope="SITE",
            detected_value="missing",
            expected_value="present",
            evidence="No robots.txt found",
            finding_detail="/robots.txt returned 404",
            remediation="Create robots.txt",
            owner="SEO/Dev",
            acceptance_criteria="200 response",
            data_source="LibreCrawl",
            confidence=1.0,
        )

        # Legacy fields preserved (for CSV export compatibility)
        d = f.to_dict()
        assert "url" in d
        assert "check_name" in d
        assert "severity" in d
        assert "finding_detail" in d
        # check_name maps to legacy_check_name or rule_id
        assert d["check_name"] is not None


# ============================================================
# Test: CoverageRow Model
# ============================================================

class TestCoverageRow:
    """Verify CoverageRow dataclass with ExecutionStatus/ResultStatus split."""

    def test_coverage_row_required_fields(self):
        from audit_rules.models import CoverageRow
        from audit_rules.categories import (
            ExecutionStatus, ResultStatus, Priority, Scope, ImplStatus
        )

        cr = CoverageRow(
            audit_id=1,
            rule_id="robots_txt_exists",
            category="抓取与索引",
            check="robots.txt 存在与规则",
            priority=Priority.CRITICAL,
            scope=Scope.SITE,
            impl_status=ImplStatus.EXISTING_FULL,
            execution_status=ExecutionStatus.EXECUTED_FULL,
            result_status=ResultStatus.PASS,
            eligible_count=1,
            evaluated_count=1,
            coverage_pct=100.0,
            finding_count=0,
            data_source="LibreCrawl",
            required_source="LibreCrawl",
            not_checked_reason="",
            owner="SEO/Dev",
            remediation="修正规则",
            acceptance_criteria="/robots.txt 返回 200",
        )
        # Verify two-axis split (Requirement 0.3)
        assert cr.execution_status == ExecutionStatus.EXECUTED_FULL
        assert cr.result_status == ResultStatus.PASS
        assert cr.execution_status != cr.result_status  # Different enums


# ============================================================
# Test: CSV Loader
# ============================================================

class TestCSVLoader:
    """Verify both CSV files can be loaded and validated."""

    def test_load_checklist_csv(self, valid_checklist_csv):
        """Load checklist CSV and verify structure."""
        from audit_rules.registry import _load_checklist_csv
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(valid_checklist_csv)
            f.flush()
            rows = _load_checklist_csv(f.name)
        os.unlink(f.name)

        assert len(rows) == 3
        assert rows[0]["id"] == 1
        assert rows[0]["category"] == "抓取与索引"
        assert rows[0]["priority"] == "Critical"
        assert rows[2]["id"] == 3

    def test_load_mapping_csv(self, valid_mapping_csv):
        """Load mapping CSV and verify structure."""
        from audit_rules.registry import _load_mapping_csv
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(valid_mapping_csv)
            f.flush()
            rows = _load_mapping_csv(f.name)
        os.unlink(f.name)

        assert len(rows) == 3
        assert rows[0]["impl_status"] == "EXISTING_FULL"
        assert rows[1]["impl_status"] == "EXISTING_PARTIAL"

    def test_load_full_registry_from_temp_csvs(self, temp_csv_dir):
        """End-to-end: load both CSVs, merge, validate."""
        from audit_rules.registry import load_registry
        checklist_path, mapping_path = temp_csv_dir
        registry = load_registry(checklist_path, mapping_path)
        assert len(registry) == 3
        assert registry[0].audit_id == 1
        assert registry[2].audit_id == 3

    def test_load_full_80_rule_registry_from_project(self):
        """Load the real 80-item CSVs from the project."""
        from audit_rules.registry import load_registry
        checklist = PROJECT_ROOT / "audit_specs" / "technical_seo_master_checklist_80.csv"
        mapping = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        if not checklist.exists() or not mapping.exists():
            pytest.skip("Real CSV files not found")

        registry = load_registry(str(checklist), str(mapping))

        # Exactly 80 rules (Requirement 10)
        assert len(registry) == 80, f"Expected 80 rules, got {len(registry)}"

        # Unique IDs = 80 (Requirement 3)
        ids = [r.audit_id for r in registry]
        assert len(set(ids)) == 80, f"Duplicate IDs: {sorted(ids)}"

        # IDs 1-80 present, no missing (Requirement 3)
        assert set(ids) == set(range(1, 81)), f"Missing IDs: {set(range(1,81)) - set(ids)}"

    def test_load_registry_classification_counts(self):
        """Verify impl_status classification counts match expectations."""
        from audit_rules.registry import load_registry
        from audit_rules.categories import ImplStatus
        checklist = PROJECT_ROOT / "audit_specs" / "technical_seo_master_checklist_80.csv"
        mapping = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        if not checklist.exists() or not mapping.exists():
            pytest.skip("Real CSV files not found")

        registry = load_registry(str(checklist), str(mapping))

        full = sum(1 for r in registry if r.impl_status == ImplStatus.EXISTING_FULL)
        partial = sum(1 for r in registry if r.impl_status == ImplStatus.EXISTING_PARTIAL)
        new_auto = sum(1 for r in registry if r.impl_status == ImplStatus.NEW_AUTO)
        new_ext = sum(1 for r in registry if r.impl_status == ImplStatus.NEW_EXTERNAL_DATA)
        new_man = sum(1 for r in registry if r.impl_status == ImplStatus.NEW_MANUAL)

        # Phase 1 validates these counts (updated for Rule 72 MANUAL)
        assert full == 18, f"EXISTING_FULL: expected 18, got {full}"
        assert partial == 33, f"EXISTING_PARTIAL: expected 33, got {partial}"
        assert new_auto == 0, f"NEW_AUTO: expected 0 after Phase 4B, got {new_auto}"
        assert new_man >= 12, f"NEW_MANUAL: expected >=12 (Rule 72 included), got {new_man}"
        assert new_ext <= 17, f"NEW_EXTERNAL_DATA: expected <=17 (Rule 72 moved), got {new_ext}"
        assert full + partial + new_auto + new_ext + new_man == 80

    def test_missing_csv_raises_error(self):
        """CSV missing → fail fast with clear error."""
        from audit_rules.registry import load_registry
        with pytest.raises(FileNotFoundError):
            load_registry("/nonexistent/path.csv", "/also/missing.csv")

    def test_id_mismatch_between_csvs_raises_error(self, valid_checklist_csv):
        """If checklist has ID 4 but mapping doesn't → error."""
        from audit_rules.registry import load_registry

        bad_mapping = (
            "id,category,check,priority,impl_status,current_check_name,current_module,"
            "gap_description,new_module,target_severity,data_source,external_dependency,"
            "detection_method,effort_level,cannot_auto_reason\n"
            "5,抓取与索引,Nonexistent,Critical,NEW_MANUAL,,None,"
            "No match,,Error,,None,MANUAL_REVIEW,None,\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(valid_checklist_csv)
            cf = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(bad_mapping)
            mf = f.name

        with pytest.raises(ValueError, match="Missing.*id"):
            load_registry(cf, mf)

        os.unlink(cf)
        os.unlink(mf)

    def test_rule_72_is_manual(self):
        """Requirement 0.4: Rule 72 must be NEW_MANUAL, not NEW_EXTERNAL_DATA."""
        from audit_rules.registry import load_registry
        from audit_rules.categories import ImplStatus
        checklist = PROJECT_ROOT / "audit_specs" / "technical_seo_master_checklist_80.csv"
        mapping = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        if not checklist.exists() or not mapping.exists():
            pytest.skip("Real CSV files not found")

        registry = load_registry(str(checklist), str(mapping))
        rule72 = [r for r in registry if r.audit_id == 72]
        assert len(rule72) == 1, "Rule 72 not found"
        assert rule72[0].impl_status == ImplStatus.NEW_MANUAL, (
            f"Rule 72 should be NEW_MANUAL, got {rule72[0].impl_status}"
        )

    # ============================================================
    # Edge case tests (Task 2)
    # ============================================================

    def test_checklist_with_preamble_skips_title_rows(self):
        """Checklist CSV with title/description header rows should skip them."""
        from audit_rules.registry import _load_checklist_csv
        csv_content = (
            "My Custom Audit Checklist (80 items),,,,,,,,,,,,,\n"
            "适用于 WordPress 为主的独立站,,,,,,,,,,,,,\n"
            "\n"
            "id,category,check,description,priority,detection_method,tools,"
            "remediation,owner,status,acceptance_criteria,finding_type,seo_impact,notes\n"
            "1,抓取与索引,Test Rule,Test Desc,Critical,访问 /robots.txt,"
            "Browser,修正,SEO/Dev,Open,Accept,Error,Crawling,Note\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8-sig") as f:
            f.write(csv_content)
            f.flush()
            rows = _load_checklist_csv(f.name)
        os.unlink(f.name)

        assert len(rows) == 1
        assert rows[0]["id"] == 1

    def test_checklist_without_preamble_still_works(self):
        """Checklist CSV without preamble rows should also work."""
        from audit_rules.registry import _load_checklist_csv
        csv_content = (
            "id,category,check,description,priority,detection_method,tools,"
            "remediation,owner,status,acceptance_criteria,finding_type,seo_impact,notes\n"
            "1,抓取与索引,Test Rule,Test Desc,Critical,访问 /robots.txt,"
            "Browser,修正,SEO/Dev,Open,Accept,Error,Crawling,Note\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(csv_content)
            f.flush()
            rows = _load_checklist_csv(f.name)
        os.unlink(f.name)

        assert len(rows) == 1
        assert rows[0]["id"] == 1

    def test_checklist_no_data_rows_raises_error(self):
        """Checklist with header but no data rows → ValueError."""
        from audit_rules.registry import _load_checklist_csv
        csv_content = (
            "id,category,check,description,priority,detection_method,tools,"
            "remediation,owner,status,acceptance_criteria,finding_type,seo_impact,notes\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(csv_content)
            f.flush()
            with pytest.raises(ValueError, match="No valid data rows"):
                _load_checklist_csv(f.name)
        os.unlink(f.name)

    def test_checklist_no_header_raises_error(self):
        """Checklist with no 'id,' header line → ValueError."""
        from audit_rules.registry import _load_checklist_csv
        csv_content = "Not a valid header line\n1,test,check\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(csv_content)
            f.flush()
            with pytest.raises(ValueError, match="No header row"):
                _load_checklist_csv(f.name)
        os.unlink(f.name)

    def test_gapped_ids_raises_error(self):
        """Non-consecutive audit IDs → ValueError."""
        from audit_rules.registry import load_registry
        gapped_checklist = (
            "id,category,check,description,priority,detection_method,tools,"
            "remediation,owner,status,acceptance_criteria,finding_type,seo_impact,notes\n"
            "1,抓取与索引,Rule 1,Desc,Critical,检查,Browser,修正,SEO,Open,OK,Error,SEO,Note\n"
            "3,抓取与索引,Rule 3,Desc,Critical,检查,Browser,修正,SEO,Open,OK,Error,SEO,Note\n"
        )
        gapped_mapping = (
            "id,category,check,priority,impl_status,current_check_name,current_module,"
            "gap_description,new_module,target_severity,data_source,external_dependency,"
            "detection_method,effort_level,cannot_auto_reason\n"
            "1,抓取与索引,Rule 1,Critical,EXISTING_FULL,check1,server.py,,,Error,LibreCrawl,None,STATIC_ANALYSIS,None,\n"
            "3,抓取与索引,Rule 3,Critical,EXISTING_FULL,check3,server.py,,,Error,LibreCrawl,None,STATIC_ANALYSIS,None,\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(gapped_checklist)
            cf = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(gapped_mapping)
            mf = f.name
        with pytest.raises(ValueError, match="Missing audit_ids"):
            load_registry(cf, mf)
        os.unlink(cf)
        os.unlink(mf)

    def test_invalid_category_raises_error(self):
        """Invalid category value → clear ValueError."""
        from audit_rules.registry import load_registry
        bad_checklist = (
            "id,category,check,description,priority,detection_method,tools,"
            "remediation,owner,status,acceptance_criteria,finding_type,seo_impact,notes\n"
            "1,不存在的分类,Rule 1,Desc,Critical,检查,Browser,修正,SEO,Open,OK,Error,SEO,Note\n"
        )
        bad_mapping = (
            "id,category,check,priority,impl_status,current_check_name,current_module,"
            "gap_description,new_module,target_severity,data_source,external_dependency,"
            "detection_method,effort_level,cannot_auto_reason\n"
            "1,不存在的分类,Rule 1,Critical,EXISTING_FULL,check1,server.py,,,Error,LibreCrawl,None,STATIC_ANALYSIS,None,\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(bad_checklist)
            cf = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(bad_mapping)
            mf = f.name
        with pytest.raises(ValueError, match="invalid category"):
            load_registry(cf, mf)
        os.unlink(cf)
        os.unlink(mf)

    def test_invalid_priority_raises_error(self):
        """Invalid priority value → clear ValueError."""
        from audit_rules.registry import load_registry
        bad_checklist = (
            "id,category,check,description,priority,detection_method,tools,"
            "remediation,owner,status,acceptance_criteria,finding_type,seo_impact,notes\n"
            "1,抓取与索引,Rule 1,Desc,SUPER_URGENT,检查,Browser,修正,SEO,Open,OK,Error,SEO,Note\n"
        )
        bad_mapping = (
            "id,category,check,priority,impl_status,current_check_name,current_module,"
            "gap_description,new_module,target_severity,data_source,external_dependency,"
            "detection_method,effort_level,cannot_auto_reason\n"
            "1,抓取与索引,Rule 1,SUPER_URGENT,EXISTING_FULL,check1,server.py,,,Error,LibreCrawl,None,STATIC_ANALYSIS,None,\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(bad_checklist)
            cf = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(bad_mapping)
            mf = f.name
        with pytest.raises(ValueError, match="invalid priority"):
            load_registry(cf, mf)
        os.unlink(cf)
        os.unlink(mf)

    def test_invalid_impl_status_raises_error(self):
        """Invalid impl_status value → clear ValueError."""
        from audit_rules.registry import load_registry
        good_checklist = (
            "id,category,check,description,priority,detection_method,tools,"
            "remediation,owner,status,acceptance_criteria,finding_type,seo_impact,notes\n"
            "1,抓取与索引,Rule 1,Desc,Critical,检查,Browser,修正,SEO,Open,OK,Error,SEO,Note\n"
        )
        bad_mapping = (
            "id,category,check,priority,impl_status,current_check_name,current_module,"
            "gap_description,new_module,target_severity,data_source,external_dependency,"
            "detection_method,effort_level,cannot_auto_reason\n"
            "1,抓取与索引,Rule 1,Critical,UNKNOWN_STATUS,check1,server.py,,,Error,LibreCrawl,None,STATIC_ANALYSIS,None,\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(good_checklist)
            cf = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(bad_mapping)
            mf = f.name
        with pytest.raises(ValueError, match="invalid impl_status"):
            load_registry(cf, mf)
        os.unlink(cf)
        os.unlink(mf)

    def test_utf8_bom_checklist_parses_correctly(self):
        """Checklist with UTF-8 BOM should parse the same as without."""
        from audit_rules.registry import _load_checklist_csv
        csv_content = (
            "id,category,check,description,priority,detection_method,tools,"
            "remediation,owner,status,acceptance_criteria,finding_type,seo_impact,notes\n"
            "1,抓取与索引,Rule 1,Desc,Critical,检查,Browser,修正,SEO,Open,OK,Error,SEO,Note\n"
        )
        # Write with BOM
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8-sig") as f:
            f.write(csv_content)
            bom_path = f.name
        # Write without BOM
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(csv_content)
            no_bom_path = f.name

        rows_bom = _load_checklist_csv(bom_path)
        rows_no_bom = _load_checklist_csv(no_bom_path)
        os.unlink(bom_path)
        os.unlink(no_bom_path)

        assert len(rows_bom) == len(rows_no_bom) == 1
        assert rows_bom[0]["id"] == rows_no_bom[0]["id"]

    def test_compound_detection_method_maps_to_composite(self):
        """'SITE_CHECK + EXTERNAL_API' should parse as DetectionMethod.COMPOSITE."""
        from audit_rules.registry import _parse_detection_method
        from audit_rules.categories import DetectionMethod
        result = _parse_detection_method("SITE_CHECK + EXTERNAL_API")
        assert result == DetectionMethod.COMPOSITE
        result2 = _parse_detection_method("STATIC_ANALYSIS + EXTERNAL_API")
        assert result2 == DetectionMethod.COMPOSITE

    def test_empty_mapping_raises_missing_error(self, valid_checklist_csv):
        """Mapping with no matching IDs → error about missing mappings."""
        from audit_rules.registry import load_registry
        empty_mapping = (
            "id,category,check,priority,impl_status,current_check_name,current_module,"
            "gap_description,new_module,target_severity,data_source,external_dependency,"
            "detection_method,effort_level,cannot_auto_reason\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(valid_checklist_csv)
            cf = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(empty_mapping)
            mf = f.name
        with pytest.raises(ValueError, match="No valid data rows"):
            load_registry(cf, mf)
        os.unlink(cf)
        os.unlink(mf)
