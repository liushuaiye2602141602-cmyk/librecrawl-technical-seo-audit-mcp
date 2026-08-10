"""Universal demo report package (offline fixture, no live calls)."""

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

docx = pytest.importorskip("docx")


def test_demo_package_contains_universal_docx(monkeypatch):
    monkeypatch.setenv("DEMO_DATE", "2026-08-11-demo")
    import scripts.generate_universal_demo_report as demo
    demo.main()
    out = PROJECT_ROOT / "reports" / "universal-demo-2026-08-11-demo"
    docx_path = out / "01_Master_SEO_Diagnostic_Report.docx"
    assert docx_path.exists()
    from docx import Document
    doc = Document(str(docx_path))
    audits = [p for p in doc.paragraphs
              if p.style.name == "Heading 2" and p.text.startswith("AUDIT #")]
    assert len(audits) == 80


def test_demo_package_contains_09_technology_profile(monkeypatch):
    monkeypatch.setenv("DEMO_DATE", "2026-08-11-demo")
    import scripts.generate_universal_demo_report as demo
    demo.main()
    out = PROJECT_ROOT / "reports" / "universal-demo-2026-08-11-demo"
    profile_path = out / "09_Technology_Profile.json"
    assert profile_path.exists()
    import json
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    assert profile["detector_version"]
    assert any(d["technology_name"] == "WooCommerce"
               and d["status"] == "UNKNOWN" for d in profile["detections"])


def test_demo_zip_exists_and_sha(monkeypatch):
    monkeypatch.setenv("DEMO_DATE", "2026-08-11-demo")
    import scripts.generate_universal_demo_report as demo
    demo.main()
    zip_path = PROJECT_ROOT / "reports" / "universal-demo-2026-08-11-demo.zip"
    assert zip_path.exists()
    assert zip_path.stat().st_size > 0
