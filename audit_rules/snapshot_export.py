"""Bounded transport for a registered portable audit snapshot."""

import base64
import hashlib
from pathlib import Path


class SnapshotExportError(ValueError):
    """Raised when a snapshot cannot be safely exported."""


def export_snapshot_file(path: str | Path, *, max_bytes: int = 50_000_000) -> dict:
    """Read one snapshot once and return integrity-checked base64 transport data."""
    target = Path(path)
    if not target.is_file():
        raise SnapshotExportError("snapshot file does not exist")
    limit = max(1, min(int(max_bytes), 100_000_000))
    size = target.stat().st_size
    if size > limit:
        raise SnapshotExportError(
            f"snapshot size {size} exceeds export limit {limit}")
    payload = target.read_bytes()
    from audit_rules.snapshot import snapshot_from_gzip_bytes
    snapshot_from_gzip_bytes(payload)
    return {
        "filename": target.name,
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "content_base64": base64.b64encode(payload).decode("ascii"),
        "schema_version": "audit-snapshot-v1",
    }
