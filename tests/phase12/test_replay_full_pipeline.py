"""A replay artifact must drive the real offline Master Audit pipeline."""


def _export():
    return {
        "site_check": {
            "robots_txt": {
                "found": True, "disallow_count": 8,
                "important_blocked": [],
            },
            "sitemap": {"found": True, "url": "https://example.com/sitemap.xml"},
            "https_redirect": {"http_redirects_to_https": True},
            "www_redirect": {"alt_redirects_properly": True},
        },
        "pages": [
            {
                "url": "https://example.com/", "status_code": 200,
                "title": "Home", "meta_description": "Example home page",
                "h1": "Home", "word_count": 500,
                "canonical_url": "https://example.com/", "robots": "",
                "internal_links": 1, "external_links": 0,
                "linked_from": ["https://example.com/about"],
                "images": [], "json_ld": [], "hreflang": [],
            },
            {
                "url": "https://example.com/about", "status_code": 200,
                "title": "About", "meta_description": "Example about page",
                "h1": "About", "word_count": 450,
                "canonical_url": "https://example.com/about", "robots": "",
                "internal_links": 0, "external_links": 0,
                "linked_from": [], "images": [], "json_ld": [], "hreflang": [],
            },
        ],
        "links": [{
            "source_url": "https://example.com/",
            "target_url": "https://example.com/about",
            "anchor": "About", "is_internal": True,
        }],
        "completeness": {
            "pages_crawled": 2, "sitemap_total": 2,
            "sitemap_only_count": 0, "sitemap_coverage_pct": 100.0,
            "audit_complete": True, "incomplete_reasons": [],
        },
    }


def _run(export):
    from audit_rules.registry import load_registry
    from audit_rules.runner import RuleRunner

    return RuleRunner(load_registry(), providers={}).run_from_export(
        export, base_url="https://example.com/")


def test_loaded_replay_runs_real_rule_pipeline_with_semantic_parity(tmp_path):
    """A serializer-only artifact must fail this RuleRunner parity test."""
    from audit_rules.replay import (
        build_replay_document, load_replay_artifact, replay_pipeline_inputs,
        write_replay_artifact,
    )

    original = _export()
    direct_findings, direct_coverage = _run(original)
    document = build_replay_document(
        source_url="https://example.com/",
        git_head="d" * 40,
        generated_at="2026-08-09T06:00:00Z",
        crawl_metadata={
            "crawl_started_at": "2026-08-09T05:59:00Z",
            "crawl_completed_at": "2026-08-09T06:00:00Z",
            "crawl_parameters": {"total_max_pages": 1000},
            "truncation_status": "NOT_TRUNCATED",
            "politeness": "polite",
            "sitemap_fill": {"enabled": True, "cap": 500},
        },
        pages=original["pages"], links=original["links"],
        site_data=original["site_check"],
        sitemap_reconciliation={"sitemap_total": 2, "crawl_total": 2},
        crawl_completeness=original["completeness"],
        provider_evidence={},
    )
    target = tmp_path / "example.audit-replay-v1.json.gz"
    write_replay_artifact(document, target, expected_completed_pages=2)

    del original
    loaded = load_replay_artifact(target, expected_completed_pages=2)
    replay_export, replay_existing_data = replay_pipeline_inputs(loaded)
    replay_findings, replay_coverage = _run(replay_export)

    assert len(direct_coverage) == len(replay_coverage) == 80
    assert [row.audit_id for row in replay_coverage] == list(range(1, 81))
    selected_ids = {1, 6, 11, 25, 45}
    direct_selected = sorted(
        (f.audit_id, f.url, f.detected_value, f.evidence)
        for f in direct_findings if f.audit_id in selected_ids)
    replay_selected = sorted(
        (f.audit_id, f.url, f.detected_value, f.evidence)
        for f in replay_findings if f.audit_id in selected_ids)
    assert replay_selected == direct_selected
    assert replay_existing_data["replay_provider_evidence"] == {}
