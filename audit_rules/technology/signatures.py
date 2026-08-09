"""Declarative TechnologySignatureRegistry.

Signatures match technology characteristics only — never customer domains.
The registry is the single source of signal definitions used by the local
detector; no scattered string checks live in detector code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterator


VALID_STRENGTHS = frozenset({"strong", "medium", "weak"})
VALID_SIGNAL_TYPES = frozenset({
    "meta_generator", "script_src", "stylesheet_href", "asset_path",
    "url_pattern", "response_header", "analytics_fingerprint",
    "json_ld_type", "robots_meta", "cookie_name",
})
# Customer domains that must never appear in production signatures.
FORBIDDEN_DOMAINS = ("baolaipackaging", "gelgoogsort", "yashengcrafts")


@dataclass(frozen=True)
class TechnologySignature:
    technology: str
    category: str
    technology_type: str
    signals: list[dict]
    negative_signals: list[dict] = field(default_factory=list)
    version_extractor: dict | None = None
    confidence_contribution: float | None = None
    applicability_requirement: str | None = None
    notes: str = ""


class TechnologySignatureRegistry:
    """Validated, declarative signature registry."""

    def __init__(self, data: dict[str, dict]):
        self._signatures = [
            self._parse(name, spec) for name, spec in data.items()
        ]
        self._validate_no_domain_patterns()

    @staticmethod
    def _parse(name: str, spec: dict) -> TechnologySignature:
        if not isinstance(spec, dict):
            raise ValueError(f"signature {name} must be a dict")
        signals = spec.get("signals")
        if not isinstance(signals, list) or not signals:
            raise ValueError(f"signature {name} requires non-empty signals")
        for signal in signals:
            TechnologySignatureRegistry._validate_signal(name, signal)
        negative = spec.get("negative_signals") or []
        for signal in negative:
            TechnologySignatureRegistry._validate_signal(name, signal,
                                                         negative=True)
        version_extractor = spec.get("version_extractor")
        if version_extractor is not None:
            if not isinstance(version_extractor, dict):
                raise ValueError(f"signature {name} version_extractor invalid")
            pattern = version_extractor.get("pattern")
            if not isinstance(pattern, str) or "(" not in pattern:
                raise ValueError(
                    f"signature {name} version_extractor needs a capture group")
        return TechnologySignature(
            technology=str(name),
            category=str(spec.get("category") or ""),
            technology_type=str(spec.get("technology_type") or ""),
            signals=signals,
            negative_signals=negative,
            version_extractor=version_extractor,
            confidence_contribution=spec.get("confidence_contribution"),
            applicability_requirement=spec.get("applicability_requirement"),
            notes=str(spec.get("notes") or ""),
        )

    @staticmethod
    def _validate_signal(technology: str, signal: dict, *,
                         negative: bool = False) -> None:
        if not isinstance(signal, dict):
            raise ValueError(f"signature {technology} has a non-dict signal")
        signal_type = signal.get("type")
        pattern = signal.get("pattern")
        strength = signal.get("strength")
        if signal_type not in VALID_SIGNAL_TYPES:
            raise ValueError(
                f"signature {technology} invalid signal type {signal_type!r}")
        if not isinstance(pattern, str) or not pattern:
            raise ValueError(
                f"signature {technology} signal pattern must be non-empty")
        if not negative and strength not in VALID_STRENGTHS:
            raise ValueError(
                f"signature {technology} invalid strength {strength!r}")

    def _validate_no_domain_patterns(self) -> None:
        for signature in self._signatures:
            for signal in signature.signals + signature.negative_signals:
                pattern = str(signal.get("pattern") or "")
                lower = pattern.lower()
                if any(domain in lower for domain in FORBIDDEN_DOMAINS):
                    raise ValueError(
                        f"signature {signature.technology} contains a "
                        f"customer-domain pattern: {pattern!r}")
            extractor = signature.version_extractor
            if extractor:
                pattern = str(extractor.get("pattern") or "")
                if any(domain in pattern.lower()
                       for domain in FORBIDDEN_DOMAINS):
                    raise ValueError(
                        f"signature {signature.technology} version extractor "
                        f"contains a customer-domain pattern")

    def iter_signatures(self) -> Iterator[TechnologySignature]:
        yield from self._signatures

    def by_technology(self, technology: str) -> TechnologySignature:
        for signature in self._signatures:
            if signature.technology.lower() == technology.lower():
                return signature
        raise KeyError(f"no signature for {technology}")

    def categories(self) -> list[str]:
        return sorted({s.category for s in self._signatures})


def load_default_registry() -> TechnologySignatureRegistry:
    from audit_rules.technology.signature_data import SIGNATURES
    return TechnologySignatureRegistry(SIGNATURES)
