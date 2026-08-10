"""Task M 鈥?customer-domain hardcode scan for the technology package."""

import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

_DOMAINS = ("baolaipackaging", "gelgoogsort", "yashengcrafts")


def test_technology_hardcode_scan_covers_new_package():
    package = PROJECT_ROOT / "audit_rules" / "technology"
    files = sorted(package.rglob("*.py"))
    assert files, "technology package scan found no Python files"
    for path in files:
        text = path.read_text(encoding="utf-8")
        # The FORBIDDEN_DOMAINS guard legitimately names the domains once.
        cleaned = re.sub(r"FORBIDDEN_DOMAINS.*", "", text)
        for domain in _DOMAINS:
            assert domain not in cleaned, (
                f"{path} contains customer domain {domain}")


def test_registry_rejects_customer_domain_signatures():
    from audit_rules.technology.signatures import TechnologySignatureRegistry
    with pytest.raises(ValueError, match="customer-domain"):
        TechnologySignatureRegistry({
            "FakeCMS": {
                "category": "CMS",
                "technology_type": "CMS",
                "signals": [
                    {"type": "asset_path",
                     "pattern": r"https://gelgoogsort.com/wp-content/",
                     "strength": "strong"},
                ],
            },
        })


def test_runtime_technology_files_are_domain_free():
    production_files = [
        "audit_rules/runner.py",
        "runner.py",
        "audit_rules/replay.py",
    ]
    for relative in production_files:
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        for domain in _DOMAINS:
            assert domain not in text.lower(), (
                f"{relative} contains customer domain {domain}")
