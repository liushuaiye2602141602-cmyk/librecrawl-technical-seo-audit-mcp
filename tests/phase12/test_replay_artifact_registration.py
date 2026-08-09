"""Runner registration and explicit replay-artifact failure semantics."""

from pathlib import Path
from types import SimpleNamespace


def _inputs():
    pages = [{
        "url": "https://example.com/", "status_code": 200,
        "title": "Home", "internal_links": 1, "external_links": 0,
        "links_detailed": [{
            "url": "https://example.com/about", "anchor": "About",
            "is_internal": True, "rel": "",
        }],
    }, {
        "url": "https://example.com/about", "status_code": 200,
        "title": "About", "internal_links": 1, "external_links": 0,
        "links_detailed": [{
            "url": "https://example.com/", "anchor": "Home",
            "is_internal": True, "rel": "",
        }],
    }]
    return {
        "pages": pages,
        "links": [],
        "site_data": {
            "robots_txt": {"found": True},
            "sitemap": {"found": True, "url": "https://example.com/sitemap.xml"},
        },
        "reconciliation": {
            "sitemap_total": 2, "crawl_total": 2,
            "sitemap_only": [], "crawl_only": [],
        },
        "completeness": {
            "pages_crawled": 2, "audit_complete": True,
            "max_pages": 1000, "max_pages_hit": False,
            "incomplete_reasons": [],
        },
        "session": {
            "started_at": 1786251000.0, "finished_at": 1786251100.0,
            "upstream_crawl_id": 7, "total_max_pages": 1000,
            "chunk_target_pages": 25, "politeness": "polite",
            "settings": {
                "fill_sitemap_orphans": True, "sitemap_fill_cap": 500,
            },
        },
        "fill_summary": {
            "attempted": 1, "success_count": 1, "cap_hit": False,
        },
    }


def test_runner_writes_validated_replay_and_registers_complete_link_graph(
        monkeypatch, tmp_path):
    """Omitting registration or per-page link normalization must fail."""
    import runner
    from audit_rules.replay import load_replay_artifact

    registered = []
    events = []
    monkeypatch.setattr(
        runner.state, "add_artifact",
        lambda sid, kind, path: registered.append((sid, kind, Path(path))))
    monkeypatch.setattr(
        runner.state, "log_event",
        lambda sid, kind, detail=None: events.append((sid, kind, detail)))
    monkeypatch.setenv("AUDIT_GIT_HEAD", "e" * 40)
    data = _inputs()

    path = runner._write_replay_artifact(
        "session-1", "https://example.com/", "example.com", "20260809-0600",
        tmp_path, audit_runner=SimpleNamespace(providers={}, last_shared_data={}),
        **data,
    )

    assert path is not None
    assert registered == [("session-1", "audit_replay", path)]
    loaded = load_replay_artifact(
        path, expected_source_url="https://example.com/",
        expected_completed_pages=2)
    assert loaded["git_head"] == "e" * 40
    assert loaded["counts"] == {"link_count": 2, "page_count": 2}
    assert loaded["crawl_metadata"]["crawl_parameters"] == {
        "chunk_target_pages": 25,
        "fill_sitemap_orphans": True,
        "politeness": "polite",
        "sitemap_fill_cap": 500,
        "total_max_pages": 1000,
    }
    replay_event = next(
        detail for _, kind, detail in events
        if kind == "v3_replay_artifact_generated"
    )
    assert replay_event == {
        "pages": 2, "links": 2,
        "parity": "REPLAY_PARITY_PASS",
        "sha256": replay_event["sha256"],
    }


def test_runner_replay_persists_technology_profile(monkeypatch, tmp_path):
    """The crawl-time technology profile must survive in the replay."""
    import runner
    from audit_rules.replay import load_replay_artifact

    monkeypatch.setattr(
        runner.state, "add_artifact",
        lambda sid, kind, path: None)
    monkeypatch.setattr(
        runner.state, "log_event",
        lambda sid, kind, detail=None: None)
    monkeypatch.setenv("AUDIT_GIT_HEAD", "e" * 40)
    data = _inputs()
    profile = {
        "schema_version": "technology-profile-v1",
        "detector_version": "1.0.0",
        "signature_registry_version": "1.0.0",
        "source_url": "https://example.com/",
        "detections": [{
            "category": "Analytics",
            "technology_name": "GA4",
            "technology_type": "Analytics",
            "status": "DETECTED",
            "confidence": "High",
            "version": "Unknown",
            "detection_sources": [],
        }],
        "detection_status": "COMPLETE",
    }
    audit_runner = SimpleNamespace(
        providers={}, last_shared_data={"technology_profile": profile})

    path = runner._write_replay_artifact(
        "session-1", "https://example.com/", "example.com", "20260809-0600",
        tmp_path, audit_runner=audit_runner, **data)

    loaded = load_replay_artifact(
        path, expected_source_url="https://example.com/",
        expected_completed_pages=2)
    stored = loaded["technology_profile"]
    assert stored["schema_version"] == "technology-profile-v1"
    assert stored["detections"][0]["technology_name"] == "GA4"
    assert stored["detections"][0]["status"] == "DETECTED"


def test_runner_marks_replay_partial_and_does_not_register_invalid_output(
        monkeypatch, tmp_path):
    """A failed replay writer must not make the bundle appear complete."""
    import runner
    import audit_rules.replay as replay

    registered = []
    events = []
    monkeypatch.setattr(
        runner.state, "add_artifact",
        lambda sid, kind, path: registered.append((sid, kind, path)))
    monkeypatch.setattr(
        runner.state, "log_event",
        lambda sid, kind, detail=None: events.append((sid, kind, detail)))
    monkeypatch.setattr(
        replay, "write_replay_artifact",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            replay.ReplayValidationError("REPLAY_ARTIFACT_INCOMPLETE")))
    data = _inputs()

    path = runner._write_replay_artifact(
        "session-1", "https://example.com/", "example.com", "20260809-0600",
        tmp_path, audit_runner=SimpleNamespace(providers={}, last_shared_data={}),
        **data,
    )

    assert path is None
    assert registered == []
    assert ("session-1", "v3_artifact_failed", {
        "artifact": "audit_replay", "error_type": "ReplayValidationError",
        "reason": "REPLAY_ARTIFACT_INCOMPLETE",
    }) in events
    assert ("session-1", "v3_artifacts_partial", {
        "failed_artifact": "audit_replay",
    }) in events
    assert not list(tmp_path.glob("*.audit-replay-v1.json.gz"))
