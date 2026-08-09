"""External provider evidence artifact contracts."""

import csv
import io
import json


def test_external_artifacts_are_emitted_only_for_collected_provider_data():
    from audit_rules.external_artifacts import build_external_artifacts

    artifacts = build_external_artifacts({
        "gsc": {"current_rows": [{"page": "https://example.com/", "query": "x",
                                    "country": "usa", "device": "MOBILE",
                                    "clicks": 2, "impressions": 10,
                                    "ctr": 0.2, "position": 3}],
                "previous_rows": [], "errors": []},
        "semrush": {"target": "example.com", "lost_links": [{
            "source_url": "https://ref.example/", "target_url": "https://example.com/",
            "domain_score": 50, "is_lost": True}], "errors": []},
        "server_logs": {"processed_lines": 10, "status_counts": {"200": 8},
                        "bot_counts": {"Googlebot": 3}, "waste_bot_counts": {},
                        "errors": []},
        "wordpress_privileged": {"schema_version": "wordpress-audit-v1",
                                  "site_host": "example.com", "plugins": []},
    })

    assert set(artifacts) == {
        "search_performance_csv", "backlinks_csv", "server_log_analysis_csv",
        "wordpress_audit_json"}
    assert next(csv.DictReader(io.StringIO(
        artifacts["search_performance_csv"]))) ["period"] == "current"
    assert json.loads(artifacts["wordpress_audit_json"])["site_host"] == "example.com"


def test_runner_registers_external_evidence_files(tmp_path, monkeypatch):
    import runner

    registered = []
    monkeypatch.setattr(
        runner.state, "add_artifact",
        lambda sid, kind, path: registered.append((kind, path)))
    paths = runner._write_external_evidence_artifacts(
        "session-1", {"ga4": {"property": {"name": "properties/1"}, "errors": []}},
        "example.com", "20260809-1200", tmp_path)

    assert set(paths) == {"ga4_audit_json"}
    assert registered[0][0] == "ga4_audit_json"
