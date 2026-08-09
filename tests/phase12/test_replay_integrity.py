"""Fail-closed validation for audit replay completeness and hygiene."""

from copy import deepcopy

import pytest


def _valid_document():
    from audit_rules.replay import build_replay_document

    return build_replay_document(
        source_url="https://example.com/",
        git_head="c" * 40,
        generated_at="2026-08-09T06:00:00Z",
        crawl_metadata={
            "crawl_started_at": "2026-08-09T05:59:00Z",
            "crawl_completed_at": "2026-08-09T06:00:00Z",
            "crawl_parameters": {"total_max_pages": 1000},
            "truncation_status": "NOT_TRUNCATED",
            "politeness": "polite",
            "sitemap_fill": {"enabled": True, "cap": 500},
        },
        pages=[
            {"url": "https://example.com/a", "status_code": 200},
            {"url": "https://example.com/b", "status_code": 200},
        ],
        links=[],
        site_data={"robots_txt": {"found": True}},
        sitemap_reconciliation={"sitemap_total": 2, "crawl_total": 2},
        crawl_completeness={"pages_crawled": 2, "audit_complete": True},
        provider_evidence={},
    )


@pytest.mark.parametrize("field", [
    "crawl_metadata", "pages", "links", "site_data",
    "sitemap_reconciliation", "crawl_completeness", "provider_evidence",
])
def test_validator_rejects_each_missing_replay_collection(field):
    """Dropping any replay input collection must make the artifact invalid."""
    from audit_rules.replay import ReplayValidationError, validate_replay_document

    document = _valid_document()
    document.pop(field)

    with pytest.raises(ReplayValidationError):
        validate_replay_document(document)


def test_validator_rejects_duplicate_or_empty_page_urls():
    """A count-correct artifact must not hide duplicate or missing URLs."""
    from audit_rules.replay import ReplayValidationError, validate_replay_document

    duplicate = _valid_document()
    duplicate["pages"][1]["url"] = duplicate["pages"][0]["url"]
    empty = _valid_document()
    empty["pages"][1]["url"] = ""

    with pytest.raises(ReplayValidationError, match="page URLs"):
        validate_replay_document(duplicate)
    with pytest.raises(ReplayValidationError, match="page URLs"):
        validate_replay_document(empty)


def test_validator_rejects_completed_crawl_page_mismatch_without_caller_hint():
    """Internal completed-page parity must not depend on a caller argument."""
    from audit_rules.replay import ReplayValidationError, validate_replay_document

    document = _valid_document()
    document["crawl_completeness"]["pages_crawled"] = 315

    with pytest.raises(ReplayValidationError, match="REPLAY_ARTIFACT_INCOMPLETE"):
        validate_replay_document(document)


def test_validator_rejects_unsupported_schema_wrong_source_and_unstable_page_order():
    """A permissive loader must not accept another schema/site/order."""
    from audit_rules.replay import ReplayValidationError, validate_replay_document

    unsupported = _valid_document()
    unsupported["schema_version"] = "2.0"
    with pytest.raises(ReplayValidationError, match="schema_version"):
        validate_replay_document(unsupported)

    with pytest.raises(ReplayValidationError, match="source_url"):
        validate_replay_document(
            _valid_document(), expected_source_url="https://other.example/")

    unsorted = _valid_document()
    unsorted["pages"].reverse()
    with pytest.raises(ReplayValidationError, match="stable URL order"):
        validate_replay_document(unsorted)


def test_builder_removes_nested_credential_like_fields_and_validator_rejects_them():
    """Credential fields outside response headers must also fail closed."""
    from audit_rules.replay import (
        ReplayValidationError, build_replay_document, validate_replay_document,
    )

    source = _valid_document()
    source["site_data"] = {
        "robots_txt": {"found": True},
        "api_key": "SECRET",
        "nested": {"refresh_token": "SECRET", "safe": "retained"},
    }
    rebuilt = build_replay_document(
        source_url=source["source_url"],
        git_head=source["git_head"],
        generated_at=source["generated_at"],
        crawl_metadata=source["crawl_metadata"],
        pages=source["pages"],
        links=source["links"],
        site_data=source["site_data"],
        sitemap_reconciliation=source["sitemap_reconciliation"],
        crawl_completeness=source["crawl_completeness"],
        provider_evidence={},
    )
    assert "api_key" not in rebuilt["site_data"]
    assert "refresh_token" not in rebuilt["site_data"]["nested"]
    assert rebuilt["site_data"]["nested"]["safe"] == "retained"

    contaminated = deepcopy(_valid_document())
    contaminated["provider_evidence"] = {
        "pagespeed": {"authorization": "Bearer SECRET"}}
    with pytest.raises(ReplayValidationError, match="credential"):
        validate_replay_document(contaminated)


@pytest.mark.parametrize("collection,extra", [
    ("pages", {"raw_html": "<html>unsafe/uncontracted</html>"}),
    ("links", {"raw_request": "GET / HTTP/1.1"}),
])
def test_validator_rejects_fields_outside_replay_allowlists(collection, extra):
    from audit_rules.replay import ReplayValidationError, validate_replay_document

    document = _valid_document()
    if collection == "links":
        document["links"] = [{
            "source_url": "https://example.com/a",
            "target_url": "https://example.com/b",
            **extra,
        }]
        document["counts"]["link_count"] = 1
    else:
        document[collection][0].update(extra)

    with pytest.raises(ReplayValidationError, match="field"):
        validate_replay_document(document)


@pytest.mark.parametrize("name", ["authorization", "x-api-key", "x-custom-token"])
def test_validator_rechecks_response_header_allowlist_after_deserialization(name):
    from audit_rules.replay import ReplayValidationError, validate_replay_document

    document = _valid_document()
    document["pages"][0]["response_headers"] = {name: "real-value"}

    with pytest.raises(ReplayValidationError, match="header"):
        validate_replay_document(document)


def test_flat_and_page_link_aliases_deduplicate_to_one_canonical_edge():
    from audit_rules.replay import build_replay_document

    source = _valid_document()
    source["pages"][0]["links_detailed"] = [{
        "url": "https://example.com/b", "anchor": "B",
        "rel": "", "is_internal": True,
    }]


def test_link_dedupe_merges_optional_internal_classification():
    from audit_rules.replay import build_replay_document

    source = _valid_document()
    source["pages"][0]["links_detailed"] = [{
        "url": "https://example.com/b", "anchor": "B", "rel": "",
        "is_internal": True,
    }]
    document = build_replay_document(
        source_url=source["source_url"], git_head=source["git_head"],
        generated_at=source["generated_at"], crawl_metadata=source["crawl_metadata"],
        pages=source["pages"], links=[{
            "source_url": "https://example.com/a",
            "target_url": "https://example.com/b", "anchor": "B", "rel": "",
        }], site_data=source["site_data"],
        sitemap_reconciliation=source["sitemap_reconciliation"],
        crawl_completeness=source["crawl_completeness"], provider_evidence={},
    )

    assert document["counts"]["link_count"] == 1
    assert document["links"][0]["is_internal"] is True
    document = build_replay_document(
        source_url=source["source_url"], git_head=source["git_head"],
        generated_at=source["generated_at"],
        crawl_metadata=source["crawl_metadata"], pages=source["pages"],
        links=[{
            "from": "https://example.com/a", "href": "https://example.com/b",
            "anchor_text": "B", "rel": "", "is_internal": True,
        }], site_data=source["site_data"],
        sitemap_reconciliation=source["sitemap_reconciliation"],
        crawl_completeness=source["crawl_completeness"], provider_evidence={},
    )

    assert document["counts"]["link_count"] == 1
    assert document["links"] == [{
        "source_url": "https://example.com/a",
        "target_url": "https://example.com/b",
        "anchor": "B", "rel": "", "is_internal": True,
    }]


def test_validator_rejects_unknown_provider_evidence_fields():
    from audit_rules.replay import ReplayValidationError, validate_replay_document

    document = _valid_document()
    document["provider_evidence"] = {
        "gsc": {"status": "CHECKED", "data": {
            "current_rows": [{"page": "https://example.com/a"}],
            "raw_http_response": {"headers": {"x-debug": "value"}},
        }},
        "provider_status": {"gsc": "CHECKED"},
    }

    with pytest.raises(ReplayValidationError, match="provider evidence field"):
        validate_replay_document(document)


def test_validator_rejects_unknown_pagespeed_snapshot_fields():
    from audit_rules.replay import ReplayValidationError, validate_replay_document

    document = _valid_document()
    document["provider_evidence"] = {
        "pagespeed": {
            "status": "CHECKED", "strategy": "mobile", "collected_at": "",
            "snapshots": [{
                "url": "https://example.com/a", "strategy": "mobile",
                "psi_status": "success", "raw_http_response": {"kind": "forbidden"},
            }],
        },
        "provider_status": {},
    }

    with pytest.raises(ReplayValidationError, match="pagespeed evidence field"):
        validate_replay_document(document)


@pytest.mark.parametrize("status,snapshots", [
    ("CHECKED", []),
    ("BOGUS", []),
    ("LIVE_VALIDATION_PENDING", [{
        "url": "https://example.com/a", "strategy": "mobile",
        "psi_status": "success",
    }]),
])
def test_pagespeed_status_must_match_successful_snapshot_evidence(status, snapshots):
    from audit_rules.replay import ReplayValidationError, validate_replay_document

    document = _valid_document()
    document["provider_evidence"] = {
        "pagespeed": {
            "status": status, "strategy": "mobile", "collected_at": "",
            "snapshots": snapshots,
        },
        "provider_status": {},
    }

    with pytest.raises(ReplayValidationError, match="pagespeed status"):
        validate_replay_document(document)


@pytest.mark.parametrize("status", ["BOGUS", "CHECKED"])
def test_provider_status_must_be_valid_and_consistent_with_evidence(status):
    from audit_rules.replay import ReplayValidationError, validate_replay_document

    document = _valid_document()
    document["provider_evidence"] = {"provider_status": {"gsc": status}}

    with pytest.raises(ReplayValidationError, match="provider status"):
        validate_replay_document(document)
