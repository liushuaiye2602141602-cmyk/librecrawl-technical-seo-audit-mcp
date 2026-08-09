"""A merge-final ZIP cannot be built from a partial or mixed run."""

import pytest


def test_final_zip_refuses_bundle_without_replay_and_manifest(tmp_path):
    from server import _build_current_run_zip

    coverage = tmp_path / "coverage.csv"
    coverage.write_text("audit_id\n1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing required current-run artifacts"):
        _build_current_run_zip(
            {"id": "session-1", "url": "https://example.com/", "pages_done": 315},
            [{"kind": "coverage_csv", "path": str(coverage)}],
        )


def test_offline_315_page_final_bundle_passes_current_run_contract(tmp_path):
    from scripts.validate_v3_artifacts import run_validation
    from tests.phase12.test_replay_315_page_parity import _synthetic_export

    pages, links = _synthetic_export()
    export_data = {
        "site_check": {
            "robots_txt": {
                "found": True, "status": 200, "disallow_count": 0,
                "sitemap_declared": ["https://example.com/sitemap.xml"],
            },
            "sitemap": {"found": True, "url": "https://example.com/sitemap.xml"},
        },
        "pages": pages,
        "links": links,
    }

    result = run_validation(
        tmp_path,
        export_data=export_data,
        pdf_renderer=lambda markdown, output_path, base_url: output_path.write_bytes(
            b"%PDF-1.7\n% offline 315-page fixture\n"
        ),
    )

    assert result["offline_final_bundle_status"] == "OFFLINE_FINAL_BUNDLE_PASS"
    assert result["coverage_rows"] == 80
    assert result["replay_pages"] == 315
    assert result["replay_links"] == 1260
    assert result["zip_valid"] is True
    assert result["stale_artifacts"] == []
