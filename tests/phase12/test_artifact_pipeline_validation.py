"""Production-like offline validation of the complete applicable V3 bundle."""

from pathlib import Path
import sys
from types import SimpleNamespace


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
        "audit_replay", "audit_score_json", "audit_snapshot", "coverage_csv",
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


def test_pdf_container_installs_a_cjk_font_for_chinese_acceptance_criteria():
    dockerfile = (Path(__file__).resolve().parents[2] / "Dockerfile").read_text(
        encoding="utf-8"
    )

    assert "fonts-noto-cjk" in dockerfile


def test_pdf_renderer_reports_pages_without_an_optional_pdf_reader(monkeypatch, tmp_path):
    import pdf_report

    class FakeDocument:
        pages = [object(), object()]

        def write_pdf(self, target):
            Path(target).write_bytes(b"%PDF-1.7\n")

    class FakeHTML:
        def __init__(self, **kwargs):
            pass

        def render(self):
            return FakeDocument()

    monkeypatch.setitem(sys.modules, "weasyprint", SimpleNamespace(HTML=FakeHTML))

    result = pdf_report.render_pdf(
        "# Production acceptance", tmp_path / "acceptance.pdf", "https://example.com"
    )

    assert result["pages"] == 2
