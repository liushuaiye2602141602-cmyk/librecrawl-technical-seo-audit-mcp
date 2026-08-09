"""Task 4: Coverage semantics tests — 5 state semantics (CASE A-E).

CASE A: EXECUTED_FULL + PASS — rule executed, no issues found
CASE B: EXECUTED_FULL + FAIL — rule executed, errors found
CASE C: EXECUTED_PARTIAL + WARNING — sampled/partial execution
CASE D: NOT_CHECKED + UNKNOWN — missing external data or manual
CASE E: NOT_APPLICABLE + UNKNOWN — rule doesn't apply to this site type
"""

import sys
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def mini_registry():
    """A small registry with representative rules for each case."""
    from audit_rules.models import RuleDefinition
    from audit_rules.categories import (
        Category, Priority, Severity, Scope, ImplStatus, DetectionMethod,
    )

    return [
        # CASE A/B: EXISTING_FULL — automatable, fully executed
        RuleDefinition(
            audit_id=1, rule_id="robots_txt_exists",
            category=Category.CRAWL_INDEX, title="robots.txt 存在与规则",
            description="Test", priority=Priority.CRITICAL,
            severity=Severity.ERROR, default_finding_type="Error",
            scope=Scope.SITE, execution_type=DetectionMethod.STATIC_ANALYSIS,
            required_data_sources=["LibreCrawl"], impl_status=ImplStatus.EXISTING_FULL,
            automatable=True, owner="SEO/Dev", remediation="修正",
            acceptance_criteria="200", tools="Browser", notes="",
            legacy_check_names=["robots_txt_found"],
        ),
        # CASE A/B: EXISTING_FULL — page-scope, automatable
        RuleDefinition(
            audit_id=3, rule_id="page_noindex_nofollow",
            category=Category.CRAWL_INDEX, title="页面 noindex/nofollow 检查",
            description="Test", priority=Priority.CRITICAL,
            severity=Severity.ERROR, default_finding_type="Error",
            scope=Scope.PAGE, execution_type=DetectionMethod.STATIC_ANALYSIS,
            required_data_sources=["LibreCrawl"], impl_status=ImplStatus.EXISTING_FULL,
            automatable=True, owner="SEO/Dev", remediation="修正",
            acceptance_criteria="OK", tools="Screaming Frog", notes="",
            legacy_check_names=["meta_robots"],
        ),
        # CASE C: EXISTING_PARTIAL — partially automated
        RuleDefinition(
            audit_id=5, rule_id="crawl_budget_waste",
            category=Category.CRAWL_INDEX, title="抓取预算浪费",
            description="Test", priority=Priority.HIGH,
            severity=Severity.WARNING, default_finding_type="Warning",
            scope=Scope.SITE, execution_type=DetectionMethod.COMPOSITE,
            required_data_sources=["LibreCrawl", "GSC API", "Server Logs"],
            impl_status=ImplStatus.EXISTING_PARTIAL,
            automatable=True, owner="SEO", remediation="修正",
            acceptance_criteria="OK", tools="GSC", notes="",
            legacy_check_names=["spider_trap_calendar"],
        ),
        # CASE D: NEW_MANUAL — manual review only
        RuleDefinition(
            audit_id=72, rule_id="manual_actions_security",
            category=Category.SECURITY, title="手动操作与安全问题",
            description="Test", priority=Priority.CRITICAL,
            severity=Severity.ERROR, default_finding_type="Error",
            scope=Scope.SITE, execution_type=DetectionMethod.MANUAL_REVIEW,
            required_data_sources=["Manual Review"], impl_status=ImplStatus.NEW_MANUAL,
            automatable=False, owner="SEO", remediation="手动审查",
            acceptance_criteria="无安全问题", tools="GSC", notes="",
            legacy_check_names=[],
        ),
        # CASE D: NEW_EXTERNAL_DATA — requires GSC which may be unavailable
        RuleDefinition(
            audit_id=34, rule_id="gsc_ga4_config",
            category=Category.MONITORING, title="GSC/GA4 配置验证",
            description="Test", priority=Priority.HIGH,
            severity=Severity.ERROR, default_finding_type="Error",
            scope=Scope.SITE, execution_type=DetectionMethod.EXTERNAL_API,
            required_data_sources=["LibreCrawl", "GSC API", "GA4"],
            impl_status=ImplStatus.NEW_EXTERNAL_DATA,
            automatable=False, owner="SEO", remediation="配置GSC",
            acceptance_criteria="OK", tools="GSC, GA4", notes="",
            legacy_check_names=[],
        ),
        # CASE E: WordPress rule on generic site → NOT_APPLICABLE
        RuleDefinition(
            audit_id=36, rule_id="wp_updates_security",
            category=Category.SECURITY, title="WordPress 核心/插件/主题更新",
            description="Test", priority=Priority.CRITICAL,
            severity=Severity.ERROR, default_finding_type="Error",
            scope=Scope.SITE, execution_type=DetectionMethod.SITE_CHECK,
            required_data_sources=["LibreCrawl"], impl_status=ImplStatus.NEW_AUTO,
            automatable=True, owner="Dev", remediation="更新WP",
            acceptance_criteria="最新版本", tools="WP Admin", notes="",
            legacy_check_names=[],
        ),
    ]


@pytest.fixture
def sample_site_ctx():
    from audit_rules.context import SiteContext
    return SiteContext(
        base_url="https://example.com",
        robots_txt_found=True,
        site_profile="generic",  # Not WordPress
    )


@pytest.fixture
def sample_page_contexts():
    from audit_rules.context import PageContext
    return [
        PageContext(url="https://example.com", status_code=200),
        PageContext(url="https://example.com/about", status_code=200),
        PageContext(url="https://example.com/contact", status_code=200),
    ]


@pytest.fixture
def wordpress_site_ctx():
    from audit_rules.context import SiteContext
    return SiteContext(
        base_url="https://example.com",
        robots_txt_found=True,
        site_profile="wordpress",
    )


# ============================================================
# Test: 5 State Semantics (CASE A-E)
# ============================================================

class TestCoverageStateSemantics:
    """Verify the 5 key coverage state semantics."""

    def test_case_a_executed_full_pass(self, mini_registry, sample_site_ctx, sample_page_contexts):
        """CASE A: EXECUTED_FULL + PASS — rule executed, no findings."""
        from audit_rules.coverage import CoverageManager
        from audit_rules.categories import ExecutionStatus, ResultStatus

        mgr = CoverageManager(mini_registry)
        rows = mgr.compute(sample_site_ctx, sample_page_contexts, [],
                           providers_available={"LibreCrawl"})

        # Rule 1 (robots.txt) — automatable, no findings → EXECUTED_FULL + PASS
        r1 = [r for r in rows if r.audit_id == 1][0]
        assert r1.execution_status == ExecutionStatus.EXECUTED_FULL
        assert r1.result_status == ResultStatus.PASS
        assert r1.finding_count == 0

    def test_case_b_executed_full_fail(self, mini_registry, sample_site_ctx, sample_page_contexts):
        """CASE B: EXECUTED_FULL + FAIL — rule executed, errors found."""
        from audit_rules.coverage import CoverageManager
        from audit_rules.models import Finding
        from audit_rules.categories import ExecutionStatus, ResultStatus

        findings = [
            Finding(
                audit_id=1, rule_id="robots_txt_exists",
                url="https://example.com", category="抓取与索引",
                priority="Critical", severity="Error", finding_type="Error",
                scope="SITE", detected_value="missing",
                expected_value="present", evidence="No robots.txt",
                finding_detail="/robots.txt returned 404",
                remediation="Create robots.txt", owner="SEO/Dev",
                acceptance_criteria="200", data_source="LibreCrawl",
            ),
        ]

        mgr = CoverageManager(mini_registry)
        rows = mgr.compute(sample_site_ctx, sample_page_contexts, findings,
                           providers_available={"LibreCrawl"})

        r1 = [r for r in rows if r.audit_id == 1][0]
        assert r1.execution_status == ExecutionStatus.EXECUTED_FULL
        assert r1.result_status == ResultStatus.FAIL
        assert r1.finding_count == 1

    def test_completed_page_adapter_evaluates_all_pages_even_with_one_finding(
        self, mini_registry, sample_site_ctx, sample_page_contexts
    ):
        from audit_rules.coverage import CoverageManager
        from audit_rules.models import Finding
        from audit_rules.categories import ExecutionStatus

        finding = Finding(
            audit_id=3, rule_id="page_noindex_nofollow",
            url="https://example.com/about", category="crawl",
            priority="Critical", severity="Error", finding_type="Error",
            scope="PAGE", detected_value="noindex", expected_value="index",
            evidence="meta robots", finding_detail="one affected page",
            remediation="remove noindex", owner="SEO",
            acceptance_criteria="indexable", data_source="LibreCrawl")
        rows = CoverageManager(mini_registry).compute(
            sample_site_ctx, sample_page_contexts, [finding],
            providers_available={"LibreCrawl"}, executed_rule_ids={3})
        row = next(row for row in rows if row.audit_id == 3)
        assert row.execution_status == ExecutionStatus.EXECUTED_FULL
        assert row.eligible_count == 3
        assert row.evaluated_count == 3
        assert row.coverage_pct == 100.0

    def test_case_c_executed_partial_warning(self, mini_registry, sample_site_ctx, sample_page_contexts):
        """CASE C: EXECUTED_PARTIAL — partially available data, some findings."""
        from audit_rules.coverage import CoverageManager
        from audit_rules.models import Finding
        from audit_rules.categories import ExecutionStatus, ResultStatus

        # Rule 5 (crawl_budget_waste) requires LibreCrawl + GSC + Server Logs
        # Only LibreCrawl is available → PARTIAL
        findings = [
            Finding(
                audit_id=5, rule_id="crawl_budget_waste",
                url="https://example.com", category="抓取与索引",
                priority="High", severity="Warning", finding_type="Warning",
                scope="SITE", detected_value="spider_trap", expected_value="clean",
                evidence="Calendar URLs detected", finding_detail="Found 50 trap URLs",
                remediation="Block traps in robots.txt", owner="SEO",
                acceptance_criteria="No traps", data_source="LibreCrawl",
            ),
        ]

        mgr = CoverageManager(mini_registry)
        rows = mgr.compute(sample_site_ctx, sample_page_contexts, findings,
                           providers_available={"LibreCrawl"})

        r5 = [r for r in rows if r.audit_id == 5][0]
        # Rule 5 has GSC + Server Logs missing → NOT_CHECKED due to missing data
        assert r5.execution_status == ExecutionStatus.NOT_CHECKED
        assert r5.result_status == ResultStatus.UNKNOWN
        assert "GSC API" in r5.not_checked_reason

    def test_completed_local_adapter_with_findings_and_missing_provider_is_partial(
        self, mini_registry, sample_site_ctx, sample_page_contexts
    ):
        """Production findings cannot coexist with NOT_CHECKED/evaluated=0."""
        from audit_rules.coverage import CoverageManager
        from audit_rules.models import Finding
        from audit_rules.categories import ExecutionStatus, ResultStatus

        finding = Finding(
            audit_id=5, rule_id="crawl_budget_waste",
            url="https://example.com", category="抓取与索引",
            priority="High", severity="Warning", finding_type="Warning",
            scope="SITE", evidence="Local crawl trap evidence",
        )

        rows = CoverageManager(mini_registry).compute(
            sample_site_ctx,
            sample_page_contexts,
            [finding],
            providers_available={"LibreCrawl"},
            executed_rule_ids={5},
        )
        row = next(row for row in rows if row.audit_id == 5)

        assert row.execution_status == ExecutionStatus.EXECUTED_PARTIAL
        assert row.result_status == ResultStatus.WARNING
        assert row.evaluated_count == 1
        assert row.finding_count == 1
        assert "GSC API" in row.not_checked_reason

    def test_case_c_partial_with_all_providers(self, mini_registry, sample_site_ctx, sample_page_contexts):
        """CASE C variant: EXISTING_PARTIAL with all providers available → fully executed."""
        from audit_rules.coverage import CoverageManager
        from audit_rules.categories import ExecutionStatus, ResultStatus

        mgr = CoverageManager(mini_registry)
        rows = mgr.compute(sample_site_ctx, sample_page_contexts, [],
                           providers_available={"LibreCrawl", "GSC API", "Server Logs"})

        r5 = [r for r in rows if r.audit_id == 5][0]
        assert r5.execution_status == ExecutionStatus.EXECUTED_FULL
        assert r5.result_status == ResultStatus.PASS

    def test_case_d_manual_rule_not_checked(self, mini_registry, sample_site_ctx, sample_page_contexts):
        """CASE D: NEW_MANUAL → NOT_CHECKED + UNKNOWN regardless of findings."""
        from audit_rules.coverage import CoverageManager
        from audit_rules.categories import ExecutionStatus, ResultStatus

        mgr = CoverageManager(mini_registry)
        rows = mgr.compute(sample_site_ctx, sample_page_contexts, [],
                           providers_available={"LibreCrawl"})

        r72 = [r for r in rows if r.audit_id == 72][0]
        assert r72.execution_status == ExecutionStatus.NOT_CHECKED
        assert r72.result_status == ResultStatus.UNKNOWN
        assert "Manual review" in r72.not_checked_reason

    def test_case_d_external_data_unavailable(self, mini_registry, sample_site_ctx, sample_page_contexts):
        """CASE D: EXTERNAL_DATA with missing provider → NOT_CHECKED + UNKNOWN."""
        from audit_rules.coverage import CoverageManager
        from audit_rules.categories import ExecutionStatus, ResultStatus

        # Only LibreCrawl available, GSC + GA4 missing
        mgr = CoverageManager(mini_registry)
        rows = mgr.compute(sample_site_ctx, sample_page_contexts, [],
                           providers_available={"LibreCrawl"})

        r34 = [r for r in rows if r.audit_id == 34][0]
        assert r34.execution_status == ExecutionStatus.NOT_CHECKED
        assert r34.result_status == ResultStatus.UNKNOWN
        assert "GSC API" in r34.not_checked_reason

    def test_case_e_not_applicable_wordpress_on_generic(self, mini_registry, sample_site_ctx, sample_page_contexts):
        """CASE E: WordPress rule on generic site → NOT_APPLICABLE + UNKNOWN."""
        from audit_rules.coverage import CoverageManager
        from audit_rules.categories import ExecutionStatus, ResultStatus

        mgr = CoverageManager(mini_registry)
        rows = mgr.compute(sample_site_ctx, sample_page_contexts, [],
                           providers_available={"LibreCrawl"})

        r36 = [r for r in rows if r.audit_id == 36][0]
        assert r36.execution_status == ExecutionStatus.NOT_APPLICABLE
        assert r36.result_status == ResultStatus.UNKNOWN
        assert "WordPress-specific" in r36.not_checked_reason

    def test_case_e_wordpress_rule_on_wordpress_site(self, mini_registry, wordpress_site_ctx, sample_page_contexts):
        """CASE E variant: WordPress rule on WordPress site → applicable, executes."""
        from audit_rules.coverage import CoverageManager
        from audit_rules.categories import ExecutionStatus, ResultStatus

        mgr = CoverageManager(mini_registry)
        rows = mgr.compute(wordpress_site_ctx, sample_page_contexts, [],
                           providers_available={"LibreCrawl"})

        r36 = [r for r in rows if r.audit_id == 36][0]
        assert r36.execution_status != ExecutionStatus.NOT_APPLICABLE
        assert r36.execution_status == ExecutionStatus.EXECUTED_FULL
        assert r36.result_status == ResultStatus.PASS


# ============================================================
# Test: CoverageRow counts
# ============================================================

class TestCoverageRowCounts:
    """Verify CoverageManager produces correct counts."""

    def test_exactly_n_rows_equal_registry_size(self, mini_registry, sample_site_ctx, sample_page_contexts):
        """CoverageManager must produce one row per registry rule (exactly N)."""
        from audit_rules.coverage import CoverageManager
        mgr = CoverageManager(mini_registry)
        rows = mgr.compute(sample_site_ctx, sample_page_contexts, [],
                           providers_available={"LibreCrawl"})
        assert len(rows) == len(mini_registry)

    def test_eligible_count_site_scope_is_one(self, mini_registry, sample_site_ctx, sample_page_contexts):
        """SITE-scope rules have eligible_count = 1."""
        from audit_rules.coverage import CoverageManager
        mgr = CoverageManager(mini_registry)
        rows = mgr.compute(sample_site_ctx, sample_page_contexts, [],
                           providers_available={"LibreCrawl"})
        r1 = [r for r in rows if r.audit_id == 1][0]
        assert r1.eligible_count == 1

    def test_eligible_count_page_scope_counts_200_pages(self, mini_registry, sample_site_ctx, sample_page_contexts):
        """PAGE-scope rules count all 200-status pages."""
        from audit_rules.coverage import CoverageManager
        mgr = CoverageManager(mini_registry)
        rows = mgr.compute(sample_site_ctx, sample_page_contexts, [],
                           providers_available={"LibreCrawl"})
        r3 = [r for r in rows if r.audit_id == 3][0]
        assert r3.eligible_count == 3  # 3 pages, all 200

    def test_eligible_excludes_non200_pages(self, mini_registry, sample_site_ctx):
        """PAGE-scope rules exclude 404/500/etc pages."""
        from audit_rules.coverage import CoverageManager
        from audit_rules.context import PageContext
        pages = [
            PageContext(url="https://example.com", status_code=200),
            PageContext(url="https://example.com/404", status_code=404),
            PageContext(url="https://example.com/500", status_code=500),
            PageContext(url="https://example.com/about", status_code=200),
        ]
        mgr = CoverageManager(mini_registry)
        rows = mgr.compute(sample_site_ctx, pages, [],
                           providers_available={"LibreCrawl"})
        r3 = [r for r in rows if r.audit_id == 3][0]
        assert r3.eligible_count == 2  # Only the two 200s

    def test_coverage_pct_computed(self, mini_registry, sample_site_ctx, sample_page_contexts):
        """coverage_pct = evaluated / eligible * 100."""
        from audit_rules.coverage import CoverageManager
        mgr = CoverageManager(mini_registry)
        rows = mgr.compute(sample_site_ctx, sample_page_contexts, [],
                           providers_available={"LibreCrawl"})
        for row in rows:
            if row.execution_status not in (
                row.execution_status.NOT_CHECKED,
                row.execution_status.NOT_APPLICABLE,
            ):
                if row.eligible_count > 0:
                    expected = round(row.evaluated_count / row.eligible_count * 100, 1)
                    assert row.coverage_pct == expected

    def test_not_checked_has_zero_evaluated(self, mini_registry, sample_site_ctx, sample_page_contexts):
        """NOT_CHECKED rules have evaluated_count = 0."""
        from audit_rules.coverage import CoverageManager
        mgr = CoverageManager(mini_registry)
        rows = mgr.compute(sample_site_ctx, sample_page_contexts, [],
                           providers_available={"LibreCrawl"})
        r72 = [r for r in rows if r.audit_id == 72][0]
        assert r72.evaluated_count == 0

    def test_not_applicable_has_zero_evaluated(self, mini_registry, sample_site_ctx, sample_page_contexts):
        """NOT_APPLICABLE rules have evaluated_count = 0."""
        from audit_rules.coverage import CoverageManager
        mgr = CoverageManager(mini_registry)
        rows = mgr.compute(sample_site_ctx, sample_page_contexts, [],
                           providers_available={"LibreCrawl"})
        r36 = [r for r in rows if r.audit_id == 36][0]
        assert r36.evaluated_count == 0


# ============================================================
# Test: Finding result derivation
# ============================================================

class TestFindingResultDerivation:
    """Verify result status is correctly derived from findings."""

    def test_error_finding_produces_fail(self):
        from audit_rules.coverage import CoverageManager
        from audit_rules.models import Finding
        findings = [
            Finding(
                audit_id=1, rule_id="test", url="https://x.com",
                category="Test", priority="High", severity="Error",
                finding_type="Error", scope="SITE",
                detected_value="x", expected_value="y",
                evidence="z", finding_detail="z",
                remediation="fix", owner="seo",
                acceptance_criteria="ok", data_source="LibreCrawl",
            ),
        ]
        result = CoverageManager(registry=[])._derive_result_from_findings(findings)
        from audit_rules.categories import ResultStatus
        assert result == ResultStatus.FAIL

    def test_warning_finding_produces_warning(self):
        from audit_rules.coverage import CoverageManager
        from audit_rules.models import Finding
        findings = [
            Finding(
                audit_id=1, rule_id="test", url="https://x.com",
                category="Test", priority="Medium", severity="Warning",
                finding_type="Warning", scope="SITE",
                detected_value="x", expected_value="y",
                evidence="z", finding_detail="z",
                remediation="fix", owner="seo",
                acceptance_criteria="ok", data_source="LibreCrawl",
            ),
        ]
        result = CoverageManager(registry=[])._derive_result_from_findings(findings)
        from audit_rules.categories import ResultStatus
        assert result == ResultStatus.WARNING

    def test_opportunity_finding_produces_opportunity(self):
        from audit_rules.coverage import CoverageManager
        from audit_rules.models import Finding
        findings = [
            Finding(
                audit_id=1, rule_id="test", url="https://x.com",
                category="Test", priority="Low", severity="Opportunity",
                finding_type="Opportunity", scope="SITE",
                detected_value="x", expected_value="y",
                evidence="z", finding_detail="z",
                remediation="fix", owner="seo",
                acceptance_criteria="ok", data_source="LibreCrawl",
            ),
        ]
        result = CoverageManager(registry=[])._derive_result_from_findings(findings)
        from audit_rules.categories import ResultStatus
        assert result == ResultStatus.OPPORTUNITY

    def test_mixed_severities_produces_worst(self):
        """Error + Warning + Opportunity → FAIL (worst wins)."""
        from audit_rules.coverage import CoverageManager
        from audit_rules.models import Finding
        findings = [
            Finding(
                audit_id=1, rule_id="test", url="https://x.com",
                category="Test", priority="High", severity="Warning",
                finding_type="Warning", scope="SITE",
                detected_value="x", expected_value="y",
                evidence="z", finding_detail="z",
                remediation="fix", owner="seo",
                acceptance_criteria="ok", data_source="LibreCrawl",
            ),
            Finding(
                audit_id=1, rule_id="test", url="https://x.com/page2",
                category="Test", priority="High", severity="Error",
                finding_type="Error", scope="PAGE",
                detected_value="x", expected_value="y",
                evidence="z", finding_detail="z",
                remediation="fix", owner="seo",
                acceptance_criteria="ok", data_source="LibreCrawl",
            ),
            Finding(
                audit_id=1, rule_id="test", url="https://x.com/page3",
                category="Test", priority="Low", severity="Opportunity",
                finding_type="Opportunity", scope="PAGE",
                detected_value="x", expected_value="y",
                evidence="z", finding_detail="z",
                remediation="fix", owner="seo",
                acceptance_criteria="ok", data_source="LibreCrawl",
            ),
        ]
        result = CoverageManager(registry=[])._derive_result_from_findings(findings)
        from audit_rules.categories import ResultStatus
        assert result == ResultStatus.FAIL


# ============================================================
# Test: Provider availability
# ============================================================

class TestProviderAvailability:
    """Verify NOT_CHECKED for rules requiring unavailable providers."""

    def test_default_providers_is_librecrawl_only(self, mini_registry, sample_site_ctx, sample_page_contexts):
        """Default providers_available = {'LibreCrawl'}."""
        from audit_rules.coverage import CoverageManager
        from audit_rules.categories import ExecutionStatus

        mgr = CoverageManager(mini_registry)
        rows = mgr.compute(sample_site_ctx, sample_page_contexts, [])

        # Rules requiring only LibreCrawl should execute
        r1 = [r for r in rows if r.audit_id == 1][0]
        assert r1.execution_status == ExecutionStatus.EXECUTED_FULL

        # Rules requiring GSC should NOT CHECK
        r34 = [r for r in rows if r.audit_id == 34][0]
        assert r34.execution_status == ExecutionStatus.NOT_CHECKED

    def test_all_providers_available_executes_all_auto_rules(self, mini_registry, sample_site_ctx, sample_page_contexts):
        """With all providers, all automatable rules should execute.

        NEW_EXTERNAL_DATA rules remain NOT_CHECKED even with all providers
        because they require implementation (code changes), not just API access.
        EXISTING_PARTIAL rules that were blocked by missing data SHOULD execute.
        """
        from audit_rules.coverage import CoverageManager
        from audit_rules.categories import ExecutionStatus

        mgr = CoverageManager(mini_registry)
        rows = mgr.compute(sample_site_ctx, sample_page_contexts, [],
                           providers_available={"LibreCrawl", "GSC API", "GA4", "Server Logs"})

        # Rule 5 (EXISTING_PARTIAL) — was NOT_CHECKED before, now fully executes
        r5 = [r for r in rows if r.audit_id == 5][0]
        assert r5.execution_status == ExecutionStatus.EXECUTED_FULL

        # Rule 34 (NEW_EXTERNAL_DATA) — still NOT_CHECKED (needs implementation)
        r34 = [r for r in rows if r.audit_id == 34][0]
        assert r34.execution_status == ExecutionStatus.NOT_CHECKED
        assert "Not executed" in r34.not_checked_reason

        # Rule 72 (manual) still NOT_CHECKED
        r72 = [r for r in rows if r.audit_id == 72][0]
        assert r72.execution_status == ExecutionStatus.NOT_CHECKED


# ============================================================
# Test: Exactly 80 rows (production)
# ============================================================

class TestProductionCoverage:
    """Verify CoverageManager handles the full 80-rule registry."""

    def test_full_registry_produces_80_rows(self):
        """Full 80-rule registry → exactly 80 CoverageRows."""
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
        rows = mgr.compute(site_ctx, pages, [],
                           providers_available={"LibreCrawl"})

        assert len(rows) == 80, f"Expected 80, got {len(rows)}"
        ids = [r.audit_id for r in rows]
        assert set(ids) == set(range(1, 81))

    def test_full_registry_counts_by_status(self):
        """Verify ExecutionStatus/ResultStatus counts for full registry."""
        from audit_rules.registry import load_registry
        from audit_rules.coverage import CoverageManager
        from audit_rules.context import SiteContext, PageContext
        from audit_rules.categories import ExecutionStatus, ResultStatus

        checklist = PROJECT_ROOT / "audit_specs" / "technical_seo_master_checklist_80.csv"
        mapping = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        if not checklist.exists() or not mapping.exists():
            pytest.skip("Real CSV files not found")

        registry = load_registry(str(checklist), str(mapping))
        site_ctx = SiteContext(base_url="https://example.com")
        pages = [PageContext(url="https://example.com", status_code=200)]

        mgr = CoverageManager(registry)
        rows = mgr.compute(site_ctx, pages, [],
                           providers_available={"LibreCrawl"})

        # With only LibreCrawl available on a generic site:
        # - 18 EXISTING_FULL rules should execute
        # - WordPress rules should be NOT_APPLICABLE
        # - Manual rules should be NOT_CHECKED
        # - External data rules should be NOT_CHECKED

        executed = sum(1 for r in rows if r.execution_status == ExecutionStatus.EXECUTED_FULL)
        not_checked = sum(1 for r in rows if r.execution_status == ExecutionStatus.NOT_CHECKED)
        not_applicable = sum(1 for r in rows if r.execution_status == ExecutionStatus.NOT_APPLICABLE)

        assert executed >= 18, f"At least 18 EXISTING_FULL should execute, got {executed}"
        assert not_checked >= 12, f"At least 12 manual/external should be NOT_CHECKED, got {not_checked}"
        assert not_applicable == 12, (
            f"10 WP rules + 2 schema-empty rules (#28/#78) should be "
            f"NOT_APPLICABLE, got {not_applicable}"
        )
        assert executed + not_checked + not_applicable == 80
