"""Build and verify a production-like offline V3 artifact bundle."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import zipfile
from typing import Callable


_PROVIDER_KINDS = {
    "performance_csv", "search_performance_csv", "backlinks_csv",
    "server_log_analysis_csv", "wordpress_audit_json", "ga4_audit_json",
    "render_audit_json", "availability_audit_json",
}

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


def _export() -> dict:
    return {
        "site_check": {
            "robots_txt": {"found": True, "disallow_count": 0},
            "sitemap": {"found": True, "url": "https://example.com/sitemap.xml"},
        },
        "pages": [{
            "url": "https://example.com/", "status_code": 200,
            "title": "Example Home", "meta_description": "Example audit page",
            "h1": ["Example"], "word_count": 500,
            "canonical_url": "https://example.com/", "robots": "index,follow",
            "internal_links": 1, "external_links": 0, "links_detailed": [],
            "images": [], "json_ld": [], "hreflang": [],
        }],
        "links": [],
    }


def run_validation(
    output_dir: str | Path,
    *,
    pdf_renderer: Callable[[str, Path, str], None] | None = None,
) -> dict:
    """Create real applicable artifacts, zip them, and validate key contracts."""
    import runner as production_runner
    import pdf_report
    from audit_rules import integration
    from audit_rules.checks.audit_deliverables import generate_task_csv

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    registered: dict[str, Path] = {}
    events = []
    original_add = production_runner.state.add_artifact
    original_log = production_runner.state.log_event
    original_render_pdf = pdf_report.render_pdf
    env_names = [
        "MASTER_AUDIT_V3_ENABLED", "MASTER_AUDIT_PSI_ENABLED",
        "MASTER_AUDIT_GSC_ENABLED", "MASTER_AUDIT_SEMRUSH_ENABLED",
        "MASTER_AUDIT_GA4_ENABLED", "MASTER_AUDIT_SERVER_LOGS_ENABLED",
        "MASTER_AUDIT_WORDPRESS_ENABLED", "MASTER_AUDIT_RENDER_ENABLED",
        "MASTER_AUDIT_AVAILABILITY_ENABLED", "MANUAL_REVIEW_INPUT_PATH",
        "AUDIT_SNAPSHOT_BASELINE_PATH", "AUDIT_SNAPSHOT_OUTPUT_DIR",
        "AUDIT_GIT_HEAD",
    ]
    original_env = {name: os.environ.get(name) for name in env_names}
    was_enabled = integration.is_v3_enabled()
    try:
        if pdf_renderer is not None:
            pdf_report.render_pdf = pdf_renderer
        os.environ.update({
            "MASTER_AUDIT_V3_ENABLED": "true",
            "MASTER_AUDIT_PSI_ENABLED": "false",
            "MASTER_AUDIT_GSC_ENABLED": "false",
            "MASTER_AUDIT_SEMRUSH_ENABLED": "false",
            "MASTER_AUDIT_GA4_ENABLED": "false",
            "MASTER_AUDIT_SERVER_LOGS_ENABLED": "false",
            "MASTER_AUDIT_WORDPRESS_ENABLED": "false",
            "MASTER_AUDIT_RENDER_ENABLED": "false",
            "MASTER_AUDIT_AVAILABILITY_ENABLED": "false",
            "MANUAL_REVIEW_INPUT_PATH": "",
            "AUDIT_SNAPSHOT_BASELINE_PATH": "",
            "AUDIT_SNAPSHOT_OUTPUT_DIR": str(target),
            "AUDIT_GIT_HEAD": "f" * 40,
        })
        production_runner.state.add_artifact = (
            lambda sid, kind, path: registered.__setitem__(kind, Path(path)))
        production_runner.state.log_event = (
            lambda sid, kind, detail=None: events.append((kind, detail)))
        integration.enable_v3()
        integration.reset_runner_cache()

        export = _export()
        snapshot_data = production_runner._prepare_snapshot_artifacts(
            "validation", export, "https://example.com", "example.com",
            "validation", target)
        findings, coverage, coverage_csv = integration.run_v3_pipeline(
            export_data=export, existing_data=snapshot_data,
            base_url="https://example.com")
        audit_runner = integration._get_runner()

        production_runner._write_replay_artifact(
            "validation", "https://example.com", "example.com", "validation",
            target,
            pages=export["pages"], links=export["links"],
            site_data=export["site_check"],
            reconciliation={
                "sitemap_total": 1, "crawl_total": 1,
                "sitemap_only": [], "crawl_only": [],
            },
            completeness={
                "pages_crawled": 1, "audit_complete": True,
                "max_pages": 1, "max_pages_hit": False,
                "incomplete_reasons": [],
            },
            session={
                "started_at": 1, "finished_at": 2,
                "upstream_crawl_id": 1, "total_max_pages": 1,
                "settings": {
                    "chunk_target_pages": 1, "politeness": "polite",
                    "fill_sitemap_orphans": True, "sitemap_fill_cap": 1,
                },
            },
            fill_summary={"attempted": 0, "success_count": 0, "cap_hit": False},
            audit_runner=audit_runner,
        )

        coverage_path = target / "example.com-validation.coverage.csv"
        coverage_path.write_text(coverage_csv, encoding="utf-8")
        production_runner.state.add_artifact(
            "validation", "coverage_csv", coverage_path)
        production_runner._write_manual_review_artifact(
            "validation", "https://example.com", "example.com",
            "validation", target)
        production_runner._write_v3_summary_artifacts(
            "validation", findings, coverage, "example.com", "validation",
            target, audit_runner)
        production_runner._write_external_evidence_artifacts(
            "validation", audit_runner.last_shared_data, "example.com",
            "validation", target)
        production_runner._write_master_report_artifacts(
            "validation", "https://example.com", findings, coverage,
            "example.com", "validation", target)
        task_path = target / "example.com-validation.master-audit-tasks.csv"
        task_path.write_text(
            generate_task_csv(findings, audit_runner.registry), encoding="utf-8")
        production_runner.state.add_artifact("validation", "task_csv", task_path)

        zip_path = target / "example.com-validation.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("SUMMARY.txt", "Offline V3 artifact validation\n")
            for kind, path in sorted(registered.items()):
                archive.write(path, arcname=path.name)
        with zipfile.ZipFile(zip_path) as archive:
            archive.testzip()
            zip_names = set(archive.namelist())

        pdf_path = registered["master_report_pdf"]
        return {
            "coverage_rows": len(coverage),
            "finding_count": len(findings),
            "artifact_kinds": sorted(registered),
            "provider_artifacts": sorted(set(registered) & _PROVIDER_KINDS),
            "zip_valid": "SUMMARY.txt" in zip_names
                         and all(path.name in zip_names for path in registered.values()),
            "pdf_valid": pdf_path.read_bytes().startswith(b"%PDF"),
            "zip_path": str(zip_path),
            "events": events,
        }
    finally:
        production_runner.state.add_artifact = original_add
        production_runner.state.log_event = original_log
        pdf_report.render_pdf = original_render_pdf
        integration.reset_runner_cache()
        if was_enabled:
            integration.enable_v3()
        else:
            integration.disable_v3()
        for name, value in original_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="librecrawl-v3-validation-") as directory:
        print(json.dumps(run_validation(directory), indent=2, sort_keys=True))
