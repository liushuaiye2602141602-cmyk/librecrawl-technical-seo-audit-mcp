"""Optional external technology enrichment (contract only, v1 fail-open).

Local detection is the primary source of truth. External enrichment is
additive and never silently overrides local evidence: facts carry
``source_provenance="external_api"`` and the profile keeps its local
detection sources untouched. Any timeout, quota error, missing credential,
or other provider failure is recorded as ``{"status": "unavailable"}`` and
never blocks the audit, DOCX generation, or replay.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EnrichmentFact:
    """One externally sourced observation; provenance preserved."""

    technology_name: str
    category: str
    version: str = "Unknown"
    signal_value: str = ""
    source_provenance: str = "external_api"
    provider: str = ""


class OptionalTechnologyEnrichmentProvider(ABC):
    """Contract for optional Wappalyzer-like / BuiltWith-like providers.

    v1 ships no real external provider; implementers must be fail-open.
    """

    name: str = ""

    @abstractmethod
    def enrich(self, profile: dict[str, Any]) -> list[EnrichmentFact]:
        """Return additive facts or raise; callers convert failures to
        ``unavailable``."""


class NoOpTechnologyEnrichmentProvider(OptionalTechnologyEnrichmentProvider):
    """v1 no-op: enrichment is unavailable, audit never depends on it."""

    name = "noop"

    def enrich(self, profile: dict[str, Any]) -> list[EnrichmentFact]:
        return []


def run_enrichment(
    profile: dict[str, Any],
    providers: list[OptionalTechnologyEnrichmentProvider] | None = None,
) -> dict[str, Any]:
    """Run optional providers against a serialized profile; never raises.

    Records the combined status in ``profile["external_enrichment"]``. Local
    detections and their evidence are never modified by external facts.
    """
    providers = providers or []
    status: dict[str, Any] = {"status": "unavailable", "facts": []}
    for provider in providers:
        try:
            facts = list(provider.enrich(profile))
            normalized = [
                {
                    "technology_name": f.technology_name,
                    "category": f.category,
                    "version": f.version,
                    "signal_value": f.signal_value,
                    "source_provenance": f.source_provenance,
                    "provider": f.provider or provider.name,
                }
                for f in facts
            ]
            status = {
                "provider": provider.name,
                "status": "ok" if normalized else "unavailable",
                "facts": normalized,
            }
        except Exception as exc:  # fail-open by contract
            status = {
                "provider": provider.name,
                "status": "unavailable",
                "facts": [],
                "error": f"{type(exc).__name__}: {exc}",
            }
    if not status.get("provider"):
        status["provider"] = ""
    profile["external_enrichment"] = status
    return status
