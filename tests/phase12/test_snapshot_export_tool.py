"""Portable snapshot export payload contract."""

import base64
import hashlib

import pytest


def test_snapshot_export_returns_bounded_verified_base64(tmp_path):
    from audit_rules.context import SiteContext
    from audit_rules.snapshot import build_snapshot, snapshot_to_gzip_bytes
    from audit_rules.snapshot_export import export_snapshot_file

    payload = snapshot_to_gzip_bytes(build_snapshot(
        SiteContext(base_url="https://example.com"), [],
        created_at="2026-08-09T00:00:00Z"))
    path = tmp_path / "example.audit-snapshot-v1.json.gz"
    path.write_bytes(payload)
    result = export_snapshot_file(path, max_bytes=1024)

    assert result["filename"] == path.name
    assert result["size_bytes"] == len(payload)
    assert base64.b64decode(result["content_base64"]) == payload
    assert result["sha256"] == hashlib.sha256(payload).hexdigest()


def test_snapshot_export_rejects_missing_or_oversized_file(tmp_path):
    from audit_rules.snapshot_export import SnapshotExportError, export_snapshot_file

    with pytest.raises(SnapshotExportError, match="does not exist"):
        export_snapshot_file(tmp_path / "missing.gz")
    path = tmp_path / "large.gz"
    path.write_bytes(b"12345")
    with pytest.raises(SnapshotExportError, match="exceeds"):
        export_snapshot_file(path, max_bytes=4)
