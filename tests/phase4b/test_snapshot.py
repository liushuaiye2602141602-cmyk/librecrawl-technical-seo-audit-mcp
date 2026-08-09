"""TDD coverage for the portable audit-snapshot-v1 artifact."""

from __future__ import annotations

import copy

import pytest

from audit_rules.context import PageContext, SiteContext


def _make_site() -> SiteContext:
    return SiteContext(base_url="https://example.com", site_profile="generic")


def _make_pages() -> list[PageContext]:
    return [
        PageContext(
            url="https://example.com/z",
            status_code=404,
            title="Missing",
            robots="noindex",
            linked_from_count=1,
        ),
        PageContext(
            url="https://example.com/a",
            status_code=200,
            title="Alpha",
            meta_description="Alpha description",
            h1="Alpha heading",
            canonical_url="https://example.com/a",
            robots="index, follow",
            lang="en",
            linked_from_count=3,
            internal_links_count=2,
            external_links_count=1,
            json_ld_types=["Organization", "WebPage"],
            hreflang_summary=[
                {"lang": "x-default", "url": "https://example.com/a"},
                {"lang": "en", "url": "https://example.com/a"},
            ],
            links_detailed=[
                {"url": "https://example.com/z", "anchor": "Missing", "is_internal": True},
                {"url": "https://outside.example/", "anchor": "Outside", "is_internal": False},
            ],
            content_hash="content-alpha",
        ),
    ]


def test_build_snapshot_has_v1_contract_and_stable_page_order() -> None:
    """Removing a required v1 field or URL sorting must break this contract."""
    from audit_rules.snapshot import build_snapshot

    snapshot = build_snapshot(
        _make_site(),
        _make_pages(),
        created_at="2026-08-09T00:00:00Z",
    )

    assert snapshot["schema_version"] == 1
    assert snapshot["created_at"] == "2026-08-09T00:00:00Z"
    assert snapshot["base_url"] == "https://example.com"
    assert [page["url"] for page in snapshot["pages"]] == [
        "https://example.com/a",
        "https://example.com/z",
    ]
    assert set(snapshot["pages"][0]) >= {
        "url",
        "status",
        "indexable",
        "robots",
        "title",
        "meta_description",
        "h1",
        "canonical",
        "hreflang",
        "schema_fingerprint",
        "content_fingerprint",
        "internal_links",
        "technical_signals",
    }


def test_build_snapshot_is_deterministic_for_page_and_nested_order() -> None:
    """Reordering crawl pages or nested SEO records must not change output."""
    from audit_rules.snapshot import build_snapshot

    pages = _make_pages()
    reversed_nested = copy.deepcopy(pages)
    reversed_nested[1].hreflang_summary = list(
        reversed(reversed_nested[1].hreflang_summary or [])
    )
    reversed_nested[1].json_ld_types = list(
        reversed(reversed_nested[1].json_ld_types or [])
    )

    first = build_snapshot(
        _make_site(),
        pages,
        created_at="2026-08-09T00:00:00Z",
    )
    second = build_snapshot(
        _make_site(),
        list(reversed(reversed_nested)),
        created_at="2026-08-09T00:00:00Z",
    )

    assert second == first


def test_build_snapshot_from_export_uses_existing_crawl_data_only() -> None:
    """Dropping export-to-context wiring must make snapshot construction fail."""
    from audit_rules.snapshot import build_snapshot_from_export

    export = {
        "site_check": {},
        "pages": [
            {
                "url": "https://example.com/",
                "status_code": 200,
                "title": "Home",
                "robots": "index, follow",
                "body_text": "Existing exported body text",
            }
        ],
        "links": [],
    }

    snapshot = build_snapshot_from_export(
        export,
        "https://example.com/",
        created_at="2026-08-09T00:00:00Z",
    )

    assert snapshot["base_url"] == "https://example.com"
    assert snapshot["summary"] == {"page_count": 1, "indexable_count": 1}
    assert len(snapshot["pages"][0]["content_fingerprint"]) == 64


def test_gzip_round_trip_preserves_unknown_additive_v1_fields(tmp_path) -> None:
    """A v1 reader must not reject or discard additive future fields."""
    from audit_rules.snapshot import build_snapshot, load_snapshot, write_snapshot

    snapshot = build_snapshot(
        _make_site(),
        _make_pages(),
        created_at="2026-08-09T00:00:00Z",
    )
    snapshot["future_optional_field"] = {"enabled": True}
    path = write_snapshot(snapshot, tmp_path / "audit-snapshot-v1.json.gz")

    assert path.read_bytes()[:2] == b"\x1f\x8b"
    assert load_snapshot(path) == snapshot


def test_gzip_bytes_are_deterministic_for_identical_snapshot(tmp_path) -> None:
    """Wall-clock gzip metadata must not make equal artifacts differ."""
    from audit_rules.snapshot import build_snapshot, write_snapshot

    snapshot = build_snapshot(
        _make_site(),
        _make_pages(),
        created_at="2026-08-09T00:00:00Z",
    )
    first = write_snapshot(snapshot, tmp_path / "first.json.gz").read_bytes()
    second = write_snapshot(snapshot, tmp_path / "second.json.gz").read_bytes()

    assert second == first


def test_validation_rejects_unsupported_schema_version(tmp_path) -> None:
    """Accepting a future major version would allow unsafe misinterpretation."""
    from audit_rules.snapshot import (
        SnapshotValidationError,
        build_snapshot,
        write_snapshot,
    )

    snapshot = build_snapshot(_make_site(), _make_pages())
    snapshot["schema_version"] = 2

    with pytest.raises(
        SnapshotValidationError,
        match="Unsupported snapshot schema version: 2",
    ):
        write_snapshot(snapshot, tmp_path / "unsupported.json.gz")


def test_validation_rejects_duplicate_page_urls() -> None:
    """Duplicate URL rows would make diff indexing silently lossy."""
    from audit_rules.snapshot import (
        SnapshotValidationError,
        build_snapshot,
        validate_snapshot,
    )

    snapshot = build_snapshot(_make_site(), _make_pages())
    snapshot["pages"].append(dict(snapshot["pages"][0]))

    with pytest.raises(SnapshotValidationError, match="duplicate URL"):
        validate_snapshot(snapshot)


def test_load_wraps_malformed_gzip_with_path(tmp_path) -> None:
    """Raw gzip/JSON errors must not escape without artifact context."""
    from audit_rules.snapshot import SnapshotValidationError, load_snapshot

    path = tmp_path / "broken.json.gz"
    path.write_bytes(b"not-a-gzip-file")

    with pytest.raises(SnapshotValidationError, match="broken.json.gz"):
        load_snapshot(path)
