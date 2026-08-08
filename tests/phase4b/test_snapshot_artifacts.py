"""TDD coverage for snapshot bytes and crawl-diff artifact assembly."""

from __future__ import annotations

from copy import deepcopy

import pytest

from audit_rules.snapshot import (
    SnapshotValidationError,
    snapshot_from_gzip_bytes,
    snapshot_to_gzip_bytes,
)
from audit_rules.integration import build_snapshot_artifacts


def _export(*, title: str = "Home") -> dict:
    return {
        "site_check": {},
        "pages": [
            {
                "url": "https://example.com/",
                "status_code": 200,
                "title": title,
                "meta_description": "Example description",
                "h1": "Welcome",
                "canonical_url": "https://example.com/",
                "robots": "index, follow",
                "word_count": 300,
                "internal_links_count": 1,
                "linked_from": [],
            }
        ],
        "links": [],
    }


def test_snapshot_byte_round_trip_is_deterministic():
    snapshot_bytes, changes, diff_csv = build_snapshot_artifacts(
        _export(),
        "https://example.com",
        created_at="2026-08-09T00:00:00Z",
    )

    snapshot = snapshot_from_gzip_bytes(snapshot_bytes)
    assert snapshot["schema_version"] == 1
    assert snapshot["base_url"] == "https://example.com"
    assert snapshot_to_gzip_bytes(snapshot) == snapshot_bytes
    assert changes == []
    assert diff_csv == ""


def test_snapshot_from_bytes_wraps_corrupt_payload():
    with pytest.raises(SnapshotValidationError, match="Unable to decode snapshot bytes"):
        snapshot_from_gzip_bytes(b"not-a-snapshot")


def test_build_snapshot_artifacts_compares_valid_baseline(tmp_path):
    baseline_bytes, _, _ = build_snapshot_artifacts(
        _export(title="Old title"),
        "https://example.com",
        created_at="2026-08-08T00:00:00Z",
    )
    baseline_path = tmp_path / "baseline.audit-snapshot-v1.json.gz"
    baseline_path.write_bytes(baseline_bytes)

    current_bytes, changes, diff_csv = build_snapshot_artifacts(
        _export(title="New title"),
        "https://example.com",
        baseline_path=baseline_path,
        created_at="2026-08-09T00:00:00Z",
    )

    assert snapshot_from_gzip_bytes(current_bytes)["created_at"] == "2026-08-09T00:00:00Z"
    assert ("TITLE_CHANGED", "INFORMATIONAL_CHANGE") in [
        (change.change_type, change.classification) for change in changes
    ]
    assert diff_csv.startswith("url,change_type,classification,field,before,after,evidence\n")
    assert "TITLE_CHANGED" in diff_csv


def test_build_snapshot_artifacts_emits_header_for_identical_valid_baseline(tmp_path):
    baseline_bytes, _, _ = build_snapshot_artifacts(
        _export(),
        "https://example.com",
        created_at="2026-08-08T00:00:00Z",
    )
    baseline_path = tmp_path / "baseline.audit-snapshot-v1.json.gz"
    baseline_path.write_bytes(baseline_bytes)

    _, changes, diff_csv = build_snapshot_artifacts(
        deepcopy(_export()),
        "https://example.com",
        baseline_path=baseline_path,
        created_at="2026-08-09T00:00:00Z",
    )

    assert changes == []
    assert diff_csv == "url,change_type,classification,field,before,after,evidence\n"


def test_build_snapshot_artifacts_rejects_corrupt_baseline(tmp_path):
    baseline_path = tmp_path / "corrupt.json.gz"
    baseline_path.write_bytes(b"broken")

    with pytest.raises(SnapshotValidationError, match="Unable to load snapshot"):
        build_snapshot_artifacts(
            _export(),
            "https://example.com",
            baseline_path=baseline_path,
        )


def test_runner_registers_snapshot_without_baseline(tmp_path, monkeypatch):
    import runner

    registered = []
    monkeypatch.delenv("AUDIT_SNAPSHOT_BASELINE_PATH", raising=False)
    monkeypatch.setenv("AUDIT_SNAPSHOT_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(runner.state, "add_artifact", lambda sid, kind, path: registered.append((kind, path)))

    existing_data = runner._prepare_snapshot_artifacts(
        "session-1",
        _export(),
        "https://example.com",
        "example.com",
        "20260809-1200",
        tmp_path / "reports",
    )

    assert existing_data == {
        "snapshot_changes": [],
        "snapshot_baseline_available": False,
    }
    assert [kind for kind, _ in registered] == ["audit_snapshot"]
    assert registered[0][1].name == "example.com-20260809-1200.audit-snapshot-v1.json.gz"
    assert registered[0][1].read_bytes()[:2] == b"\x1f\x8b"


def test_runner_registers_diff_for_valid_baseline(tmp_path, monkeypatch):
    import runner

    baseline_bytes, _, _ = build_snapshot_artifacts(
        _export(title="Before"),
        "https://example.com",
        created_at="2026-08-08T00:00:00Z",
    )
    baseline = tmp_path / "baseline.json.gz"
    baseline.write_bytes(baseline_bytes)
    registered = []
    monkeypatch.setenv("AUDIT_SNAPSHOT_BASELINE_PATH", str(baseline))
    monkeypatch.setenv("AUDIT_SNAPSHOT_OUTPUT_DIR", str(tmp_path / "snapshots"))
    monkeypatch.setattr(runner.state, "add_artifact", lambda sid, kind, path: registered.append((kind, path)))

    existing_data = runner._prepare_snapshot_artifacts(
        "session-2",
        _export(title="After"),
        "https://example.com",
        "example.com",
        "20260809-1201",
        tmp_path / "reports",
    )

    assert existing_data["snapshot_baseline_available"] is True
    assert existing_data["snapshot_changes"]
    assert [kind for kind, _ in registered] == ["audit_snapshot", "crawl_diff_csv"]
    assert registered[1][1].read_text(encoding="utf-8").startswith("url,change_type,")


def test_runner_logs_corrupt_baseline_and_keeps_current_snapshot(tmp_path, monkeypatch):
    import runner

    baseline = tmp_path / "corrupt.json.gz"
    baseline.write_bytes(b"broken")
    registered = []
    events = []
    monkeypatch.setenv("AUDIT_SNAPSHOT_BASELINE_PATH", str(baseline))
    monkeypatch.delenv("AUDIT_SNAPSHOT_OUTPUT_DIR", raising=False)
    monkeypatch.setattr(runner.state, "add_artifact", lambda sid, kind, path: registered.append((kind, path)))
    monkeypatch.setattr(runner.state, "log_event", lambda sid, kind, detail=None: events.append((kind, detail)))

    existing_data = runner._prepare_snapshot_artifacts(
        "session-3",
        _export(),
        "https://example.com",
        "example.com",
        "20260809-1202",
        tmp_path / "reports",
    )

    assert existing_data["snapshot_baseline_available"] is False
    assert [kind for kind, _ in registered] == ["audit_snapshot"]
    assert [kind for kind, _ in events] == ["snapshot_diff_failed"]
