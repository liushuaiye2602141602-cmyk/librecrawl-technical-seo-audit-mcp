"""80-rule diagnostic quality correction regression tests.

Contracts locked by these tests:
  - x-default missing is an OPPORTUNITY, not a FAIL.
  - zero HTML inbound links => orphan candidate (not PASS).
  - high CLS without font attribution does not trigger Rule 63.
  - no CrUX field data cannot PASS field CWV.
  - PSI sampling is partial execution, not full-site coverage.
  - NOT_APPLICABLE rules cannot emit remediation tasks.
  - crawl-layer sitemap/thin-content checks run without GSC (partial).
  - empty schema set is NOT_APPLICABLE for validation rules, not PASS.
  - ALT length thresholds and title widths are heuristics.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _registry():
    from audit_rules.registry import load_registry
    return load_registry()


def _rule(audit_id: int):
    return next(r for r in _registry() if r.audit_id == audit_id)


def _page(url="https://example.com/", status=200, hreflang=None,
          linked_from=0, internal_links=1, title="Unique title", meta=None,
          h1="Heading", word_count=500, json_ld=None, images=None,
          canonical=None, robots=""):
    from audit_rules.context import PageContext
    return PageContext(
        url=url,
        status_code=status,
        title=title,
        meta_description=meta,
        h1=h1,
        canonical_url=canonical or url,
        robots=robots,
        word_count=word_count,
        hreflang_summary=hreflang,
        json_ld_types=json_ld or [],
        linked_from_count=linked_from,
        internal_links_count=internal_links,
        _raw_export={"links_detailed": [], "linked_from": [], "images": images or []},
    )


def _site(profile="generic", sitemap_found=True):
    from audit_rules.context import SiteContext
    return SiteContext(
        base_url="https://example.com/",
        robots_txt_found=True,
        sitemap_found=sitemap_found,
        sitemap_url="https://example.com/sitemap.xml",
        site_profile=profile,
        _site_data={"sitemap": {"found": sitemap_found,
                                 "url": "https://example.com/sitemap.xml"}},
    )


def _coverage_row(audit_id, site_ctx, pages, findings, providers=None,
                  executed=None, partial=None, reasons=None,
                  evaluated_overrides=None):
    from audit_rules.coverage import CoverageManager
    rows = CoverageManager(_registry()).compute(
        site_ctx, pages, findings,
        providers_available=providers or {"LibreCrawl"},
        executed_rule_ids=executed or {audit_id},
        partially_executed_rule_ids=partial or set(),
        not_checked_reasons=reasons or {},
        evaluated_overrides=evaluated_overrides or {},
    )
    return next(r for r in rows if r.audit_id == audit_id)


# ---------------------------------------------------------------------------
# Audit #29 — hreflang basics
# ---------------------------------------------------------------------------

def _reciprocal_hreflang():
    en = [{"lang": "en", "url": "https://example.com/"},
          {"lang": "de", "url": "https://example.com/de/"},
          {"lang": "es", "url": "https://example.com/es/"}]
    de = [{"lang": "en", "url": "https://example.com/"},
          {"lang": "de", "url": "https://example.com/de/"},
          {"lang": "es", "url": "https://example.com/es/"}]
    return [
        _page("https://example.com/", hreflang=en),
        _page("https://example.com/de/", hreflang=de),
    ]


def test_missing_x_default_only_does_not_fail_hreflang():
    from audit_rules.adapters import _adapter_hreflang_basics
    pages = _reciprocal_hreflang()
    findings = _adapter_hreflang_basics(_rule(29), _site(), pages, {})
    assert findings, "expected x-default opportunity findings"
    assert all(str(f.severity) == "Opportunity" for f in findings)
    assert all("x-default" in (f.detected_value or "") for f in findings)
    row = _coverage_row(29, _site(), pages, findings)
    assert row.result_status.value == "OPPORTUNITY"


def test_invalid_hreflang_code_fails():
    from audit_rules.adapters import _adapter_hreflang_basics
    pages = [
        _page("https://example.com/", hreflang=[
            {"lang": "english", "url": "https://example.com/"},
            {"lang": "de", "url": "https://example.com/de/"},
        ]),
    ]
    findings = _adapter_hreflang_basics(_rule(29), _site(), pages, {})
    assert any(str(f.severity) in ("Error", "Warning") for f in findings)


def test_missing_return_link_warns_per_contract():
    from audit_rules.adapters import _adapter_hreflang_basics
    pages = [
        _page("https://example.com/", hreflang=[
            {"lang": "en", "url": "https://example.com/"},
            {"lang": "de", "url": "https://example.com/de/"},
        ]),
        _page("https://example.com/de/", hreflang=[
            {"lang": "de", "url": "https://example.com/de/"},
            # missing reciprocal en entry
        ]),
    ]
    findings = _adapter_hreflang_basics(_rule(29), _site(), pages, {})
    assert any("return" in (f.detected_value or "").lower()
               or "reciprocal" in (f.detected_value or "").lower()
               for f in findings)


def test_duplicate_hreflang_lang_conflict_warns():
    from audit_rules.adapters import _adapter_hreflang_basics
    pages = [
        _page("https://example.com/", hreflang=[
            {"lang": "en", "url": "https://example.com/"},
            {"lang": "en", "url": "https://example.com/en-alt/"},
            {"lang": "de", "url": "https://example.com/de/"},
        ]),
    ]
    findings = _adapter_hreflang_basics(_rule(29), _site(), pages, {})
    assert any("conflict" in (f.detected_value or "").lower()
               or "duplicate" in (f.detected_value or "").lower()
               for f in findings)


def test_hreflang_target_404_fails():
    from audit_rules.adapters import _adapter_hreflang_indexability
    pages = [
        _page("https://example.com/", hreflang=[
            {"lang": "en", "url": "https://example.com/"},
            {"lang": "de", "url": "https://example.com/de/"}]),
        _page("https://example.com/de/", status=404),
    ]
    findings = _adapter_hreflang_indexability(_rule(58), _site(), pages, {})
    assert any(str(f.severity) == "Error" for f in findings)


def test_hreflang_target_noindex_fails():
    from audit_rules.adapters import _adapter_hreflang_indexability
    pages = [
        _page("https://example.com/", hreflang=[
            {"lang": "en", "url": "https://example.com/"},
            {"lang": "de", "url": "https://example.com/de/"}]),
        _page("https://example.com/de/", robots="noindex, nofollow"),
    ]
    findings = _adapter_hreflang_indexability(_rule(58), _site(), pages, {})
    assert any(str(f.severity) == "Error" for f in findings)


# ---------------------------------------------------------------------------
# Audit #11 vs #45 — internal links / orphan candidates
# ---------------------------------------------------------------------------

def test_zero_html_inlink_url_is_orphan_candidate():
    from audit_rules.adapters import _adapter_orphan_pages
    pages = [_page("https://example.com/lonely.html", linked_from=0,
                   internal_links=2)]
    findings = _adapter_orphan_pages(_rule(45), _site(), pages, {})
    assert len(findings) == 1
    assert str(findings[0].severity) in ("Warning", "Opportunity")


def test_internally_linked_url_is_not_orphan():
    from audit_rules.adapters import _adapter_orphan_pages
    pages = [_page("https://example.com/", linked_from=3, internal_links=2)]
    findings = _adapter_orphan_pages(_rule(45), _site(), pages, {})
    assert findings == []


def test_sitemap_discovery_does_not_count_as_internal_link():
    from audit_rules.adapters import _adapter_orphan_pages
    site = _site(sitemap_found=True)
    pages = [_page("https://example.com/sitemap-only.html", linked_from=0,
                   internal_links=1)]
    findings = _adapter_orphan_pages(_rule(45), site, pages, {})
    assert len(findings) == 1
    assert "linked_from" in (findings[0].evidence or "")


# ---------------------------------------------------------------------------
# Audit #63 — font CLS attribution
# ---------------------------------------------------------------------------

def _font_snapshot(cls=0.4, shifts=None, font_issues=None):
    from audit_rules.providers.performance_snapshot import (
        LayoutShiftElement, PerformanceSnapshot,
    )
    return PerformanceSnapshot(
        url="https://example.com/", strategy="mobile",
        psi_status="success", lab_cls=cls,
        layout_shift_elements=[LayoutShiftElement(
            node_label=label, cls_contribution=contribution)
            for label, contribution in (shifts or [])],
        font_display_issues=font_issues or [],
    )


def test_high_cls_without_font_shift_does_not_trigger_rule63():
    from audit_rules.checks.performance import check_font_cls
    snap = _font_snapshot(cls=0.4, shifts=[("image-gallery", 0.35)])
    data = {"_psi_cache": {("https://example.com", "mobile"): snap},
            "psi_strategy": "mobile"}
    findings = check_font_cls(_rule(63), _site(), [
        _page("https://example.com/")], data)
    assert findings == []


def test_font_shift_evidence_can_trigger_rule63():
    from audit_rules.checks.performance import check_font_cls
    snap = _font_snapshot(cls=0.4, shifts=[("heading text", 0.25)])
    data = {"_psi_cache": {("https://example.com", "mobile"): snap},
            "psi_strategy": "mobile"}
    findings = check_font_cls(_rule(63), _site(), [
        _page("https://example.com/")], data)
    assert len(findings) >= 1


# ---------------------------------------------------------------------------
# Audit #19 — field vs lab CWV
# ---------------------------------------------------------------------------

def _lab_snapshot(score=95, lcp=1500.0, status="success", error=""):
    from audit_rules.providers.performance_snapshot import PerformanceSnapshot
    return PerformanceSnapshot(
        url="https://example.com/", strategy="mobile", psi_status=status,
        error=error, lab_performance_score=score, lab_lcp_ms=lcp,
        field_data_scope="NONE",
    )


def test_psi_timeout_is_provider_error_not_seo_failure():
    from audit_rules.checks.performance import check_core_web_vitals
    snap = _lab_snapshot(status="error", error="PSI request timed out after 30s")
    data = {"_psi_cache": {("https://example.com", "mobile"): snap},
            "psi_strategy": "mobile"}
    findings = check_core_web_vitals(_rule(19), _site(), [
        _page("https://example.com/")], data)
    assert len(findings) == 1
    assert str(findings[0].severity) == "Info"
    assert "provider error" in (findings[0].finding_detail or "").lower()


def test_no_crux_cannot_pass_field_cwv():
    from audit_rules.checks.performance import check_core_web_vitals
    snap = _lab_snapshot(score=95, lcp=1500.0)
    data = {"_psi_cache": {("https://example.com", "mobile"): snap},
            "psi_strategy": "mobile"}
    page = _page("https://example.com/")
    findings = check_core_web_vitals(_rule(19), _site(), [page], data)
    assert findings
    row = _coverage_row(
        19, _site(), [page], findings,
        providers={"LibreCrawl", "PageSpeed API"},
        evaluated_overrides={19: 1},
    )
    assert row.result_status.value != "PASS"


class _StaticPSI:
    name = "PageSpeed API"
    aliases = {"PageSpeed API"}
    _strategies = ["mobile"]
    _sample_limit = 2

    def __init__(self, snapshots):
        self._cache = {
            (s.url.rstrip("/").lower(), s.strategy): s for s in snapshots}

    def is_available(self):
        return True

    def collect(self, site_ctx, page_contexts, existing_data):
        return True

    def clear_cache(self):
        pass

    def get_snapshot(self, url, strategy="mobile"):
        return self._cache.get((url.rstrip("/").lower(), strategy))


def test_sampled_psi_is_partial_execution():
    from audit_rules.runner import RuleRunner
    _StaticPSI._sample_limit = 1
    pages = [
        _page(f"https://example.com/p{i}.html") for i in range(1, 6)
    ]
    snap = _lab_snapshot(score=60, lcp=5000.0)
    snap.url = "https://example.com/p1.html"
    runner = RuleRunner(_registry(), providers={"PageSpeed API": _StaticPSI([snap])})
    _, coverage = runner.run(
        site_data={"robots_txt": {"found": True},
                   "sitemap": {"found": True, "url": "https://example.com/sitemap.xml"}},
        pages=[p._raw_export | {"url": p.url, "status_code": 200,
                                "title": p.title, "word_count": p.word_count}
               for p in pages],
        links=[], base_url="https://example.com/",
    )
    row = next(r for r in coverage if r.audit_id == 19)
    assert row.execution_status.value == "EXECUTED_PARTIAL"
    assert row.evaluated_count == 1


# ---------------------------------------------------------------------------
# Audit #70 — form accessibility must not false-PASS
# ---------------------------------------------------------------------------

def test_insufficient_body_html_cannot_pass_full_accessibility():
    from audit_rules.checks.form_accessibility import check_form_accessibility
    page = _page("https://example.com/contact.html")
    findings = check_form_accessibility(_rule(70), _site(), [page], {})
    row = _coverage_row(70, _site(), [page], findings)
    assert row.execution_status.value == "EXECUTED_PARTIAL"
    assert row.result_status.value == "UNKNOWN"


# ---------------------------------------------------------------------------
# NOT_APPLICABLE cannot create tasks
# ---------------------------------------------------------------------------

def test_not_applicable_rule_cannot_emit_remediation_task():
    from audit_rules.checks.audit_deliverables import applicable_findings
    from audit_rules.adapters import _mk_finding
    from audit_rules.coverage import CoverageManager

    staging_finding = _mk_finding(
        _rule(67), url="https://example.com/",
        detected="no staging candidates", expected="no staging exposure",
        evidence="staging_candidates=0", detail="observation only",
    )
    pages = [_page()]
    rows = CoverageManager(_registry()).compute(
        _site(profile="generic"), pages, [staging_finding],
        executed_rule_ids=set(), not_checked_reasons={},
    )
    active = applicable_findings([staging_finding], rows)
    assert active == []


# ---------------------------------------------------------------------------
# Audit #2 / #16 — crawl-layer partial execution
# ---------------------------------------------------------------------------

def test_sitemap_crawl_checks_can_execute_without_gsc():
    from audit_rules.adapters import _adapter_sitemap_indexability
    from audit_rules.checks.foundation_gaps import check_xml_sitemap_valid

    site = _site(sitemap_found=True)
    pages = [_page("https://example.com/")]
    findings = check_xml_sitemap_valid(_rule(2), site, pages, {})
    findings += _adapter_sitemap_indexability(_rule(42), site, pages, {})
    row = _coverage_row(
        2, site, pages, findings,
        providers={"LibreCrawl"},
        executed={2},
    )
    assert row.execution_status.value == "EXECUTED_PARTIAL"
    assert "GSC" in (row.not_checked_reason or "")


def test_missing_gsc_makes_rule_partial_not_unchecked():
    from audit_rules.checks.foundation_gaps import check_xml_sitemap_valid
    site = _site(sitemap_found=True)
    pages = [_page("https://example.com/")]
    findings = check_xml_sitemap_valid(_rule(2), site, pages, {})
    row = _coverage_row(2, site, pages, findings,
                        providers={"LibreCrawl"}, executed={2})
    assert row.execution_status.value != "NOT_CHECKED"


def test_crawl_can_generate_thin_content_candidates():
    from audit_rules.checks.content_metadata import check_thin_content
    thin = _page("https://example.com/thin.html", word_count=60,
                 title="", meta="", h1="")
    findings = check_thin_content(_rule(16), _site(), [thin], {})
    assert findings
    assert all(str(f.severity) != "Error" for f in findings)


def test_word_count_alone_cannot_confirm_low_value():
    from audit_rules.checks.content_metadata import check_thin_content
    ok = _page("https://example.com/rich.html", word_count=150,
               title="A descriptive title for this page",
               meta="A useful meta description for this page",
               h1="A clear heading")
    findings = check_thin_content(_rule(16), _site(), [ok], {})
    assert all(str(f.severity) != "Error" for f in findings)


# ---------------------------------------------------------------------------
# Audit #27 / #28 / #78 — empty schema semantics
# ---------------------------------------------------------------------------

def test_no_schema_does_not_pass_schema_error_rule():
    from audit_rules.checks.structured_data import check_schema_conflict
    pages = [_page("https://example.com/", json_ld=[])]
    findings = check_schema_conflict(_rule(28), _site(), pages, {})
    row = _coverage_row(28, _site(), pages, findings, executed={28})
    assert row.execution_status.value == "NOT_APPLICABLE"
    assert "NO_SCHEMA" in (row.not_checked_reason or "").upper()


def test_no_schema_does_not_pass_visible_content_match():
    from audit_rules.checks.structured_data import check_schema_vs_visible
    pages = [_page("https://example.com/", json_ld=[])]
    findings = check_schema_vs_visible(_rule(78), _site(), pages, {})
    row = _coverage_row(78, _site(), pages, findings, executed={78})
    assert row.execution_status.value == "NOT_APPLICABLE"
    assert "NO_SCHEMA" in (row.not_checked_reason or "").upper()


def test_schema_types_extracted_from_nested_json_ld():
    from audit_rules.context import PageContext
    ctx = PageContext.from_export({
        "url": "https://example.com/", "status_code": 200,
        "json_ld": [[{"@context": "https://schema.org",
                      "@type": "Organization", "name": "Example"}]],
    })
    assert "Organization" in ctx.json_ld_types


# ---------------------------------------------------------------------------
# Audit #79 — image alt candidates
# ---------------------------------------------------------------------------

def test_empty_alt_not_automatically_error():
    from audit_rules.checks.media import check_image_alt_quality
    page = _page("https://example.com/", images=[
        {"src": "https://example.com/dec.png", "alt": ""},
    ])
    findings = check_image_alt_quality(_rule(79), _site(), [page], {})
    assert findings == []


def test_missing_alt_attribute_on_informative_candidate_warns():
    from audit_rules.checks.media import check_image_alt_quality
    page = _page("https://example.com/", images=[
        {"src": "https://example.com/product.jpg", "alt": ""},
    ])
    # image summary missing_alt>0 drives the warning when per-image list lacks alt
    page.image_summary = {"count": 1, "missing_alt": 1}
    findings = check_image_alt_quality(_rule(79), _site(), [page], {})
    assert any(str(f.severity) in ("Warning", "Opportunity") for f in findings)


def test_alt_length_threshold_is_heuristic():
    from audit_rules.checks.media import check_image_alt_quality
    page = _page("https://example.com/", images=[
        {"src": "https://example.com/x.jpg",
         "alt": "a" * 200},
    ])
    findings = check_image_alt_quality(_rule(79), _site(), [page], {})
    assert all(str(f.severity) != "Error" for f in findings)


# ---------------------------------------------------------------------------
# Audit #13 — title semantics
# ---------------------------------------------------------------------------

def test_title_width_only_is_opportunity():
    from audit_rules.checks.foundation_gaps import check_title_uniqueness
    long_title = "This is a deliberately very long title that will exceed the estimated SERP display width threshold for search results"
    page = _page("https://example.com/", title=long_title)
    findings = check_title_uniqueness(_rule(13), _site(), [page], {})
    assert findings
    assert all(str(f.severity) == "Opportunity" for f in findings)


def test_duplicate_title_is_warning():
    from audit_rules.checks.foundation_gaps import check_title_uniqueness
    pages = [
        _page("https://example.com/a.html", title="Same title"),
        _page("https://example.com/b.html", title="Same title"),
    ]
    findings = check_title_uniqueness(_rule(13), _site(), pages, {})
    assert any(str(f.severity) == "Warning" for f in findings)


def test_missing_title_is_error_per_contract():
    from audit_rules.checks.foundation_gaps import check_title_uniqueness
    page = _page("https://example.com/", title=None)
    findings = check_title_uniqueness(_rule(13), _site(), [page], {})
    assert any(str(f.severity) == "Error" for f in findings)
