"""Every merge-final artifact must be attributable to one current run."""

import hashlib
import json


def test_manifest_records_current_session_head_and_artifact_hashes(monkeypatch, tmp_path):
    import runner

    coverage = tmp_path / "example.coverage.csv"
    coverage.write_text("audit_id\n1\n", encoding="utf-8")
    replay = tmp_path / "example.audit-replay-v1.json.gz"
    replay.write_bytes(b"replay")
    artifacts = [
        {"kind": "coverage_csv", "path": str(coverage)},
        {"kind": "audit_replay", "path": str(replay)},
    ]
    registered = []
    monkeypatch.setattr(runner.state, "list_artifacts", lambda sid: artifacts)
    monkeypatch.setattr(
        runner.state, "add_artifact",
        lambda sid, kind, path: registered.append((sid, kind, path)),
    )

    path = runner._write_artifact_manifest(
        "session-current", "https://example.com/", "example.com", "run-1",
        tmp_path, git_head="b" * 40, generated_at="2026-08-09T08:00:00Z",
    )
    manifest = json.loads(path.read_text(encoding="utf-8"))

    assert manifest["session_id"] == "session-current"
    assert manifest["git_head"] == "b" * 40
    assert manifest["source_url"] == "https://example.com/"
    assert manifest["generated_at"] == "2026-08-09T08:00:00Z"
    assert manifest["artifacts"] == [
        {
            "artifact_name": replay.name, "artifact_type": "audit_replay",
            "generated_at": "2026-08-09T08:00:00Z", "git_head": "b" * 40,
            "session_id": "session-current",
            "sha256": hashlib.sha256(b"replay").hexdigest(),
        },
        {
            "artifact_name": coverage.name, "artifact_type": "coverage_csv",
            "generated_at": "2026-08-09T08:00:00Z", "git_head": "b" * 40,
            "session_id": "session-current",
            "sha256": hashlib.sha256(coverage.read_bytes()).hexdigest(),
        },
    ]
    assert registered == [("session-current", "artifact_manifest", path)]
