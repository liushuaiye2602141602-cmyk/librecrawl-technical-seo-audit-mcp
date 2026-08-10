"""Task C — TechnologySignatureRegistry."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_signature_registry_loads_declarative_signatures():
    from audit_rules.technology.signatures import load_default_registry
    registry = load_default_registry()
    signatures = list(registry.iter_signatures())
    assert len(signatures) >= 15
    assert any(s.technology == "WordPress" for s in signatures)
    assert any(s.technology == "Cloudflare" for s in signatures)


def test_signature_patterns_are_technology_scoped_not_domain_scoped():
    from audit_rules.technology.signatures import TechnologySignatureRegistry
    bad = {
        "WordPress": {
            "category": "CMS", "technology_type": "CMS",
            "signals": [
                {"type": "asset_path", "pattern": r"https://gelgoogsort.com/",
                 "strength": "strong"},
            ],
        },
    }
    with pytest.raises(ValueError):
        TechnologySignatureRegistry(bad)


def test_signature_strength_contributes_to_confidence():
    from audit_rules.technology.signatures import load_default_registry
    registry = load_default_registry()
    wordpress = registry.by_technology("WordPress")
    strengths = {s["strength"] for s in wordpress.signals}
    assert strengths <= {"strong", "medium", "weak"}
    assert "strong" in strengths


def test_version_extractor_only_with_reliable_evidence():
    from audit_rules.technology.signatures import load_default_registry
    registry = load_default_registry()
    wordpress = registry.by_technology("WordPress")
    extractor = wordpress.version_extractor
    assert extractor is not None
    assert "(" in extractor["pattern"]  # capture group for the version


def test_negative_signals_are_supported():
    from audit_rules.technology.signatures import load_default_registry
    registry = load_default_registry()
    wordpress = registry.by_technology("WordPress")
    assert isinstance(wordpress.negative_signals, list)


def test_conflicting_signals_are_not_silently_overwritten():
    from audit_rules.technology.signatures import load_default_registry
    registry = load_default_registry()
    for signature in registry.iter_signatures():
        seen = {}
        for signal in signature.signals:
            key = (signal["type"], signal["pattern"])
            assert key not in seen, (
                f"duplicate signal in {signature.technology}")
            seen[key] = True


def test_signature_fields_are_valid():
    from audit_rules.technology.signatures import load_default_registry
    registry = load_default_registry()
    for signature in registry.iter_signatures():
        assert signature.technology
        assert signature.category
        assert signature.technology_type
        assert signature.signals
