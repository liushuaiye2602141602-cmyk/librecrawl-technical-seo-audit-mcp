"""Versioned audit replay serialization contracts."""

import gzip
import json


def _document():
    from audit_rules.replay import build_replay_document

    return build_replay_document(
        source_url="https://example.com/",
        git_head="a" * 40,
        generated_at="2026-08-09T06:00:00Z",
        crawl_metadata={
            "crawl_started_at": "2026-08-09T05:55:00Z",
            "crawl_completed_at": "2026-08-09T06:00:00Z",
            "crawl_parameters": {"total_max_pages": 1000},
            "truncation_status": "NOT_TRUNCATED",
            "politeness": "polite",
            "sitemap_fill": {"enabled": True, "cap": 500},
        },
        pages=[
            {
                "url": "https://example.com/z",
                "status_code": 200,
                "title": "Zed",
                "internal_links": 1,
                "external_links": 0,
                "unknown_future_field": "must not leak into v1",
            },
            {
                "url": "https://example.com/a",
                "status_code": 200,
                "title": "Alpha",
                "internal_links": 2,
                "external_links": 1,
            },
        ],
        links=[
            {
                "source_url": "https://example.com/z",
                "target_url": "https://example.com/a",
                "anchor": "A",
                "is_internal": True,
            }
        ],
        site_data={"robots_txt": {"found": True}},
        sitemap_reconciliation={
            "sitemap_total": 2,
            "crawl_total": 2,
            "sitemap_only": [],
            "crawl_only": [],
            "both": ["https://example.com/a", "https://example.com/z"],
        },
        crawl_completeness={
            "pages_crawled": 2,
            "audit_complete": True,
            "incomplete_reasons": [],
        },
        provider_evidence={
            "provider_status": {"gsc": "LIVE_VALIDATION_PENDING"}
        },
    )


def test_replay_writer_stably_sorts_and_loads_current_crawl_inputs(tmp_path):
    """Removing stable sorting or a required collection must break replay."""
    from audit_rules.replay import load_replay_artifact, write_replay_artifact

    target = tmp_path / "example.com-20260809-0600.audit-replay-v1.json.gz"
    result = write_replay_artifact(
        _document(), target,
        expected_source_url="https://example.com/",
        expected_completed_pages=2,
    )

    assert result.valid is True
    assert result.page_count == 2
    assert result.link_count == 1
    loaded = load_replay_artifact(
        target,
        expected_source_url="https://example.com/",
        expected_completed_pages=2,
    )
    assert loaded["schema_version"] == "1.0"
    assert loaded["artifact_type"] == "audit_replay"
    assert loaded["counts"] == {"link_count": 1, "page_count": 2}
    assert [page["url"] for page in loaded["pages"]] == [
        "https://example.com/a", "https://example.com/z"]
    assert "unknown_future_field" not in loaded["pages"][1]

    with gzip.open(target, "rt", encoding="utf-8") as stream:
        decoded = json.load(stream)
    assert decoded == loaded


def test_same_document_writes_identical_gzip_bytes(tmp_path):
    """Adding gzip timestamps or unstable ordering must break reproducibility."""
    from audit_rules.replay import write_replay_artifact

    first = tmp_path / "first.json.gz"
    second = tmp_path / "second.json.gz"
    document = _document()

    write_replay_artifact(document, first, expected_completed_pages=2)
    write_replay_artifact(document, second, expected_completed_pages=2)

    assert first.read_bytes() == second.read_bytes()
