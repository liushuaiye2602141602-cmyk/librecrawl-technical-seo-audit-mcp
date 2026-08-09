"""TDD coverage for deterministic v1 snapshot comparison."""

from __future__ import annotations

import copy
import csv
import io

import pytest


def _page(url: str = "https://example.com/a") -> dict:
    return {
        "url": url,
        "status": 200,
        "indexable": True,
        "robots": "index, follow",
        "title": "Alpha title",
        "meta_description": "Alpha description",
        "h1": "Alpha heading",
        "canonical": url,
        "hreflang": [{"lang": "en", "url": url}],
        "schema_fingerprint": "schema-a",
        "content_fingerprint": "content-a",
        "internal_links": {
            "inbound_count": 5,
            "outbound_count": 4,
            "target_count": 4,
            "targets_fingerprint": "targets-a",
        },
        "technical_signals": {
            "lang": "en",
            "viewport": "width=device-width",
            "word_count": 500,
            "response_time_ms": 120,
        },
    }


def _snapshot(*pages: dict) -> dict:
    page_list = list(pages) or [_page()]
    return {
        "schema_version": 1,
        "created_at": "2026-08-09T00:00:00Z",
        "base_url": "https://example.com",
        "site_profile": "generic",
        "pages": page_list,
        "summary": {
            "page_count": len(page_list),
            "indexable_count": sum(1 for page in page_list if page["indexable"]),
        },
    }


def _change_types(before: dict, after: dict) -> set[str]:
    from audit_rules.snapshot_diff import diff_snapshots

    return {change.change_type for change in diff_snapshots(before, after)}


@pytest.mark.parametrize(
    ("mutate", "expected_type"),
    [
        (
            lambda after: after["pages"].append(_page("https://example.com/new")),
            "URL_ADDED",
        ),
        (lambda after: after["pages"].pop(), "URL_REMOVED"),
        (lambda after: after["pages"][0].update(status=404), "STATUS_CHANGED"),
        (
            lambda after: after["pages"][0].update(indexable=False),
            "INDEXABILITY_CHANGED",
        ),
        (
            lambda after: after["pages"][0].update(robots="noindex"),
            "ROBOTS_CHANGED",
        ),
        (
            lambda after: after["pages"][0].update(
                canonical="https://example.com/other"
            ),
            "CANONICAL_CHANGED",
        ),
        (
            lambda after: after["pages"][0].update(title="Changed title"),
            "TITLE_CHANGED",
        ),
        (
            lambda after: after["pages"][0].update(
                meta_description="Changed description"
            ),
            "DESCRIPTION_CHANGED",
        ),
        (
            lambda after: after["pages"][0].update(h1="Changed heading"),
            "H1_CHANGED",
        ),
        (
            lambda after: after["pages"][0].update(
                hreflang=[
                    {"lang": "de", "url": "https://example.com/de/a"}
                ]
            ),
            "HREFLANG_CHANGED",
        ),
        (
            lambda after: after["pages"][0].update(
                schema_fingerprint="schema-b"
            ),
            "SCHEMA_CHANGED",
        ),
        (
            lambda after: after["pages"][0].update(
                content_fingerprint="content-b"
            ),
            "CONTENT_CHANGED",
        ),
        (
            lambda after: after["pages"][0]["internal_links"].update(
                inbound_count=0
            ),
            "INTERNAL_LINK_REGRESSION",
        ),
    ],
)
def test_detects_every_required_change_type(mutate, expected_type: str) -> None:
    """Dropping any required comparison branch must fail its literal case."""
    before = _snapshot()
    after = copy.deepcopy(before)
    mutate(after)

    assert expected_type in _change_types(before, after)


def test_good_to_bad_status_and_indexability_are_regressions() -> None:
    """A healthy URL becoming non-indexable must never be informational."""
    from audit_rules.snapshot_diff import diff_snapshots

    before = _snapshot()
    after = copy.deepcopy(before)
    after["pages"][0].update(status=404, indexable=False)

    actual = {
        (change.change_type, change.classification)
        for change in diff_snapshots(before, after)
    }
    assert ("STATUS_CHANGED", "REGRESSED") in actual
    assert ("INDEXABILITY_CHANGED", "REGRESSED") in actual


def test_bad_to_good_status_and_indexability_are_fixed() -> None:
    """Reversing a crawl/indexing failure must be classified as fixed."""
    from audit_rules.snapshot_diff import diff_snapshots

    before_page = _page()
    before_page.update(status=404, indexable=False)
    before = _snapshot(before_page)
    after = copy.deepcopy(before)
    after["pages"][0].update(status=200, indexable=True)

    actual = {
        (change.change_type, change.classification)
        for change in diff_snapshots(before, after)
    }
    assert ("STATUS_CHANGED", "FIXED") in actual
    assert ("INDEXABILITY_CHANGED", "FIXED") in actual


def test_metadata_loss_is_new_issue_and_restoration_is_fixed() -> None:
    """Empty metadata transitions must not be treated like neutral rewrites."""
    from audit_rules.snapshot_diff import diff_snapshots

    before = _snapshot()
    missing = copy.deepcopy(before)
    missing["pages"][0]["title"] = ""
    lost = diff_snapshots(before, missing)
    restored = diff_snapshots(missing, before)

    assert [(item.change_type, item.classification) for item in lost] == [
        ("TITLE_CHANGED", "NEW_ISSUE")
    ]
    assert [(item.change_type, item.classification) for item in restored] == [
        ("TITLE_CHANGED", "FIXED")
    ]


def test_value_to_value_metadata_change_is_informational() -> None:
    """A title rewrite alone is not automatically an SEO regression."""
    from audit_rules.snapshot_diff import diff_snapshots

    before = _snapshot()
    after = copy.deepcopy(before)
    after["pages"][0]["title"] = "Rewritten title"

    change = diff_snapshots(before, after)[0]
    assert change.change_type == "TITLE_CHANGED"
    assert change.classification == "INFORMATIONAL_CHANGE"


def test_identical_snapshots_only_emit_unchanged_when_requested() -> None:
    """Default artifacts stay concise while the UNCHANGED class remains usable."""
    from audit_rules.snapshot_diff import diff_snapshots

    before = _snapshot()
    after = copy.deepcopy(before)

    assert diff_snapshots(before, after) == []
    unchanged = diff_snapshots(before, after, include_unchanged=True)
    assert [(item.change_type, item.classification) for item in unchanged] == [
        ("PAGE_UNCHANGED", "UNCHANGED")
    ]


def test_internal_link_improvement_does_not_emit_regression() -> None:
    """The regression-only signal must not flag increasing inbound links."""
    before = _snapshot()
    after = copy.deepcopy(before)
    after["pages"][0]["internal_links"]["inbound_count"] = 8

    assert "INTERNAL_LINK_REGRESSION" not in _change_types(before, after)


def test_output_order_is_url_then_change_type() -> None:
    """Crawl input ordering must not make artifacts nondeterministic."""
    from audit_rules.snapshot_diff import diff_snapshots

    before = _snapshot(
        _page("https://example.com/z"),
        _page("https://example.com/a"),
    )
    after = copy.deepcopy(before)
    for page in after["pages"]:
        page["title"] = "Changed"
        page["h1"] = "Changed"

    actual = [
        (change.url, change.change_type)
        for change in diff_snapshots(before, after)
    ]
    assert actual == [
        ("https://example.com/a", "H1_CHANGED"),
        ("https://example.com/a", "TITLE_CHANGED"),
        ("https://example.com/z", "H1_CHANGED"),
        ("https://example.com/z", "TITLE_CHANGED"),
    ]


def test_diff_5000_pages_returns_only_the_single_mutation() -> None:
    """A final-page mutation must not require or emit all-pairs comparisons."""
    from audit_rules.snapshot_diff import diff_snapshots

    pages = [_page(f"https://example.com/{index:04d}") for index in range(5000)]
    before = _snapshot(*pages)
    after = copy.deepcopy(before)
    after["pages"][-1]["content_fingerprint"] = "changed"

    changes = diff_snapshots(before, after)
    assert [(item.url, item.change_type) for item in changes] == [
        ("https://example.com/4999", "CONTENT_CHANGED")
    ]


def test_csv_writer_preserves_header_order_json_values_and_utf8() -> None:
    """Changing column order or lossy value encoding must break the artifact."""
    from audit_rules.snapshot_diff import (
        SnapshotChange,
        crawl_diff_csv_to_string,
    )

    changes = [
        SnapshotChange(
            url="https://example.com/中文",
            change_type="HREFLANG_CHANGED",
            classification="INFORMATIONAL_CHANGE",
            field="hreflang",
            before=[{"lang": "en", "url": "https://example.com/en"}],
            after=[{"lang": "zh", "url": "https://example.com/zh"}],
            evidence="hreflang changed",
        )
    ]

    csv_text = crawl_diff_csv_to_string(changes)
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)

    assert reader.fieldnames == [
        "url",
        "change_type",
        "classification",
        "field",
        "before",
        "after",
        "evidence",
    ]
    assert rows[0]["url"] == "https://example.com/中文"
    assert rows[0]["before"] == '[{"lang":"en","url":"https://example.com/en"}]'
    assert rows[0]["after"] == '[{"lang":"zh","url":"https://example.com/zh"}]'


def test_file_writer_round_trips_csv(tmp_path) -> None:
    """The path writer must persist exactly the in-memory representation."""
    from audit_rules.snapshot_diff import (
        SnapshotChange,
        crawl_diff_csv_to_string,
        write_crawl_diff_csv,
    )

    changes = [
        SnapshotChange(
            url="https://example.com/a",
            change_type="TITLE_CHANGED",
            classification="INFORMATIONAL_CHANGE",
            field="title",
            before="Before",
            after="After",
            evidence="title changed",
        )
    ]
    target = write_crawl_diff_csv(changes, tmp_path / "crawl-diff.csv")

    assert target.read_text(encoding="utf-8") == crawl_diff_csv_to_string(changes)
