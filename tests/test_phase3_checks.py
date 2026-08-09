"""Phase 3 — Performance Check TDD Tests.

Verifies all 8 performance rule checks (19 CWV, 20 TTFB, 21 Render Blocking,
22 Image Optimization, 24 Mobile Experience, 61 Field vs Lab, 62 Third-Party,
63 Font/CLS) with mock PSI fixtures.

Design:
  - No real HTTP — all data from fixtures/psi/ mock PerformanceSnapshots.
  - Covers: positive (finds issues), negative (clean page), edge, false-positive.
  - Verifies field/lab separation, origin vs URL scope, INP vs TBT distinction.
  - Adapter counts updated: 18 P1 + 13 P2 + 8 P3 = 39 total.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Helpers
# ============================================================

def _get_rule(registry, audit_id: int):
    """Get a RuleDefinition from registry by audit_id."""
    for r in registry:
        if r.audit_id == audit_id:
            return r
    raise ValueError(f"Rule {audit_id} not found in registry")


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="module")
def registry():
    """Load the real 80-rule registry."""
    from audit_rules.registry import load_registry
    return load_registry()


@pytest.fixture
def good_snap():
    from tests.fixtures.psi import make_good_mobile
    return make_good_mobile()


@pytest.fixture
def poor_snap():
    from tests.fixtures.psi import make_poor_mobile
    return make_poor_mobile()


@pytest.fixture
def no_field_snap():
    from tests.fixtures.psi import make_no_field_data
    return make_no_field_data()


@pytest.fixture
def origin_only_snap():
    from tests.fixtures.psi import make_origin_field_only
    return make_origin_field_only()


@pytest.fixture
def partial_lh_snap():
    from tests.fixtures.psi import make_partial_lighthouse
    return make_partial_lighthouse()


@pytest.fixture
def error_snap():
    from tests.fixtures.psi import make_api_error
    return make_api_error()


@pytest.fixture
def tp_heavy_snap():
    from tests.fixtures.psi import make_third_party_heavy
    return make_third_party_heavy()


@pytest.fixture
def image_heavy_snap():
    from tests.fixtures.psi import make_image_heavy
    return make_image_heavy()


@pytest.fixture
def cls_font_snap():
    from tests.fixtures.psi import make_cls_font_issue
    return make_cls_font_issue()


@pytest.fixture
def data_with_snaps():
    def _build(*snapshots, strategy="mobile"):
        from tests.fixtures.psi import make_data_dict
        return make_data_dict(list(snapshots), strategy)
    return _build


@pytest.fixture
def site_ctx():
    from tests.fixtures.psi import make_site_context
    return make_site_context()


@pytest.fixture
def pages():
    from tests.fixtures.psi import make_page_contexts
    return make_page_contexts


# ============================================================
# Rule 19 — Core Web Vitals
# ============================================================

class TestCoreWebVitals:

    def test_all_good_url_level_no_finding(self, registry, site_ctx, pages, data_with_snaps, good_snap):
        from audit_rules.checks.performance import check_core_web_vitals
        rule = _get_rule(registry, 19)
        data = data_with_snaps(good_snap)
        findings = check_core_web_vitals(rule, site_ctx, pages([good_snap.url]), data)
        actionable = [f for f in findings if str(f.severity) not in ("Info", "Opportunity")]
        assert len(actionable) == 0, (
            f"Expected no actionable findings for GOOD CWV, got: "
            f"{[(f.detected_value, f.severity) for f in actionable]}"
        )

    def test_poor_url_level_error(self, registry, site_ctx, pages, data_with_snaps, poor_snap):
        from audit_rules.checks.performance import check_core_web_vitals
        rule = _get_rule(registry, 19)
        data = data_with_snaps(poor_snap)
        findings = check_core_web_vitals(rule, site_ctx, pages([poor_snap.url]), data)
        errors = [f for f in findings if str(f.severity) == "Error"]
        assert len(errors) >= 1, f"Expected ERROR for POOR CWV, got {len(errors)}"

    def test_no_field_data_info_only(self, registry, site_ctx, pages, data_with_snaps, no_field_snap):
        from audit_rules.checks.performance import check_core_web_vitals
        rule = _get_rule(registry, 19)
        data = data_with_snaps(no_field_snap)
        findings = check_core_web_vitals(rule, site_ctx, pages([no_field_snap.url]), data)
        errors = [f for f in findings if str(f.severity) == "Error"]
        warnings = [f for f in findings if str(f.severity) == "Warning"]
        assert len(errors) == 0, "No field data must NOT produce ERROR"
        assert len(warnings) == 0, "No field data with good lab must NOT be WARNING"

    def test_origin_only_partial(self, registry, site_ctx, pages, data_with_snaps, origin_only_snap):
        from audit_rules.checks.performance import check_core_web_vitals
        rule = _get_rule(registry, 19)
        data = data_with_snaps(origin_only_snap)
        findings = check_core_web_vitals(rule, site_ctx, pages([origin_only_snap.url]), data)
        assert len(findings) >= 1
        assert findings[0].confidence < 0.95, f"Origin-only should have low confidence, got {findings[0].confidence}"
        assert "origin" in findings[0].finding_detail.lower()

    def test_api_error_info_not_error(self, registry, site_ctx, pages, data_with_snaps, error_snap):
        from audit_rules.checks.performance import check_core_web_vitals
        rule = _get_rule(registry, 19)
        data = data_with_snaps(error_snap)
        findings = check_core_web_vitals(rule, site_ctx, pages([error_snap.url]), data)
        errors = [f for f in findings if str(f.severity) == "Error"]
        assert len(errors) == 0, "PSI errors must not be SEO ERRORs"

    def test_needs_improvement_warning(self, registry, site_ctx, pages, data_with_snaps):
        from audit_rules.checks.performance import check_core_web_vitals
        from tests.fixtures.psi import PerformanceSnapshot
        snap = PerformanceSnapshot(
            url="https://example.com/medium", strategy="mobile",
            psi_status="success",
            field_data_available=True, field_data_scope="URL",
            field_lcp_ms=3000.0, field_lcp_category="AVERAGE",
            field_inp_ms=250.0, field_inp_category="AVERAGE",
            field_cls=0.15, field_cls_category="AVERAGE",
        )
        rule = _get_rule(registry, 19)
        data = data_with_snaps(snap)
        findings = check_core_web_vitals(rule, site_ctx, pages([snap.url]), data)
        warnings = [f for f in findings if str(f.severity) == "Warning"]
        assert len(warnings) >= 1, f"Expected WARNING, got {len(warnings)}"


# ============================================================
# Rule 20 — TTFB
# ============================================================

class TestTTFB:

    def test_good_ttfb_no_finding(self, registry, site_ctx, pages, data_with_snaps, good_snap):
        from audit_rules.checks.performance import check_ttfb
        rule = _get_rule(registry, 20)
        data = data_with_snaps(good_snap)
        findings = check_ttfb(rule, site_ctx, pages([good_snap.url]), data)
        assert len(findings) == 0, f"Expected no findings for good TTFB, got {len(findings)}"

    def test_high_ttfb_opportunity(self, registry, site_ctx, pages, data_with_snaps):
        from audit_rules.checks.performance import check_ttfb
        from tests.fixtures.psi import PerformanceSnapshot
        snap = PerformanceSnapshot(
            url="https://example.com/slow-ttfb", strategy="mobile",
            psi_status="success", field_data_available=True, field_data_scope="URL",
            field_ttfb_ms=1500.0, field_ttfb_category="SLOW",
        )
        rule = _get_rule(registry, 20)
        data = data_with_snaps(snap)
        findings = check_ttfb(rule, site_ctx, pages([snap.url]), data)
        assert len(findings) >= 1
        assert "TTFB" in findings[0].detected_value

    def test_lab_ttfb_lower_confidence(self, registry, site_ctx, pages, data_with_snaps, no_field_snap):
        from audit_rules.checks.performance import check_ttfb
        from audit_rules.adapters import DataUnavailableError
        rule = _get_rule(registry, 20)
        data = data_with_snaps(no_field_snap)
        # Lab-only evidence (no field TTFB) must NOT produce a TTFB finding;
        # Lighthouse LCP is not TTFB. The rule reports a data gap instead.
        try:
            check_ttfb(rule, site_ctx, pages([no_field_snap.url]), data)
        except DataUnavailableError:
            return
        raise AssertionError("check_ttfb must raise DataUnavailableError without field TTFB")


# ============================================================
# Rule 21 — Render-Blocking Resources
# ============================================================

class TestRenderBlocking:

    def test_clean_page_no_finding(self, registry, site_ctx, pages, data_with_snaps, good_snap):
        from audit_rules.checks.performance import check_render_blocking
        rule = _get_rule(registry, 21)
        data = data_with_snaps(good_snap)
        findings = check_render_blocking(rule, site_ctx, pages([good_snap.url]), data)
        assert len(findings) == 0, f"Expected no findings, got {len(findings)}"

    def test_blocking_resources_warning(self, registry, site_ctx, pages, data_with_snaps, poor_snap):
        from audit_rules.checks.performance import check_render_blocking
        rule = _get_rule(registry, 21)
        data = data_with_snaps(poor_snap)
        findings = check_render_blocking(rule, site_ctx, pages([poor_snap.url]), data)
        assert len(findings) >= 1
        assert any("render-blocking" in f.detected_value.lower() for f in findings)

    def test_unused_css_opportunity(self, registry, site_ctx, pages, data_with_snaps, poor_snap):
        from audit_rules.checks.performance import check_render_blocking
        rule = _get_rule(registry, 21)
        data = data_with_snaps(poor_snap)
        findings = check_render_blocking(rule, site_ctx, pages([poor_snap.url]), data)
        css = [f for f in findings if "css" in f.evidence.lower() or "unused CSS" in f.detected_value.lower()]
        assert len(css) >= 1, f"Expected unused CSS finding, got {[f.detected_value for f in findings]}"

    def test_api_error_skipped(self, registry, site_ctx, pages, data_with_snaps, error_snap):
        from audit_rules.checks.performance import check_render_blocking
        rule = _get_rule(registry, 21)
        data = data_with_snaps(error_snap)
        findings = check_render_blocking(rule, site_ctx, pages([error_snap.url]), data)
        assert len(findings) == 0, "PSI errors should be silently skipped"


# ============================================================
# Rule 22 — Image Optimization
# ============================================================

class TestImageOptimization:

    def test_clean_page_no_finding(self, registry, site_ctx, pages, data_with_snaps, good_snap):
        from audit_rules.checks.performance import check_image_performance
        rule = _get_rule(registry, 22)
        data = data_with_snaps(good_snap)
        findings = check_image_performance(rule, site_ctx, pages([good_snap.url]), data)
        assert len(findings) == 0

    def test_oversized_images_opportunity(self, registry, site_ctx, pages, data_with_snaps, image_heavy_snap):
        from audit_rules.checks.performance import check_image_performance
        rule = _get_rule(registry, 22)
        data = data_with_snaps(image_heavy_snap)
        findings = check_image_performance(rule, site_ctx, pages([image_heavy_snap.url]), data)
        assert len(findings) >= 1
        assert any("image" in f.detected_value.lower() for f in findings)

    def test_lcp_image_not_lazy_load(self, registry, site_ctx, pages, data_with_snaps, image_heavy_snap):
        from audit_rules.checks.performance import check_image_performance
        rule = _get_rule(registry, 22)
        data = data_with_snaps(image_heavy_snap)
        findings = check_image_performance(rule, site_ctx, pages([image_heavy_snap.url]), data)
        for f in findings:
            if "lcp" in f.detected_value.lower() and "lazy" in f.detected_value.lower():
                pytest.fail(f"LCP image should never get lazy-load recommendation: {f.detected_value}")

    def test_opportunity_tagged_pagespeed_lab(self, registry, site_ctx, pages, data_with_snaps, image_heavy_snap):
        from audit_rules.checks.performance import check_image_performance
        rule = _get_rule(registry, 22)
        data = data_with_snaps(image_heavy_snap)
        findings = check_image_performance(rule, site_ctx, pages([image_heavy_snap.url]), data)
        for f in findings:
            assert "[pagespeed_lab]" in f.detected_value or "pagespeed_lab" in f.evidence, (
                f"Image finding must be tagged: {f.detected_value}"
            )


# ============================================================
# Rule 24 — Mobile Experience
# ============================================================

class TestMobileExperience:

    def test_good_mobile_no_finding(self, registry, site_ctx, pages, data_with_snaps, good_snap):
        from audit_rules.checks.performance import check_mobile_experience
        rule = _get_rule(registry, 24)
        data = data_with_snaps(good_snap)
        findings = check_mobile_experience(rule, site_ctx, pages([good_snap.url]), data)
        assert len(findings) == 0, f"Expected no findings, got {len(findings)}"

    def test_poor_mobile_warning(self, registry, site_ctx, pages, data_with_snaps, poor_snap):
        from audit_rules.checks.performance import check_mobile_experience
        rule = _get_rule(registry, 24)
        data = data_with_snaps(poor_snap)
        findings = check_mobile_experience(rule, site_ctx, pages([poor_snap.url]), data)
        assert len(findings) >= 1
        assert "mobile" in findings[0].detected_value.lower()

    def test_desktop_strategy_no_finding(self, registry, site_ctx, pages, data_with_snaps, poor_snap):
        from audit_rules.checks.performance import check_mobile_experience
        rule = _get_rule(registry, 24)
        data = data_with_snaps(poor_snap, strategy="desktop")
        findings = check_mobile_experience(rule, site_ctx, pages([poor_snap.url]), data)
        assert len(findings) == 0, "Mobile check should return nothing for desktop strategy"


# ============================================================
# Rule 61 — Field vs Lab Data
# ============================================================

class TestFieldVsLab:

    def test_both_available_reports_discrepancy(self, registry, site_ctx, pages, data_with_snaps, poor_snap):
        from audit_rules.checks.performance import check_field_vs_lab
        rule = _get_rule(registry, 61)
        data = data_with_snaps(poor_snap)
        findings = check_field_vs_lab(rule, site_ctx, pages([poor_snap.url]), data)
        assert len(findings) >= 1

    def test_inp_and_tbt_not_conflated(self, registry, site_ctx, pages, data_with_snaps, poor_snap):
        from audit_rules.checks.performance import check_field_vs_lab
        rule = _get_rule(registry, 61)
        data = data_with_snaps(poor_snap)
        findings = check_field_vs_lab(rule, site_ctx, pages([poor_snap.url]), data)
        for f in findings:
            detail = f.finding_detail.lower()
            if "inp" in detail and "tbt" in detail:
                assert "different" in detail, f"INP vs TBT must state they differ: {detail[:200]}"

    def test_no_field_data_info(self, registry, site_ctx, pages, data_with_snaps, no_field_snap):
        from audit_rules.checks.performance import check_field_vs_lab
        rule = _get_rule(registry, 61)
        data = data_with_snaps(no_field_snap)
        findings = check_field_vs_lab(rule, site_ctx, pages([no_field_snap.url]), data)
        assert len(findings) >= 1
        assert any(str(f.severity) == "Info" for f in findings), "Missing field data → INFO"

    def test_lcp_discrepancy_detected(self, registry, site_ctx, pages, data_with_snaps):
        from audit_rules.checks.performance import check_field_vs_lab
        from tests.fixtures.psi import PerformanceSnapshot
        snap = PerformanceSnapshot(
            url="https://example.com/lcp-gap", strategy="mobile",
            psi_status="success", field_data_available=True, field_data_scope="URL",
            field_lcp_ms=4500.0, field_inp_ms=150.0, field_cls=0.05,
            lab_performance_score=90, lab_lcp_ms=2000.0,
            lab_tbt_ms=100.0, lab_cls=0.03,
        )
        rule = _get_rule(registry, 61)
        data = data_with_snaps(snap)
        findings = check_field_vs_lab(rule, site_ctx, pages([snap.url]), data)
        assert any("LCP" in f.detected_value for f in findings), (
            f"Should detect large LCP discrepancy: {[f.detected_value for f in findings]}"
        )


# ============================================================
# Rule 62 — Third-Party Scripts
# ============================================================

class TestThirdPartyScripts:

    def test_clean_page_no_finding(self, registry, site_ctx, pages, data_with_snaps, good_snap):
        from audit_rules.checks.performance import check_third_party_scripts
        rule = _get_rule(registry, 62)
        data = data_with_snaps(good_snap)
        findings = check_third_party_scripts(rule, site_ctx, pages([good_snap.url]), data)
        assert len(findings) == 0

    def test_heavy_third_party_warning(self, registry, site_ctx, pages, data_with_snaps, tp_heavy_snap):
        from audit_rules.checks.performance import check_third_party_scripts
        rule = _get_rule(registry, 62)
        data = data_with_snaps(tp_heavy_snap)
        findings = check_third_party_scripts(rule, site_ctx, pages([tp_heavy_snap.url]), data)
        assert len(findings) >= 1
        assert any("third-party" in f.detected_value.lower() for f in findings)

    def test_ga_not_false_positive(self, registry, site_ctx, pages, data_with_snaps):
        from audit_rules.checks.performance import check_third_party_scripts
        from tests.fixtures.psi import PerformanceSnapshot, ThirdPartyEntity
        snap = PerformanceSnapshot(
            url="https://example.com", strategy="mobile",
            psi_status="success", field_data_available=False, field_data_scope="NONE",
            lab_performance_score=80,
            third_party_transfer_bytes=50000, third_party_main_thread_ms=80,
            third_party_entities=[
                ThirdPartyEntity(
                    domain="www.googletagmanager.com", provider="Google Tag Manager",
                    transfer_bytes=50000, main_thread_ms=80, blocking_time_ms=20,
                ),
            ],
        )
        rule = _get_rule(registry, 62)
        data = data_with_snaps(snap)
        findings = check_third_party_scripts(rule, site_ctx, pages([snap.url]), data)
        assert len(findings) == 0, "GTM alone with low impact should not flag"

    def test_main_thread_cost_highlighted(self, registry, site_ctx, pages, data_with_snaps, tp_heavy_snap):
        from audit_rules.checks.performance import check_third_party_scripts
        rule = _get_rule(registry, 62)
        data = data_with_snaps(tp_heavy_snap)
        findings = check_third_party_scripts(rule, site_ctx, pages([tp_heavy_snap.url]), data)
        for f in findings:
            assert "main_thread" in f.evidence or "main thread" in f.finding_detail.lower(), (
                f"Third-party finding must mention main-thread cost: {f.detected_value}"
            )


# ============================================================
# Rule 63 — Font Loading / CLS
# ============================================================

class TestFontCLS:

    def test_clean_page_no_finding(self, registry, site_ctx, pages, data_with_snaps, good_snap):
        from audit_rules.checks.performance import check_font_cls
        rule = _get_rule(registry, 63)
        data = data_with_snaps(good_snap)
        findings = check_font_cls(rule, site_ctx, pages([good_snap.url]), data)
        assert len(findings) == 0

    def test_missing_font_display_warning(self, registry, site_ctx, pages, data_with_snaps, cls_font_snap):
        from audit_rules.checks.performance import check_font_cls
        rule = _get_rule(registry, 63)
        data = data_with_snaps(cls_font_snap)
        findings = check_font_cls(rule, site_ctx, pages([cls_font_snap.url]), data)
        font_findings = [f for f in findings if "font" in f.detected_value.lower()]
        assert len(font_findings) >= 1, f"Expected font-display finding: {[f.detected_value for f in findings]}"

    def test_high_cls_warning(self, registry, site_ctx, pages, data_with_snaps, cls_font_snap):
        from audit_rules.checks.performance import check_font_cls
        rule = _get_rule(registry, 63)
        data = data_with_snaps(cls_font_snap)
        findings = check_font_cls(rule, site_ctx, pages([cls_font_snap.url]), data)
        cls_findings = [f for f in findings if "CLS" in f.detected_value.upper()]
        assert len(cls_findings) >= 1, f"Expected high CLS finding, got {[f.detected_value for f in findings]}"

    def test_layout_shift_elements_mentioned(self, registry, site_ctx, pages, data_with_snaps, cls_font_snap):
        from audit_rules.checks.performance import check_font_cls
        rule = _get_rule(registry, 63)
        data = data_with_snaps(cls_font_snap)
        findings = check_font_cls(rule, site_ctx, pages([cls_font_snap.url]), data)
        shift_findings = [f for f in findings if "Layout shift" in f.detected_value]
        assert len(shift_findings) >= 1, f"Expected layout shift findings: {[f.detected_value for f in findings]}"

    def test_google_fonts_not_auto_fail(self, registry, site_ctx, pages, data_with_snaps):
        from audit_rules.checks.performance import check_font_cls
        from tests.fixtures.psi import PerformanceSnapshot
        snap = PerformanceSnapshot(
            url="https://example.com", strategy="mobile",
            psi_status="success", lab_performance_score=85,
            lab_cls=0.05, font_display_issues=[], layout_shift_elements=[],
        )
        rule = _get_rule(registry, 63)
        data = data_with_snaps(snap)
        findings = check_font_cls(rule, site_ctx, pages([snap.url]), data)
        assert len(findings) == 0, "Google Fonts without issues should not produce findings"


# ============================================================
# False-positive protection
# ============================================================

class TestFalsePositiveProtection:

    def test_good_page_zero_actionable(self, registry, site_ctx, pages, data_with_snaps, good_snap):
        from audit_rules.checks.performance import (
            check_core_web_vitals, check_ttfb, check_render_blocking,
            check_image_performance, check_mobile_experience,
            check_field_vs_lab, check_third_party_scripts, check_font_cls,
        )
        data = data_with_snaps(good_snap)
        pgs = pages([good_snap.url])

        all_findings = []
        all_findings.extend(check_core_web_vitals(_get_rule(registry, 19), site_ctx, pgs, data))
        from audit_rules.adapters import DataUnavailableError
        try:
            all_findings.extend(check_ttfb(_get_rule(registry, 20), site_ctx, pgs, data))
        except DataUnavailableError:
            pass  # no field TTFB: coverage-gap state, not findings
        all_findings.extend(check_render_blocking(_get_rule(registry, 21), site_ctx, pgs, data))
        all_findings.extend(check_image_performance(_get_rule(registry, 22), site_ctx, pgs, data))
        all_findings.extend(check_mobile_experience(_get_rule(registry, 24), site_ctx, pgs, data))
        all_findings.extend(check_field_vs_lab(_get_rule(registry, 61), site_ctx, pgs, data))
        all_findings.extend(check_third_party_scripts(_get_rule(registry, 62), site_ctx, pgs, data))
        all_findings.extend(check_font_cls(_get_rule(registry, 63), site_ctx, pgs, data))

        actionable = [f for f in all_findings if str(f.severity) in ("ERROR", "Warning")]
        assert len(actionable) == 0, (
            f"Good page must have ZERO actionable findings. "
            f"Got {len(actionable)}: {[(f.rule_id, str(f.severity), f.detected_value[:80]) for f in actionable]}"
        )

    def test_api_error_only_info(self, registry, site_ctx, pages, data_with_snaps, error_snap):
        from audit_rules.checks.performance import (
            check_core_web_vitals, check_ttfb, check_render_blocking,
            check_image_performance, check_field_vs_lab,
            check_third_party_scripts, check_font_cls,
        )
        data = data_with_snaps(error_snap)
        pgs = pages([error_snap.url])

        all_findings = []
        all_findings.extend(check_core_web_vitals(_get_rule(registry, 19), site_ctx, pgs, data))
        from audit_rules.adapters import DataUnavailableError as _DUE
        try:
            all_findings.extend(check_ttfb(_get_rule(registry, 20), site_ctx, pgs, data))
        except _DUE:
            pass  # no field TTFB: coverage-gap state, not findings
        all_findings.extend(check_render_blocking(_get_rule(registry, 21), site_ctx, pgs, data))
        all_findings.extend(check_image_performance(_get_rule(registry, 22), site_ctx, pgs, data))
        all_findings.extend(check_field_vs_lab(_get_rule(registry, 61), site_ctx, pgs, data))
        all_findings.extend(check_third_party_scripts(_get_rule(registry, 62), site_ctx, pgs, data))
        all_findings.extend(check_font_cls(_get_rule(registry, 63), site_ctx, pgs, data))

        errors = [f for f in all_findings if str(f.severity) == "Error"]
        assert len(errors) == 0, "API error must not produce ERROR findings"

    def test_psi_error_not_seo_finding(self, registry, site_ctx, pages, data_with_snaps, error_snap):
        from audit_rules.checks.performance import check_core_web_vitals
        rule = _get_rule(registry, 19)
        data = data_with_snaps(error_snap)
        findings = check_core_web_vitals(rule, site_ctx, pages([error_snap.url]), data)
        for f in findings:
            assert "provider error" in f.finding_detail.lower(), (
                f"PSI error must be documented as provider error: {f.finding_detail[:100]}"
            )

    def test_missing_field_data_not_fail(self, registry, site_ctx, pages, data_with_snaps, no_field_snap):
        from audit_rules.checks.performance import check_core_web_vitals
        rule = _get_rule(registry, 19)
        data = data_with_snaps(no_field_snap)
        findings = check_core_web_vitals(rule, site_ctx, pages([no_field_snap.url]), data)
        errors = [f for f in findings if str(f.severity) == "Error"]
        assert len(errors) == 0, "Missing field data is NOT a CWV FAIL"

    def test_lab_only_cannot_pass_cwv(self, registry, site_ctx, pages, data_with_snaps, no_field_snap):
        from audit_rules.checks.performance import check_core_web_vitals
        rule = _get_rule(registry, 19)
        data = data_with_snaps(no_field_snap)
        findings = check_core_web_vitals(rule, site_ctx, pages([no_field_snap.url]), data)
        assert len(findings) >= 1, "Lab-only must produce at least INFO — cannot confirm PASS"

    def test_origin_field_not_url_level(self, registry, site_ctx, pages, data_with_snaps, origin_only_snap):
        from audit_rules.checks.performance import check_core_web_vitals
        rule = _get_rule(registry, 19)
        data = data_with_snaps(origin_only_snap)
        findings = check_core_web_vitals(rule, site_ctx, pages([origin_only_snap.url]), data)
        for f in findings:
            detail = f.finding_detail.lower()
            detected = f.detected_value.lower()
            assert "origin" in detail or "origin" in detected, (
                f"Origin-only finding must mention 'origin': {f.detected_value[:100]}"
            )


# ============================================================
# Adapter Registration (Phase 3 update)
# ============================================================

class TestPhase3AdapterRegistration:

    PHASE3_IDS = {19, 20, 21, 22, 24, 61, 62, 63}

    def test_phase3_ids_in_registry(self):
        from audit_rules.registry import load_registry
        registry = load_registry()
        reg_ids = {r.audit_id for r in registry}
        missing = self.PHASE3_IDS - reg_ids
        assert not missing, f"Phase 3 IDs missing from registry: {missing}"

    def test_phase3_checks_importable(self):
        from audit_rules.checks import get_check
        expected = [
            "check_core_web_vitals", "check_ttfb", "check_render_blocking",
            "check_image_performance", "check_mobile_experience",
            "check_field_vs_lab", "check_third_party_scripts", "check_font_cls",
        ]
        for name in expected:
            fn = get_check(name)
            assert fn is not None, f"Check '{name}' not importable"
            assert callable(fn), f"Check '{name}' is not callable"

    def test_total_adapter_count_updated(self):
        from audit_rules.adapters import CompatibilityHarness
        from audit_rules.registry import load_registry
        registry = load_registry()
        harness = CompatibilityHarness(registry)
        assert len(harness._adapters) == 72, (
            f"Expected 72 adapters through Phase 11, got {len(harness._adapters)}"
        )

    def test_psi_backed_rules_are_classified_partial_not_unimplemented_external(self):
        from audit_rules.registry import load_registry

        rules = {rule.audit_id: rule for rule in load_registry()}
        for audit_id in (21, 24, 62, 63):
            assert rules[audit_id].impl_status.value == "EXISTING_PARTIAL"
            assert rules[audit_id].required_data_sources == ["PageSpeed API"]
            assert rules[audit_id].automatable is True

    def test_phase3_rule_ids_registered(self):
        from audit_rules.adapters import CompatibilityHarness
        from audit_rules.registry import load_registry
        registry = load_registry()
        harness = CompatibilityHarness(registry)
        expected_rule_ids = {
            "core_web_vitals", "server_response_ttfb", "render_blocking_css_js",
            "image_optimization", "mobile_usability", "field_vs_lab_data",
            "third_party_script_impact", "font_loading_cls",
        }
        registered = set(harness._adapters.keys())
        for rid in expected_rule_ids:
            assert rid in registered, f"Phase 3 rule_id '{rid}' not registered"


# ============================================================
# PSI Fixtures
# ============================================================

class TestPSIFixtures:

    def test_all_fixtures_constructable(self):
        from tests.fixtures.psi import ALL_FIXTURES
        for name, builder in ALL_FIXTURES.items():
            snapshot = builder()
            assert snapshot is not None, f"Fixture '{name}' returned None"
            assert snapshot.url, f"Fixture '{name}' has empty URL"
            assert snapshot.strategy in ("mobile", "desktop"), f"Fixture '{name}' bad strategy"

    def test_field_lab_separation(self):
        from tests.fixtures.psi import ALL_FIXTURES
        for name, builder in ALL_FIXTURES.items():
            snap = builder()
            assert snap.field_data_scope in ("URL", "ORIGIN", "NONE", ""), (
                f"Fixture '{name}' has invalid scope: {snap.field_data_scope}"
            )
            if snap.field_data_scope == "NONE":
                assert snap.field_lcp_ms is None, (
                    f"Fixture '{name}' scope=NONE but field_lcp_ms={snap.field_lcp_ms}"
                )

    def test_data_dict_helper(self):
        from tests.fixtures.psi import make_good_mobile, make_data_dict
        snap = make_good_mobile()
        data = make_data_dict([snap])
        assert "_psi_cache" in data
        assert "psi_strategy" in data
        key = (snap.url.rstrip("/").lower(), "mobile")
        assert key in data["_psi_cache"]
        assert data["_psi_cache"][key].url == snap.url
