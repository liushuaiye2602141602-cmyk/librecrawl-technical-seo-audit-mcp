"""Integration layer — feature flag + shadow-mode pipeline runner.

Design (Requirement 11):
  - Feature flag MASTER_AUDIT_V3_ENABLED defaults to False (shadow/parallel mode).
  - When enabled: runs the v3 pipeline alongside existing audit code.
  - When disabled: no-op — returns empty results without side effects.
  - Do NOT modify existing check implementations.

Usage (in server.py or runner.py):
    from audit_rules.integration import run_v3_pipeline, is_v3_enabled

    if is_v3_enabled():
        findings, coverage_rows, coverage_csv = run_v3_pipeline(
            site_data=site_check_result,
            pages=crawl_pages,
            links=crawl_links,
            export_data=full_export_dict,
            base_url=seed_url,
            completeness=completeness_dict,
        )
        # Add coverage_csv to the audit zip as 9th file
        zip_files["coverage.csv"] = coverage_csv
"""

import os
from pathlib import Path
from typing import Optional, Tuple

# ============================================================
# Feature flag
# ============================================================

# Defaults to "false" (shadow/parallel mode, not production source of truth).
# Set to "true" via environment variable to enable the v3 pipeline.
# Phase 1: registry runs alongside existing code; existing output is unchanged.
MASTER_AUDIT_V3_ENABLED = (
    os.environ.get("MASTER_AUDIT_V3_ENABLED", "false").lower() == "true"
)


def is_v3_enabled() -> bool:
    """Check if the v3 audit pipeline is enabled."""
    return MASTER_AUDIT_V3_ENABLED


def enable_v3():
    """Enable v3 pipeline at runtime (for testing)."""
    global MASTER_AUDIT_V3_ENABLED
    MASTER_AUDIT_V3_ENABLED = True


def disable_v3():
    """Disable v3 pipeline at runtime."""
    global MASTER_AUDIT_V3_ENABLED
    MASTER_AUDIT_V3_ENABLED = False


# ============================================================
# Pipeline runner
# ============================================================

# Cache registry + runner to avoid reloading CSVs on every audit
_runner_cache: Optional["RuleRunner"] = None


def _get_runner() -> "RuleRunner":
    """Get or create the cached RuleRunner with default registry."""
    global _runner_cache
    if _runner_cache is None:
        from audit_rules.providers.pagespeed_provider import PageSpeedDataProvider
        from audit_rules.registry import load_registry
        from audit_rules.runner import RuleRunner

        registry = load_registry()
        pagespeed = PageSpeedDataProvider()
        _runner_cache = RuleRunner(
            registry,
            providers={pagespeed.name: pagespeed},
        )
    return _runner_cache


def run_v3_pipeline(
    site_data: dict | None = None,
    pages: list[dict] | None = None,
    links: list[dict] | None = None,
    export_data: dict | None = None,
    existing_data: dict | None = None,
    base_url: str = "",
    completeness: dict | None = None,
) -> Tuple[list, list, str]:
    """Run the v3 audit pipeline (shadow mode).

    Returns (findings, coverage_rows, coverage_csv_string) when enabled.
    Returns ([], [], "") when disabled — no-op with no side effects.

    Args:
        site_data: _site_check() result dict
        pages: Crawl page dicts from LibreCrawl export
        links: Flat links list from crawl
        export_data: Full export dict (shortcut for all params)
        existing_data: Extended check output + crawl metadata
        base_url: Seed URL
        completeness: Crawl completeness from sitemap reconciliation

    Returns:
        (findings, coverage_rows, coverage_csv) — all empty if disabled
    """
    if not MASTER_AUDIT_V3_ENABLED:
        return [], [], ""

    from audit_rules.writer import write_coverage_csv_to_string

    runner = _get_runner()
    pipeline_data = dict(existing_data or {})
    pipeline_data.setdefault("deliverable_pipeline_available", True)

    if export_data:
        findings, coverage_rows = runner.run_from_export(
            export_data,
            base_url,
            existing_data=pipeline_data,
        )
    else:
        findings, coverage_rows = runner.run(
            site_data=site_data or {},
            pages=pages or [],
            links=links or [],
            existing_data=pipeline_data,
            base_url=base_url,
            completeness=completeness,
        )

    coverage_csv = write_coverage_csv_to_string(coverage_rows)
    return findings, coverage_rows, coverage_csv


def build_snapshot_artifacts(
    export_data: dict,
    base_url: str,
    *,
    baseline_path: str | Path | None = None,
    created_at: str | None = None,
) -> tuple[bytes, list, str]:
    """Build the current snapshot and, when provided, its baseline diff."""
    from audit_rules.snapshot import (
        build_snapshot_from_export,
        load_snapshot,
        snapshot_to_gzip_bytes,
    )
    from audit_rules.snapshot_diff import crawl_diff_csv_to_string, diff_snapshots

    current = build_snapshot_from_export(
        export_data,
        base_url,
        created_at=created_at,
    )
    snapshot_bytes = snapshot_to_gzip_bytes(current)
    if baseline_path is None:
        return snapshot_bytes, [], ""

    baseline = load_snapshot(baseline_path)
    changes = diff_snapshots(baseline, current)
    return snapshot_bytes, changes, crawl_diff_csv_to_string(changes)


def augment_zip_with_coverage(zip_files: dict, coverage_csv: str) -> dict:
    """Add coverage.csv to an audit zip file dict (9th file).

    Requirement 9: Existing 8-file zip preserved; only coverage.csv added.

    Args:
        zip_files: Existing dict of {filename: content} from audit export
        coverage_csv: CSV string from run_v3_pipeline()

    Returns:
        Same dict with 'coverage.csv' added (or empty string if not enabled)
    """
    if not MASTER_AUDIT_V3_ENABLED:
        return zip_files

    zip_files["coverage.csv"] = coverage_csv
    return zip_files


def reset_runner_cache():
    """Clear cached runner (for testing)."""
    global _runner_cache
    _runner_cache = None
