"""Enhanced V3 Markdown/PDF reporting contracts."""

from tests.phase12.test_scoring_and_artifacts import _coverage, _finding


def test_master_report_contains_decision_sections_and_truthful_statuses():
    from audit_rules.categories import ExecutionStatus
    from audit_rules.reporting import build_master_report

    report = build_master_report(
        "https://example.com",
        [_finding(1, severity="Error")],
        [_coverage(1), _coverage(2, execution=ExecutionStatus.NOT_CHECKED)],
    )

    for heading in (
        "Executive Summary", "Priority Plan (P0 / P1 / P2 / P3)",
        "80 Rule Coverage", "Top Business Risks", "Technical SEO",
        "Indexing / Crawling", "Architecture / Internal Links",
        "Content / Metadata", "International SEO", "Structured Data",
        "Performance / CWV", "Search Performance", "Backlinks",
        "WordPress", "Security", "Manual Review", "Missing External Data",
        "Before / After Regression", "Remediation Plan",
        "Acceptance Criteria", "Audit Score / Coverage / Confidence",
    ):
        assert f"## {heading}" in report
    assert "NOT_CHECKED" in report
    assert "FAIL" in report


def test_runner_writes_and_registers_enhanced_markdown_and_pdf(tmp_path, monkeypatch):
    import runner
    import pdf_report

    registered = []
    monkeypatch.setattr(
        runner.state, "add_artifact",
        lambda sid, kind, path: registered.append((kind, path)))

    def fake_pdf(markdown_text, output_path, base_url):
        output_path.write_bytes(b"%PDF-test")
        return {"pages": 1, "size_bytes": 9}

    monkeypatch.setattr(pdf_report, "render_pdf", fake_pdf)
    paths = runner._write_master_report_artifacts(
        "session-1", "https://example.com", [_finding(1)], [_coverage(1)],
        "example.com", "20260809-1200", tmp_path)

    assert set(paths) == {"master_report_md", "master_report_pdf"}
    assert paths["master_report_md"].read_text(encoding="utf-8").startswith(
        "# Master SEO Audit Report")
    assert [kind for kind, _ in registered] == [
        "master_report_md", "master_report_pdf"]
