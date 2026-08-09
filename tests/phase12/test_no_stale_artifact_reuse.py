"""ZIP construction is registry- and provenance-bound, never directory-glob based."""

import json
import hashlib
import zipfile
from io import BytesIO


def test_current_run_zip_excludes_unregistered_pre_fix_file(tmp_path):
    from server import _build_current_run_zip

    old = tmp_path / "old-pre-fix.coverage.csv"
    old.write_text("stale", encoding="utf-8")
    current = tmp_path / "current.coverage.csv"
    current.write_text("current", encoding="utf-8")
    replay = tmp_path / "current.audit-replay-v1.json.gz"
    replay.write_bytes(b"replay")
    required = {
        "audit_replay": replay,
        "coverage_csv": current,
    }
    for kind in (
        "task_csv", "manual_review_md", "audit_score_json", "audit_snapshot",
        "master_report_md", "master_report_pdf", "md", "pdf", "per_page_csv",
        "sitemap_recon_csv", "external_links_csv", "content_audit_csv",
        "extended_checks_csv",
    ):
        path = tmp_path / f"current.{kind}"
        path.write_text(kind, encoding="utf-8")
        required[kind] = path
    manifest = tmp_path / "current.artifact-manifest.json"
    manifest.write_text(json.dumps({
        "session_id": "current", "git_head": "c" * 40,
        "artifacts": [{
            "artifact_name": path.name, "artifact_type": kind,
            "generated_at": "2026-08-09T08:00:00Z", "git_head": "c" * 40,
            "session_id": "current",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        } for kind, path in sorted(required.items())],
    }), encoding="utf-8")
    session = {"id": "current", "url": "https://example.com/", "pages_done": 315}
    artifacts = [
        {"kind": kind, "path": str(path)} for kind, path in required.items()
    ] + [{"kind": "artifact_manifest", "path": str(manifest)}]

    result = _build_current_run_zip(session, artifacts)

    with zipfile.ZipFile(BytesIO(result["zip_bytes"])) as archive:
        names = set(archive.namelist())
        assert archive.testzip() is None
    assert old.name not in names
    assert current.name in names
    assert replay.name in names
    assert manifest.name in names
