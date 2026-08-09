"""Production-like offline validation of the complete applicable V3 bundle."""

from pathlib import Path


def test_validation_script_builds_real_applicable_artifacts_and_zip(tmp_path):
    from scripts.validate_v3_artifacts import run_validation

    def deterministic_pdf(markdown, output_path, base_url):
        assert "# Master SEO Audit Report" in markdown
        assert base_url == "https://example.com"
        output_path.write_bytes(b"%PDF-1.7\n% unit-test renderer\n")

    result = run_validation(tmp_path, pdf_renderer=deterministic_pdf)

    assert result["coverage_rows"] == 80
    assert result["zip_valid"] is True
    assert result["pdf_valid"] is True
    assert set(result["artifact_kinds"]) == {
        "audit_score_json", "audit_snapshot", "coverage_csv",
        "manual_review_md", "master_report_md", "master_report_pdf",
        "task_csv",
    }
    assert result["provider_artifacts"] == []


def test_compose_allows_mcp_to_cleanup_the_shared_upstream_database():
    """auto_cleanup requires write access to the shared LibreCrawl database."""
    compose = (Path(__file__).resolve().parents[2] / "docker-compose.yml").read_text(
        encoding="utf-8"
    )

    assert "librecrawl-data:/librecrawl-data:ro" not in compose
    assert "librecrawl-data:/librecrawl-data" in compose
