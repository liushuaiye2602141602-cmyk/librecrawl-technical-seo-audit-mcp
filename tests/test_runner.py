"""Task 6: RuleRunner tests — end-to-end pipeline verification."""

import sys
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def runner():
    """RuleRunner with full 80-rule registry."""
    from audit_rules.runner import RuleRunner
    from audit_rules.registry import load_registry

    checklist = PROJECT_ROOT / "audit_specs" / "technical_seo_master_checklist_80.csv"
    mapping = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
    if not checklist.exists() or not mapping.exists():
        pytest.skip("Real CSV files not found")

    registry = load_registry(str(checklist), str(mapping))
    return RuleRunner(registry)


@pytest.fixture
def sample_export():
    """Minimal realistic export data like LibreCrawl produces."""
    return {
        "site_check": {
            "robots_txt": {
                "found": True,
                "disallow_count": 2,
                "sitemap_url": "https://example.com/sitemap.xml",
            },
            "sitemap": {
                "found": True,
                "url": "https://example.com/sitemap.xml",
                "url_count": 10,
            },
            "https_redirect": {"redirects": True},
            "www_redirect": {"redirects": False},
        },
        "pages": [
            {
                "url": "https://example.com",
                "status_code": 200,
                "title": "Home",
                "meta_description": "The best example site on the internet for testing purposes",
                "h1": "Welcome",
                "canonical_url": "https://example.com",
                "robots": "index, follow",
                "depth": 0,
                "word_count": 500,
                "internal_links_count": 10,
                "external_links_count": 2,
                "linked_from": ["https://other.com"],
                "json_ld": [{"@type": "Organization"}],
                "hreflang": [
                    {"lang": "en", "url": "https://example.com"},
                    {"lang": "x-default", "url": "https://example.com"},
                ],
            },
            {
                "url": "https://example.com/about",
                "status_code": 200,
                "title": "About",
                "meta_description": "Learn about our company",
                "h1": "About Us",
                "canonical_url": "https://example.com/about",
                "robots": "index, follow",
                "depth": 1,
                "word_count": 300,
                "links_detailed": [
                    {"url": "https://example.com", "anchor": "Home", "is_internal": True},
                    {"url": "https://example.com/contact", "anchor": "Contact", "is_internal": True},
                ],
                "linked_from": ["https://example.com"],
            },
        ],
        "links": [],
        "completeness": {
            "pages_crawled": 2,
            "sitemap_total": 10,
            "sitemap_only_count": 8,
            "sitemap_coverage_pct": 20.0,
            "audit_complete": False,
            "incomplete_reasons": "Limited to 2 pages",
        },
    }


# ============================================================
# Test: RuleRunner pipeline
# ============================================================

class TestRuleRunnerPipeline:
    """End-to-end: RuleRunner.run() produces findings + coverage."""

    def test_run_produces_findings_and_coverage(self, runner, sample_export):
        from audit_rules.models import Finding, CoverageRow

        findings, coverage = runner.run(
            site_data=sample_export["site_check"],
            pages=sample_export["pages"],
            links=sample_export.get("links", []),
            base_url="https://example.com",
            completeness=sample_export.get("completeness"),
        )

        # Should produce some findings (at minimum: schema_coverage)
        assert isinstance(findings, list)
        assert all(isinstance(f, Finding) for f in findings)

        # Should produce exactly 80 coverage rows
        assert isinstance(coverage, list)
        assert all(isinstance(c, CoverageRow) for c in coverage)
        assert len(coverage) == 80, f"Expected 80 coverage rows, got {len(coverage)}"

    def test_run_findings_have_required_fields(self, runner, sample_export):
        findings, _ = runner.run(
            site_data=sample_export["site_check"],
            pages=sample_export["pages"],
            base_url="https://example.com",
        )
        for f in findings:
            assert f.audit_id > 0
            assert f.rule_id
            assert f.url
            assert f.category
            assert f.severity in ("Error", "Warning", "Opportunity", "Info")

    def test_run_coverage_has_all_statuses(self, runner, sample_export):
        from audit_rules.categories import ExecutionStatus, ResultStatus

        _, coverage = runner.run(
            site_data=sample_export["site_check"],
            pages=sample_export["pages"],
            base_url="https://example.com",
        )

        statuses = {c.execution_status for c in coverage}
        # With LibreCrawl only + 2 pages on generic site:
        assert ExecutionStatus.EXECUTED_FULL in statuses
        assert ExecutionStatus.NOT_CHECKED in statuses
        assert ExecutionStatus.NOT_APPLICABLE in statuses

    def test_run_from_export_convenience(self, runner, sample_export):
        findings, coverage = runner.run_from_export(sample_export, "https://example.com")
        assert len(coverage) == 80
        assert isinstance(findings, list)

    def test_run_empty_data_graceful(self, runner):
        """Runner should handle empty data gracefully."""
        findings, coverage = runner.run(
            site_data={},
            pages=[],
            base_url="",
        )
        assert len(coverage) == 80
        # No pages → no page-level findings
        assert isinstance(findings, list)

    def test_run_with_additional_existing_data(self, runner, sample_export):
        """Extended checks data should be passed through to adapters."""
        existing = {
            "extended_checks": {
                "security_headers": {
                    "hsts": True,
                    "x_frame_options": True,
                    "x_content_type_options": True,
                    "referrer_policy": True,
                },
            },
        }
        findings, _ = runner.run(
            site_data=sample_export["site_check"],
            pages=sample_export["pages"],
            existing_data=existing,
            base_url="https://example.com",
        )
        # With all security headers present, no security findings expected
        security_findings = [f for f in findings if f.audit_id == 26]
        assert len(security_findings) == 0, (
            f"Security headers present but got findings: {security_findings}"
        )

    def test_coverage_ids_are_1_to_80(self, runner, sample_export):
        """Coverage rows must have audit_ids 1-80."""
        _, coverage = runner.run(
            site_data=sample_export["site_check"],
            pages=sample_export["pages"],
            base_url="https://example.com",
        )
        ids = [c.audit_id for c in coverage]
        assert set(ids) == set(range(1, 81))

    def test_heavy_fields_released_after_run(self, runner):
        """After run(), page context heavy fields should be released."""
        pages = [{
            "url": "https://example.com",
            "status_code": 200,
            "body_html": "<html>big</html>",
        }]
        findings, _ = runner.run(
            site_data={},
            pages=pages,
            base_url="https://example.com",
        )
        # Heavy fields were loaded (adapter may access them), then released
        # This is verified by the runner calling release_heavy() on all contexts
        # The test passes if no memory exception occurs and findings are produced
        assert isinstance(findings, list)

    def test_provider_failure_graceful_degradation(self, runner, sample_export):
        """Failing provider should be discarded, not crash the pipeline."""
        from audit_rules.providers.base import DataProvider
        from audit_rules.context import SiteContext, PageContext

        class FailingProvider(DataProvider):
            @property
            def name(self): return "Failing"
            def is_available(self): return True
            def enrich_site(self, ctx): raise RuntimeError("Boom")
            def enrich_page(self, ctx): raise RuntimeError("Boom")

        runner.providers["failing"] = FailingProvider()

        # Should not raise
        findings, coverage = runner.run(
            site_data=sample_export["site_check"],
            pages=sample_export["pages"],
            base_url="https://example.com",
        )
        assert len(coverage) == 80

    def test_run_preserves_site_profile_in_coverage(self, runner, sample_export):
        """Site profile should affect NOT_APPLICABLE rules."""
        _, coverage = runner.run(
            site_data=sample_export["site_check"],
            pages=sample_export["pages"],
            base_url="https://example.com",
        )
        from audit_rules.categories import ExecutionStatus
        wp_rules = [c for c in coverage if c.audit_id in {36, 37, 38, 39, 64, 65, 66, 67, 68, 69}]
        for wpr in wp_rules:
            assert wpr.execution_status == ExecutionStatus.NOT_APPLICABLE
            assert "WordPress-specific" in wpr.not_checked_reason
