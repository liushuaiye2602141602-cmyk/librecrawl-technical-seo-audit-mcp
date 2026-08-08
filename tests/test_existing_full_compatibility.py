"""Phase 1+2 compatibility harness tests.

Verifies that each of the 32 registered adapters (18 Phase 1 EXISTING_FULL +
14 Phase 2 local checks) produces Finding objects correctly.

Design constraints (Requirement 8):
  - Adapters use existing data structures (no reimplementation)
  - Do NOT modify existing check source files
  - Each adapter must have a test with positive and negative cases
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
def harness():
    """CompatibilityHarness with the full 80-rule registry."""
    from audit_rules.adapters import CompatibilityHarness
    from audit_rules.registry import load_registry

    checklist = PROJECT_ROOT / "audit_specs" / "technical_seo_master_checklist_80.csv"
    mapping = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
    if not checklist.exists() or not mapping.exists():
        pytest.skip("Real CSV files not found")

    registry = load_registry(str(checklist), str(mapping))
    return CompatibilityHarness(registry)


@pytest.fixture
def har_rule():
    """Look up a rule by audit_id from the harness."""
    from audit_rules.adapters import CompatibilityHarness
    from audit_rules.registry import load_registry

    checklist = PROJECT_ROOT / "audit_specs" / "technical_seo_master_checklist_80.csv"
    mapping = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
    if not checklist.exists() or not mapping.exists():
        pytest.skip("Real CSV files not found")

    registry = load_registry(str(checklist), str(mapping))

    def _get(audit_id: int):
        for r in registry:
            if r.audit_id == audit_id:
                return r
        raise ValueError(f"Rule {audit_id} not found")

    return _get


@pytest.fixture
def sample_site_ctx():
    from audit_rules.context import SiteContext
    return SiteContext(
        base_url="https://example.com",
        robots_txt_found=True,
        robots_txt_disallow_count=2,
        robots_txt_has_sitemap_declaration=True,
        sitemap_found=True,
        sitemap_url="https://example.com/sitemap.xml",
        sitemap_url_count=45,
        https_redirects=False,  # Will trigger domain_protocol finding
        www_redirects=False,
    )


@pytest.fixture
def sample_pages():
    from audit_rules.context import PageContext
    return [
        PageContext(
            url="https://example.com",
            status_code=200,
            title="Homepage",
            meta_description="A wonderful homepage for testing SEO audits",
            h1="Welcome",
            canonical_url="https://example.com",
            robots="index, follow",
            depth=0,
            word_count=500,
            internal_links_count=15,
            external_links_count=3,
            linked_from_count=5,
            json_ld_types=["Organization", "BreadcrumbList"],
            hreflang_summary=[
                {"lang": "en", "url": "https://example.com"},
                {"lang": "x-default", "url": "https://example.com"},
            ],
        ),
        PageContext(
            url="https://example.com/about",
            status_code=200,
            title="About Us",
            meta_description="",
            h1="About Our Company",
            canonical_url="https://example.com/about",
            robots="index, follow",
            depth=1,
            word_count=300,
            internal_links_count=5,
            external_links_count=0,
            linked_from_count=2,
            json_ld_types=None,
            hreflang_summary=[
                {"lang": "en", "url": "https://example.com/about"},
                # Missing x-default
            ],
        ),
        PageContext(
            url="https://example.com/deep/old/page",
            status_code=200,
            depth=6,
            word_count=25,
            title="Old Page",
            meta_description=None,
            h1=None,
            canonical_url=None,
            internal_links_count=0,
            external_links_count=0,
            linked_from_count=0,
        ),
        PageContext(
            url="https://example.com/404-page",
            status_code=404,
            linked_from_count=3,
        ),
        PageContext(
            url="https://example.com/blocked",
            status_code=200,
            robots="noindex, nofollow",
            depth=1,
            word_count=200,
            h1="Blocked",
            title="Blocked Page",
        ),
    ]


# ============================================================
# Test: All 18 adapters registered
# ============================================================

class TestAdapterRegistration:
    """Verify all Phase 1 (18) + Phase 2 (13) + Phase 3 (8) rules have registered adapters.

    Rule 40 (audit_deliverables) is handled at the integration level,
    not as a per-rule adapter — generate_task_csv() has a different signature.
    """

    PHASE1_IDS = {1, 3, 4, 6, 7, 8, 9, 11, 14, 15, 26, 27, 29, 30, 41, 42, 45, 58}
    # Rule 40 (audit_deliverables) is NOT an adapter — generate_task_csv()
    # is called from integration.py with a different signature
    PHASE2_IDS = {10, 12, 16, 17, 28, 37, 38, 49, 50, 59, 70, 78, 79}
    PHASE3_IDS = {19, 20, 21, 22, 24, 61, 62, 63}
    PHASE4A_IDS = {18, 32, 39, 43, 47, 51, 60, 67}
    PHASE4B_IDS = {74}
    PHASE4C_IDS = {2, 5, 13, 23, 25, 40, 66}
    PHASE5_IDS = {44, 52, 75, 76}
    PHASE6_IDS = {31, 77}
    PHASE7_IDS = {34, 35}
    PHASE8_IDS = {33}
    PHASE9_IDS = {36, 64, 65, 68, 69}
    ALL_ADAPTER_IDS = (
        PHASE1_IDS | PHASE2_IDS | PHASE3_IDS | PHASE4A_IDS | PHASE4B_IDS |
        PHASE4C_IDS | PHASE5_IDS | PHASE6_IDS | PHASE7_IDS | PHASE8_IDS |
        PHASE9_IDS
    )  # 69 rules with adapters

    def test_all_adapters_registered(self, harness):
        """Each rule with an adapter must have it registered (32 total)."""
        for audit_id in self.ALL_ADAPTER_IDS:
            rule = None
            for r in harness.registry:
                if r.audit_id == audit_id:
                    rule = r
                    break
            assert rule is not None, f"Rule {audit_id} not in registry"
            assert rule.rule_id in harness._adapters, (
                f"Rule {audit_id} ({rule.rule_id}) missing adapter"
            )

    def test_no_extra_adapters(self, harness):
        """Only the explicitly implemented Phase 1 through 4B rules have adapters."""
        for rule in harness.registry:
            if rule.audit_id in self.ALL_ADAPTER_IDS:
                continue
            assert rule.rule_id not in harness._adapters, (
                f"Unexpected rule {rule.audit_id} ({rule.rule_id}) has adapter"
            )

    def test_phase2_count(self, harness):
        """Exactly 13 Phase 2 adapters are registered (Rule 40 is integration-level)."""
        phase2_in_adapters = [
            rule_id for rule_id in harness._adapters
            if any(r.audit_id in self.PHASE2_IDS for r in harness.registry
                   if r.rule_id == rule_id)
        ]
        assert len(phase2_in_adapters) == 13, (
            f"Expected 13 Phase 2 adapters, got {len(phase2_in_adapters)}"
        )

    def test_total_adapter_count(self, harness):
        """Exactly 48 adapters total through Phase 4B."""
        assert len(harness._adapters) == 69, (
            f"Expected 69 total adapters, got {len(harness._adapters)}"
        )


# ============================================================
# Test: Individual adapter behavior
# ============================================================

class TestAdapterRobotsTxt:
    """Rule 1: robots.txt existence + rules."""

    def test_robots_txt_missing_finding(self, har_rule, sample_site_ctx, sample_pages):
        from audit_rules.adapters import _adapter_robots_txt
        site_ctx = sample_site_ctx
        site_ctx.robots_txt_found = False
        findings = _adapter_robots_txt(har_rule(1), site_ctx, sample_pages, {})
        assert len(findings) >= 1
        assert "not found" in findings[0].finding_detail.lower()

    def test_robots_txt_ok_no_finding(self, har_rule, sample_site_ctx, sample_pages):
        from audit_rules.adapters import _adapter_robots_txt
        findings = _adapter_robots_txt(har_rule(1), sample_site_ctx, sample_pages, {})
        # robots_txt_found=True, disallow_count=2 (<5) → no finding
        assert len(findings) == 0

    def test_high_disallow_finding(self, har_rule, sample_site_ctx, sample_pages):
        from audit_rules.adapters import _adapter_robots_txt
        site_ctx = sample_site_ctx
        site_ctx.robots_txt_disallow_count = 10
        findings = _adapter_robots_txt(har_rule(1), site_ctx, sample_pages, {})
        assert len(findings) >= 1
        assert "disallow" in findings[0].finding_detail.lower()


class TestAdapterNoindex:
    """Rule 3: noindex/nofollow check."""

    def test_noindex_on_shallow_page(self, har_rule, sample_site_ctx, sample_pages):
        from audit_rules.adapters import _adapter_noindex_nofollow
        findings = _adapter_noindex_nofollow(har_rule(3), sample_site_ctx, sample_pages, {})
        # blocked page at depth=1 with noindex → finding
        noindex_findings = [f for f in findings if "blocked" in f.url]
        assert len(noindex_findings) >= 1

    def test_indexable_pages_no_finding(self, har_rule, sample_site_ctx):
        from audit_rules.context import PageContext
        from audit_rules.adapters import _adapter_noindex_nofollow
        pages = [PageContext(url="https://x.com", status_code=200, robots="index, follow", depth=1)]
        findings = _adapter_noindex_nofollow(har_rule(3), sample_site_ctx, pages, {})
        assert len(findings) == 0


class TestAdapterCrawlErrors:
    """Rule 4: crawl errors (4xx/5xx)."""

    def test_404_page_finding(self, har_rule, sample_site_ctx, sample_pages):
        from audit_rules.adapters import _adapter_crawl_errors
        findings = _adapter_crawl_errors(har_rule(4), sample_site_ctx, sample_pages, {})
        error_findings = [f for f in findings if "404" in f.url]
        assert len(error_findings) >= 1

    def test_all_200_no_finding(self, har_rule, sample_site_ctx):
        from audit_rules.context import PageContext
        from audit_rules.adapters import _adapter_crawl_errors
        pages = [PageContext(url="https://x.com", status_code=200)]
        findings = _adapter_crawl_errors(har_rule(4), sample_site_ctx, pages, {})
        assert len(findings) == 0


class TestAdapterDomainProtocol:
    """Rule 6: unified domain + protocol."""

    def test_no_https_redirect_finding(self, har_rule, sample_site_ctx, sample_pages):
        from audit_rules.adapters import _adapter_domain_protocol
        findings = _adapter_domain_protocol(har_rule(6), sample_site_ctx, sample_pages, {})
        assert len(findings) >= 1
        assert "https" in findings[0].finding_detail.lower()


class TestAdapterCanonical:
    """Rule 8: canonical correctness."""

    def test_missing_canonical_finding(self, har_rule, sample_site_ctx, sample_pages):
        from audit_rules.adapters import _adapter_canonical
        findings = _adapter_canonical(har_rule(8), sample_site_ctx, sample_pages, {})
        missing = [f for f in findings if "no canonical" in f.detected_value.lower()]
        assert len(missing) >= 1


class TestAdapterClickDepth:
    """Rule 9: click depth."""

    def test_deep_page_finding(self, har_rule, sample_site_ctx, sample_pages):
        from audit_rules.adapters import _adapter_click_depth
        findings = _adapter_click_depth(har_rule(9), sample_site_ctx, sample_pages, {})
        deep = [f for f in findings if "deep/old" in f.url]
        assert len(deep) >= 1

    def test_shallow_pages_no_finding(self, har_rule, sample_site_ctx):
        from audit_rules.context import PageContext
        from audit_rules.adapters import _adapter_click_depth
        pages = [PageContext(url="https://x.com", depth=2)]
        findings = _adapter_click_depth(har_rule(9), sample_site_ctx, pages, {})
        assert len(findings) == 0


class TestAdapterInternalLinks:
    """Rule 11: internal link distribution."""

    def test_zero_inbound_finding(self, har_rule, sample_site_ctx, sample_pages):
        from audit_rules.adapters import _adapter_internal_links
        findings = _adapter_internal_links(har_rule(11), sample_site_ctx, sample_pages, {})
        orphan = [f for f in findings if "deep/old" in f.url]
        assert len(orphan) >= 1

    def test_normal_page_no_finding(self, har_rule, sample_site_ctx):
        from audit_rules.context import PageContext
        from audit_rules.adapters import _adapter_internal_links
        pages = [PageContext(
            url="https://x.com", status_code=200,
            internal_links_count=5, linked_from_count=5,
        )]
        findings = _adapter_internal_links(har_rule(11), sample_site_ctx, pages, {})
        assert len(findings) == 0


class TestAdapterMetaDescription:
    """Rule 14: meta description audit."""

    def test_missing_meta_finding(self, har_rule, sample_site_ctx, sample_pages):
        from audit_rules.adapters import _adapter_meta_description
        findings = _adapter_meta_description(har_rule(14), sample_site_ctx, sample_pages, {})
        assert len(findings) >= 2  # about (empty) + deep/old (None)


class TestAdapterH1Headings:
    """Rule 15: H1 heading hierarchy."""

    def test_missing_h1_finding(self, har_rule, sample_site_ctx, sample_pages):
        from audit_rules.adapters import _adapter_h1_headings
        findings = _adapter_h1_headings(har_rule(15), sample_site_ctx, sample_pages, {})
        missing = [f for f in findings if "deep/old" in f.url]
        assert len(missing) >= 1


class TestAdapterSoft404:
    """Rule 41: soft 404 detection."""

    def test_thin_content_finding(self, har_rule, sample_site_ctx, sample_pages):
        from audit_rules.adapters import _adapter_soft_404
        findings = _adapter_soft_404(har_rule(41), sample_site_ctx, sample_pages, {})
        thin = [f for f in findings if "deep/old" in f.url]
        assert len(thin) >= 1

    def test_normal_content_no_finding(self, har_rule, sample_site_ctx):
        from audit_rules.context import PageContext
        from audit_rules.adapters import _adapter_soft_404
        pages = [PageContext(url="https://x.com", status_code=200, word_count=500)]
        findings = _adapter_soft_404(har_rule(41), sample_site_ctx, pages, {})
        assert len(findings) == 0


class TestAdapterOrphanPages:
    """Rule 45: orphan pages."""

    def test_orphan_finding(self, har_rule, sample_site_ctx, sample_pages):
        from audit_rules.adapters import _adapter_orphan_pages
        findings = _adapter_orphan_pages(har_rule(45), sample_site_ctx, sample_pages, {})
        orphan = [f for f in findings if "deep/old" in f.url]
        assert len(orphan) >= 1

    def test_connected_page_no_finding(self, har_rule, sample_site_ctx):
        from audit_rules.context import PageContext
        from audit_rules.adapters import _adapter_orphan_pages
        pages = [PageContext(
            url="https://x.com", status_code=200,
            linked_from_count=3, internal_links_count=5,
        )]
        findings = _adapter_orphan_pages(har_rule(45), sample_site_ctx, pages, {})
        assert len(findings) == 0


class TestAdapterBrokenLinks:
    """Rule 30: broken internal links."""

    def test_broken_with_inlinks_finding(self, har_rule, sample_site_ctx, sample_pages):
        from audit_rules.adapters import _adapter_broken_links
        findings = _adapter_broken_links(har_rule(30), sample_site_ctx, sample_pages, {})
        broken = [f for f in findings if "404" in f.url]
        assert len(broken) >= 1

    def test_broken_no_inlinks_no_finding(self, har_rule, sample_site_ctx):
        from audit_rules.context import PageContext
        from audit_rules.adapters import _adapter_broken_links
        pages = [PageContext(url="https://x.com/404", status_code=404, linked_from_count=0)]
        findings = _adapter_broken_links(har_rule(30), sample_site_ctx, pages, {})
        assert len(findings) == 0


class TestAdapterHreflang:
    """Rules 29 + 58: hreflang basics + indexability."""

    def test_missing_x_default_finding(self, har_rule, sample_site_ctx, sample_pages):
        from audit_rules.adapters import _adapter_hreflang_basics
        findings = _adapter_hreflang_basics(har_rule(29), sample_site_ctx, sample_pages, {})
        missing_xd = [f for f in findings if "about" in f.url]
        assert len(missing_xd) >= 1

    def test_no_hreflang_no_finding(self, har_rule, sample_site_ctx):
        from audit_rules.context import PageContext
        from audit_rules.adapters import _adapter_hreflang_basics
        pages = [PageContext(url="https://x.com", status_code=200)]
        findings = _adapter_hreflang_basics(har_rule(29), sample_site_ctx, pages, {})
        assert len(findings) == 0


class TestAdapterSchemaCoverage:
    """Rule 27: schema type coverage."""

    def test_low_schema_coverage_finding(self, har_rule, sample_site_ctx, sample_pages):
        from audit_rules.adapters import _adapter_schema_coverage
        findings = _adapter_schema_coverage(har_rule(27), sample_site_ctx, sample_pages, {})
        # 1/3 200 pages have schema (<30%) → finding
        assert len(findings) >= 1

    def test_good_coverage_no_finding(self, har_rule, sample_site_ctx):
        from audit_rules.context import PageContext
        from audit_rules.adapters import _adapter_schema_coverage
        pages = [
            PageContext(url="https://x.com/page1", status_code=200, json_ld_types=["Organization"]),
            PageContext(url="https://x.com/page2", status_code=200, json_ld_types=["Article"]),
            PageContext(url="https://x.com/page3", status_code=200, json_ld_types=["BreadcrumbList"]),
        ]
        findings = _adapter_schema_coverage(har_rule(27), sample_site_ctx, pages, {})
        assert len(findings) == 0


# ============================================================
# Test: harness.run integration
# ============================================================

class TestHarnessIntegration:
    """Verify the harness.run() orchestrator."""

    def test_run_produces_findings(self, harness, sample_site_ctx, sample_pages):
        """harness.run() with realistic data produces findings."""
        findings = harness.run(sample_site_ctx, sample_pages, {})
        assert len(findings) > 0, "Expected at least some findings from 18 adapters"

        # Verify all findings have required fields
        for f in findings:
            assert f.audit_id > 0
            assert f.rule_id
            assert f.category
            assert f.severity

    def test_run_perfect_site_no_issues(self, harness):
        """A perfect site should have zero ERROR/WARNING/OPPORTUNITY findings.

        INFO-severity findings (coverage gap documentation) are acceptable
        — they document what CANNOT be checked with available data, and
        are not actual audit issues.
        """
        from audit_rules.context import SiteContext, PageContext
        perfect_site = SiteContext(
            base_url="https://perfect.com",
            robots_txt_found=True,
            robots_txt_disallow_count=2,
            https_redirects=True,
            www_redirects=False,
            sitemap_found=True,
        )
        perfect_pages = [
            PageContext(
                url="https://perfect.com",
                status_code=200,
                title="Perfect Site",
                meta_description="A perfectly optimized site demonstrating all SEO best practices for maximum search engine visibility",
                h1="Perfect",
                canonical_url="https://perfect.com",
                robots="index, follow",
                depth=0,
                word_count=500,
                internal_links_count=10,
                external_links_count=2,
                linked_from_count=5,
                json_ld_types=["Organization", "BreadcrumbList"],
                hreflang_summary=[
                    {"lang": "en", "url": "https://perfect.com"},
                    {"lang": "x-default", "url": "https://perfect.com"},
                ],
            ),
        ]
        findings = harness.run(perfect_site, perfect_pages, {})
        # Filter out INFO-severity findings (coverage gap documentation)
        actionable = [f for f in findings if f.severity.lower() != "info"]
        assert len(actionable) == 0, (
            f"Expected 0 actionable findings for perfect site, "
            f"got {len(actionable)}: "
            f"{[(f.rule_id, f.severity, f.detected_value[:80]) for f in actionable]}"
        )

    def test_each_adapter_is_callable(self, harness, sample_site_ctx, sample_pages):
        """Each registered adapter function must be callable."""
        from audit_rules.adapters import DataUnavailableError

        for rule_id, adapter in harness._adapters.items():
            rule = None
            for r in harness.registry:
                if r.rule_id == rule_id:
                    rule = r
                    break
            assert rule is not None
            try:
                result = adapter(rule, sample_site_ctx, sample_pages, {})
            except DataUnavailableError:
                continue
            assert isinstance(result, list)
