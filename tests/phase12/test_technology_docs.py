"""Task K 鈥?AGENTS invariants + technology-intelligence skill docs."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

_FORBIDDEN_DOMAINS = (
    "baolaipackaging.com", "gelgoogsort.com", "yashengcrafts.com",
)


def _read(relative: str) -> str:
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def test_agents_invariants_present():
    text = _read("AGENTS.md")
    for invariant in (
        "exactly 80",
        "Technology Detection != Finding",
        "Technology Detection != Vulnerability",
        "Evidence-first",
        "No domain-specific production logic",
        "Local-first",
        "External optional",
        "Missing data never becomes PASS",
        "Client-safe reporting",
        "No Audit #81",
    ):
        assert invariant.lower() in text.lower()


def test_skill_doc_exists_and_states_no_rule81():
    path = PROJECT_ROOT / "skills" / "technology-intelligence" / "SKILL.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert text.strip()
    assert "80" in text
    assert "#81" not in text


def test_docs_contain_no_customer_domains():
    text = _read("AGENTS.md") + "\n" + _read(
        "skills/technology-intelligence/SKILL.md")
    for domain in _FORBIDDEN_DOMAINS:
        assert domain not in text
