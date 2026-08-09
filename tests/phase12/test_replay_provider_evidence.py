"""Normalized real-provider evidence stored in replay artifacts."""

import json
from types import SimpleNamespace


def test_provider_evidence_keeps_real_psi_snapshots_without_provider_secrets():
    """Serializing provider objects must never leak their credentials/config."""
    from audit_rules.providers.performance_snapshot import PerformanceSnapshot
    from audit_rules.replay import build_provider_evidence

    first = PerformanceSnapshot(
        url="https://example.com/z", requested_url="https://example.com/z",
        strategy="mobile", fetch_timestamp="2026-08-09T06:00:00Z",
        psi_status="success", field_data_scope="NONE",
        lab_performance_score=72, lab_lcp_ms=4100,
    )
    second = PerformanceSnapshot(
        url="https://example.com/a", requested_url="https://example.com/a",
        strategy="mobile", fetch_timestamp="2026-08-09T05:59:00Z",
        psi_status="success", field_data_scope="NONE",
        lab_performance_score=91, lab_lcp_ms=2100,
    )
    provider = SimpleNamespace(
        _cache={(first.url, "mobile"): first, (second.url, "mobile"): second},
        _strategies=["mobile"],
        _api_key="MUST_NOT_APPEAR",
    )
    runner = SimpleNamespace(
        providers={"PageSpeed API": provider},
        last_shared_data={
            "gsc": {
                "site_url": "sc-domain:example.com",
                "current_rows": [{
                    "page": "https://example.com/a", "query": "example",
                    "clicks": 3, "impressions": 10, "ctr": 0.3,
                    "position": 2.0,
                }],
                "previous_rows": [], "errors": [],
            },
        },
    )

    evidence = build_provider_evidence(runner)

    assert evidence["pagespeed"]["status"] == "CHECKED"
    assert evidence["pagespeed"]["strategy"] == "mobile"
    assert [row["url"] for row in evidence["pagespeed"]["snapshots"]] == [
        "https://example.com/a", "https://example.com/z"]
    assert evidence["provider_status"] == {
        "availability_snapshot": "LIVE_VALIDATION_PENDING",
        "ga4": "LIVE_VALIDATION_PENDING",
        "gsc": "CHECKED",
        "render_snapshot": "LIVE_VALIDATION_PENDING",
        "semrush": "LIVE_VALIDATION_PENDING",
        "server_logs": "LIVE_VALIDATION_PENDING",
        "wordpress_privileged": "LIVE_VALIDATION_PENDING",
    }
    assert evidence["gsc"]["status"] == "CHECKED"
    assert evidence["gsc"]["data"]["current_rows"][0]["clicks"] == 3
    payload = json.dumps(evidence, sort_keys=True)
    assert "MUST_NOT_APPEAR" not in payload
    assert "api_key" not in payload.lower()


def test_provider_evidence_marks_pagespeed_pending_without_real_snapshots():
    """An enabled-looking provider without collected rows is not CHECKED."""
    from audit_rules.replay import build_provider_evidence

    runner = SimpleNamespace(
        providers={"PageSpeed API": SimpleNamespace(
            _cache={}, _strategies=["mobile"], _api_key="ignored")},
        last_shared_data={},
    )

    evidence = build_provider_evidence(runner)

    assert evidence["pagespeed"] == {
        "status": "LIVE_VALIDATION_PENDING",
        "strategy": "mobile",
        "snapshots": [],
        "collected_at": "",
    }


def test_error_only_pagespeed_snapshots_are_not_marked_checked():
    from audit_rules.providers.performance_snapshot import PerformanceSnapshot
    from audit_rules.replay import build_provider_evidence

    snapshot = PerformanceSnapshot(
        url="https://example.com/", strategy="mobile", psi_status="error",
        error="rate limited",
    )
    provider = SimpleNamespace(
        _cache={(snapshot.url, "mobile"): snapshot}, _strategies=["mobile"])

    evidence = build_provider_evidence(SimpleNamespace(
        providers={"PageSpeed API": provider}, last_shared_data={}))

    assert evidence["pagespeed"]["status"] == "LIVE_VALIDATION_PENDING"


def test_empty_or_error_only_provider_payloads_are_not_marked_checked():
    from audit_rules.replay import build_provider_evidence

    runner = SimpleNamespace(providers={}, last_shared_data={
        "gsc": {"current_rows": [], "previous_rows": [], "errors": []},
        "server_logs": {"valid_lines": 0, "errors": []},
        "render_snapshot": {"pages": [], "errors": []},
    })

    evidence = build_provider_evidence(runner)

    assert evidence["provider_status"]["gsc"] == "UNAVAILABLE"
    assert evidence["provider_status"]["server_logs"] == "UNAVAILABLE"
    assert evidence["provider_status"]["render_snapshot"] == "UNAVAILABLE"
    assert "gsc" not in evidence
    assert "server_logs" not in evidence


def test_successful_zero_row_gsc_collection_remains_checked_and_replayable():
    from audit_rules.replay import build_provider_evidence

    gsc_provider = SimpleNamespace(name="GSC API", runtime_available=True)
    runner = SimpleNamespace(
        providers={"GSC API": gsc_provider},
        last_shared_data={"gsc": {
            "current_rows": [], "previous_rows": [], "sitemaps": [],
            "inspections": {}, "errors": [],
        }},
    )

    evidence = build_provider_evidence(runner)

    assert evidence["provider_status"]["gsc"] == "CHECKED"
    assert evidence["gsc"]["collection_success"] is True
    assert evidence["gsc"]["data"]["current_rows"] == []


def test_replay_restores_psi_gsc_and_local_provider_into_real_runner(tmp_path, monkeypatch):
    from dataclasses import asdict
    from audit_rules.providers.performance_snapshot import PerformanceSnapshot
    from audit_rules.registry import load_registry
    from audit_rules.replay import (
        build_provider_evidence, build_replay_document, load_replay_artifact,
        run_replay_pipeline, write_replay_artifact,
    )
    from audit_rules.runner import RuleRunner
    from audit_rules.scoring import compute_audit_score
    from tests.phase12.test_replay_full_pipeline import _export

    class StaticProvider:
        def __init__(self, name, aliases, key, payload):
            self.name, self.aliases = name, aliases
            self.key, self.payload = key, payload

        def is_available(self): return True
        def collect(self, site_ctx, page_contexts, existing_data):
            existing_data[self.key] = self.payload
            return True

    class StaticPSI:
        name = "PageSpeed API"
        aliases = {"PageSpeed API"}
        _strategies = ["mobile"]
        _sample_limit = 5

        def __init__(self, snapshots):
            self._cache = {(s.url.rstrip("/").lower(), s.strategy): s for s in snapshots}
        def is_available(self): return True
        def collect(self, site_ctx, page_contexts, existing_data): return True
        def clear_cache(self): pass
        def get_snapshot(self, url, strategy="mobile"):
            return self._cache.get((url.rstrip("/").lower(), strategy))

    export = _export()
    snapshots = [PerformanceSnapshot(
        url=page["url"], requested_url=page["url"], strategy="mobile",
        fetch_timestamp="2026-08-09T06:00:00Z", psi_status="success",
        field_data_scope="NONE", lab_performance_score=72, lab_lcp_ms=4100,
    ) for page in export["pages"]]
    gsc = {"current_rows": [{
        "page": export["pages"][0]["url"], "query": "example", "clicks": 3,
        "impressions": 10, "ctr": 0.3, "position": 2.0,
    }], "previous_rows": [], "sitemaps": [], "inspections": {}, "errors": []}
    logs = {"processed_lines": 3, "valid_lines": 3, "malformed_lines": 0,
            "truncated": False, "status_counts": {"200": 3},
            "bot_counts": {"Googlebot": 2}, "url_counts": {"/": 3},
            "bot_url_counts": {"Googlebot|/": 2}, "waste_bot_counts": {},
            "response_time_p95_ms": 20, "errors": []}
    direct_runner = RuleRunner(load_registry(), providers={
        "PageSpeed API": StaticPSI(snapshots),
        "GSC API": StaticProvider("GSC API", {"GSC API", "GSC"}, "gsc", gsc),
        "Server Logs": StaticProvider("Server Logs", {"Server Logs"}, "server_logs", logs),
    })
    direct_findings, direct_coverage = direct_runner.run_from_export(
        export, base_url="https://example.com/",
        existing_data={"deliverable_pipeline_available": True})
    evidence = build_provider_evidence(direct_runner)
    document = build_replay_document(
        source_url="https://example.com/", git_head="e" * 40,
        generated_at="2026-08-09T06:00:00Z",
        crawl_metadata={"crawl_parameters": {}, "truncation_status": "NOT_TRUNCATED"},
        pages=export["pages"], links=export["links"], site_data=export["site_check"],
        sitemap_reconciliation={}, crawl_completeness=export["completeness"],
        provider_evidence=evidence,
    )
    target = tmp_path / "provider.audit-replay-v1.json.gz"
    write_replay_artifact(document, target, expected_completed_pages=2)

    import socket
    def forbid_network(*args, **kwargs):
        raise AssertionError("offline replay attempted a network connection")
    monkeypatch.setattr(socket.socket, "connect", forbid_network)
    replay_findings, replay_coverage = run_replay_pipeline(load_replay_artifact(target))

    finding_key = lambda item: (item.audit_id, item.url, item.detected_value, item.evidence)
    assert sorted(map(finding_key, replay_findings)) == sorted(map(finding_key, direct_findings))
    assert list(map(asdict, replay_coverage)) == list(map(asdict, direct_coverage))
    assert compute_audit_score(replay_findings, replay_coverage).to_dict() == \
        compute_audit_score(direct_findings, direct_coverage).to_dict()
