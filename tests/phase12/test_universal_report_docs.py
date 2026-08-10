"""Universal report skill + AGENTS invariants."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

_FORBIDDEN = ("baolaipackaging", "gelgoogsort", "yashengcrafts")


def test_skill_doc_exists():
    path = PROJECT_ROOT / "skills" / "universal-seo-report" / "SKILL.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert text.strip()
    assert "80" in text
    assert "Never add Audit #81" in text


def test_agents_universal_invariants_present():
    text = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for invariant in (
        "One universal report contract",
        "Current-run-only",
        "Client-safe and shareable",
        "Actionable remediation",
        "Presentation never changes diagnosis",
    ):
        assert invariant.lower() in text.lower()


def test_docs_contain_no_customer_domains():
    text = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    text += "\n" + (PROJECT_ROOT / "skills" / "universal-seo-report"
                    / "SKILL.md").read_text(encoding="utf-8")
    for domain in _FORBIDDEN:
        assert domain not in text
