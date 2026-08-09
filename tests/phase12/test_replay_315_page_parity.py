"""Large offline replay acceptance fixture."""


def _synthetic_export():
    pages = []
    links = []
    for index in range(315):
        url = f"https://example.com/page-{index:03d}"
        page_links = []
        for offset in range(1, 5):
            target = f"https://example.com/page-{(index + offset) % 315:03d}"
            page_links.append({
                "url": target, "anchor": f"Page {(index + offset) % 315}",
                "is_internal": True, "rel": "",
            })
            links.append({
                "source_url": url, "target_url": target,
                "anchor_text": f"Page {(index + offset) % 315}",
                "is_internal": True,
            })
        pages.append({
            "url": url, "status_code": 200, "title": f"Title {index}",
            "meta_description": f"Description {index}", "h1": f"Heading {index}",
            "canonical_url": url, "robots": "index, follow", "depth": index % 5,
            "word_count": 500 + index, "hreflang": [
                {"hreflang": "en", "href": url},
            ], "json_ld": [{"@type": "WebPage", "name": f"Page {index}"}],
            "links_detailed": page_links, "internal_links": 4,
            "external_links": 0, "redirects": [], "linked_from": [],
        })
    return pages, links


def test_315_page_replay_preserves_exact_normalized_inputs_and_pipeline(tmp_path):
    from audit_rules.replay import (
        assert_replay_parity, build_replay_document, load_replay_artifact,
        run_replay_pipeline, write_replay_artifact,
    )

    pages, links = _synthetic_export()
    document = build_replay_document(
        source_url="https://example.com/", git_head="a" * 40,
        generated_at="2026-08-09T08:00:00Z",
        crawl_metadata={"crawl_parameters": {}, "truncation_status": "NOT_TRUNCATED"},
        pages=pages, links=links,
        site_data={
            "robots_txt": {"found": True, "disallow_count": 0,
                           "sitemap_declared": ["https://example.com/sitemap.xml"]},
            "sitemap": {"found": True, "url": "https://example.com/sitemap.xml"},
        },
        sitemap_reconciliation={
            "sitemap_total": 315, "crawl_total": 315,
            "sitemap_only": [], "crawl_only": [],
        },
        crawl_completeness={"pages_crawled": 315, "audit_complete": True},
        provider_evidence={},
    )
    before_findings, before_coverage = run_replay_pipeline(document)
    target = tmp_path / "example.audit-replay-v1.json.gz"
    write_replay_artifact(document, target, expected_completed_pages=315)

    pages.clear()
    links.clear()
    loaded = load_replay_artifact(target, expected_completed_pages=315)
    parity = assert_replay_parity(document, loaded)
    after_findings, after_coverage = run_replay_pipeline(loaded)

    assert loaded["counts"]["page_count"] == 315
    assert loaded["counts"]["link_count"] == 1260
    assert parity.status == "REPLAY_PARITY_PASS"
    assert len(after_coverage) == 80
    assert {(f.audit_id, f.url, f.detected_value) for f in before_findings} == {
        (f.audit_id, f.url, f.detected_value) for f in after_findings
    }
    assert [(row.audit_id, row.result_status) for row in before_coverage] == [
        (row.audit_id, row.result_status) for row in after_coverage
    ]
