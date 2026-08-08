"""Task 8: Feature flag + integration tests."""

import sys
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def reset_flag_and_cache():
    """Ensure feature flag is OFF and cache is cleared before/after each test."""
    from audit_rules import integration
    integration.disable_v3()
    integration.reset_runner_cache()
    yield
    integration.disable_v3()
    integration.reset_runner_cache()


@pytest.fixture
def sample_export():
    return {
        "site_check": {
            "robots_txt": {"found": True, "disallow_count": 2, "sitemap_url": "https://x.com/sitemap.xml"},
            "sitemap": {"found": True, "url": "https://x.com/sitemap.xml", "url_count": 5},
            "https_redirect": {"redirects": True},
            "www_redirect": {"redirects": False},
        },
        "pages": [
            {
                "url": "https://x.com",
                "status_code": 200,
                "title": "Home",
                "meta_description": "A perfectly good site for testing integration layer functionality",
                "h1": "Welcome",
                "canonical_url": "https://x.com",
                "robots": "index, follow",
                "depth": 0,
                "word_count": 500,
                "internal_links_count": 5,
                "external_links_count": 1,
                "linked_from": [],
                "json_ld": [{"@type": "Organization"}],
                "hreflang": [{"lang": "en", "url": "https://x.com"}, {"lang": "x-default", "url": "https://x.com"}],
            },
        ],
        "links": [],
    }


# ============================================================
# Test: Feature flag behavior
# ============================================================

class TestFeatureFlag:
    """Verify MASTER_AUDIT_V3_ENABLED controls pipeline activation."""

    def test_flag_defaults_to_false(self):
        from audit_rules.integration import is_v3_enabled
        assert is_v3_enabled() is False

    def test_enable_v3_activates_flag(self):
        from audit_rules.integration import enable_v3, is_v3_enabled
        enable_v3()
        assert is_v3_enabled() is True

    def test_disable_v3_deactivates_flag(self):
        from audit_rules.integration import enable_v3, disable_v3, is_v3_enabled
        enable_v3()
        disable_v3()
        assert is_v3_enabled() is False

    def test_run_v3_disabled_returns_empty(self, sample_export):
        """When disabled, run_v3_pipeline returns empty results — no side effects."""
        from audit_rules.integration import run_v3_pipeline, is_v3_enabled
        assert is_v3_enabled() is False

        findings, coverage, csv_str = run_v3_pipeline(export_data=sample_export)
        assert findings == []
        assert coverage == []
        assert csv_str == ""

    def test_run_v3_enabled_returns_results(self, sample_export):
        """When enabled, run_v3_pipeline returns findings + coverage + CSV."""
        from audit_rules.integration import enable_v3, run_v3_pipeline
        enable_v3()

        findings, coverage, csv_str = run_v3_pipeline(export_data=sample_export)
        assert isinstance(findings, list)
        assert len(coverage) == 80
        assert "audit_id" in csv_str
        assert len(csv_str) > 0

    def test_run_v3_disabled_no_side_effects(self, sample_export):
        """Disabled pipeline must not create files or modify state."""
        from audit_rules.integration import run_v3_pipeline
        import os
        before_files = set(os.listdir("."))
        run_v3_pipeline(export_data=sample_export)
        after_files = set(os.listdir("."))
        assert before_files == after_files


class TestZipAugmentation:
    """Verify coverage.csv is correctly added to zip dict."""

    def test_disabled_does_not_add_coverage(self):
        from audit_rules.integration import augment_zip_with_coverage, is_v3_enabled
        assert is_v3_enabled() is False

        zip_files = {
            "SUMMARY.txt": "content",
            "report.md": "markdown",
        }
        result = augment_zip_with_coverage(zip_files, "fake,csv,data")
        assert "coverage.csv" not in result
        assert len(result) == 2

    def test_enabled_adds_ninth_file(self):
        from audit_rules.integration import enable_v3, augment_zip_with_coverage
        enable_v3()

        zip_files = {
            "SUMMARY.txt": "content",
            "report.pdf": "pdf",
            "report.md": "md",
            "per-page.csv": "data",
            "sitemap-recon.csv": "data",
            "external-links.csv": "data",
            "content-audit.csv": "data",
            "extended-checks.csv": "data",
        }
        result = augment_zip_with_coverage(zip_files, "col1,col2\nval1,val2")
        assert "coverage.csv" in result
        assert len(result) == 9
        assert result["coverage.csv"] == "col1,col2\nval1,val2"


class TestEndToEndIntegration:
    """End-to-end: enabled → run → get CSV → 80 rows."""

    def test_full_pipeline_80_rows(self, sample_export):
        from audit_rules.integration import enable_v3, run_v3_pipeline
        enable_v3()

        findings, coverage, csv_str = run_v3_pipeline(export_data=sample_export)
        assert len(coverage) == 80
        assert len(findings) >= 0

        # Parse CSV back
        import csv, io
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 80
        ids = [int(r["audit_id"]) for r in rows]
        assert set(ids) == set(range(1, 81))

    def test_each_audit_uses_fresh_provider_instances(self, sample_export):
        """Audit-scoped clients/configuration must not leak across sites or runs."""
        from audit_rules.integration import enable_v3, run_v3_pipeline, _get_runner
        enable_v3()

        run_v3_pipeline(export_data=sample_export)
        runner1 = _get_runner()
        run_v3_pipeline(export_data=sample_export)
        runner2 = _get_runner()
        assert runner1 is not runner2
        assert runner1.providers["GSC API"] is not runner2.providers["GSC API"]

    def test_enable_disable_toggle(self, sample_export):
        from audit_rules.integration import enable_v3, disable_v3, run_v3_pipeline

        # First call with enabled
        enable_v3()
        f1, c1, s1 = run_v3_pipeline(export_data=sample_export)
        assert len(c1) == 80
        assert s1 != ""

        # Second call with disabled
        disable_v3()
        f2, c2, s2 = run_v3_pipeline(export_data=sample_export)
        assert f2 == []
        assert c2 == []
        assert s2 == ""

    def test_standalone_params_path(self, sample_export):
        """Pipeline via site_data + pages + links instead of export_data."""
        from audit_rules.integration import enable_v3, run_v3_pipeline
        enable_v3()

        findings, coverage, csv_str = run_v3_pipeline(
            site_data=sample_export["site_check"],
            pages=sample_export["pages"],
            links=sample_export.get("links", []),
            base_url="https://x.com",
        )
        assert len(coverage) == 80
        assert "audit_id" in csv_str

    def test_export_path_forwards_existing_data_to_rule_runner(
        self, sample_export, monkeypatch
    ):
        """Snapshot baselines must reach Rule 74 on the export shortcut."""
        from audit_rules import integration

        class CapturingRunner:
            def __init__(self):
                self.existing_data = None

            def run_from_export(self, export_data, base_url, existing_data=None):
                self.existing_data = existing_data
                return [], []

        fake_runner = CapturingRunner()
        monkeypatch.setattr(integration, "_runner_cache", fake_runner)
        integration.enable_v3()

        integration.run_v3_pipeline(
            export_data=sample_export,
            base_url="https://x.com",
            existing_data={"snapshot_baseline_available": True},
        )

        assert fake_runner.existing_data == {
            "snapshot_baseline_available": True,
            "deliverable_pipeline_available": True,
        }
