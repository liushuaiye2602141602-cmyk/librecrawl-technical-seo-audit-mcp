"""Provider for vendor-neutral availability monitoring aggregates."""

from __future__ import annotations

import json
import os
from pathlib import Path

from audit_rules.context import PageContext, SiteContext
from audit_rules.providers.base import DataProvider
from audit_rules.providers.snapshot_evidence import (
    EvidenceValidationError, load_snapshot, non_negative_int, same_host_url,
    validate_snapshot_identity,
)


class AvailabilitySnapshotProvider(DataProvider):
    def __init__(self, path: str = "", *, max_age_hours: int | None = None) -> None:
        self._path = Path(path or os.getenv("AVAILABILITY_AUDIT_PATH", ""))
        try:
            age = int(max_age_hours if max_age_hours is not None
                      else os.getenv("AVAILABILITY_MAX_AGE_HOURS", "24"))
        except (TypeError, ValueError):
            age = 24
        self._max_age_hours = max(1, min(age, 24 * 30))
        self.runtime_available = False

    @property
    def name(self) -> str:
        return "Availability Monitor"

    def is_available(self) -> bool:
        return bool(
            os.getenv("MASTER_AUDIT_V3_ENABLED", "false").lower() == "true"
            and os.getenv("MASTER_AUDIT_AVAILABILITY_ENABLED", "false").lower() == "true"
            and self._path.is_file())

    def missing_rule_ids(self) -> list[int]:
        return [80]

    def enrich_site(self, ctx: SiteContext) -> None:
        pass

    def enrich_page(self, ctx: PageContext) -> None:
        pass

    def collect(self, site_ctx: SiteContext, page_contexts: list[PageContext],
                shared_data: dict) -> bool:
        try:
            raw = load_snapshot(self._path)
            host, collected = validate_snapshot_identity(
                raw, schema="availability-monitor-v1", audited_url=site_ctx.base_url,
                max_age_hours=self._max_age_hours)
            window = non_negative_int(raw.get("window_hours"), "window_hours")
            endpoints = raw.get("endpoints")
            if window < 1 or not isinstance(endpoints, list) or not 1 <= len(endpoints) <= 500:
                raise EvidenceValidationError("invalid monitoring summary")
            normalized = []
            for item in endpoints:
                if not isinstance(item, dict):
                    raise EvidenceValidationError("invalid endpoint summary")
                total = non_negative_int(item.get("total_checks"), "total_checks")
                failed = non_negative_int(item.get("failed_checks"), "failed_checks")
                five_xx = non_negative_int(item.get("five_xx_checks"), "five_xx_checks")
                locations = non_negative_int(item.get("locations"), "locations")
                try:
                    availability = float(item.get("availability_pct"))
                    p95 = float(item.get("p95_ms"))
                except (TypeError, ValueError) as exc:
                    raise EvidenceValidationError("invalid availability metrics") from exc
                if total < 1 or failed > total or five_xx > failed or not 0 <= availability <= 100 or p95 < 0 or locations < 1:
                    raise EvidenceValidationError("inconsistent availability metrics")
                normalized.append({
                    "url": same_host_url(item.get("url"), host),
                    "total_checks": total, "failed_checks": failed,
                    "five_xx_checks": five_xx, "availability_pct": availability,
                    "p95_ms": p95, "locations": locations,
                })
            payload = {"schema_version": "availability-monitor-v1",
                       "collected_at": collected, "site_host": host,
                       "window_hours": window, "endpoints": normalized, "errors": []}
        except (OSError, UnicodeError, json.JSONDecodeError, EvidenceValidationError) as exc:
            shared_data["availability_snapshot"] = {"errors": [f"snapshot:{type(exc).__name__}"]}
            self.runtime_available = False
            return False
        shared_data["availability_snapshot"] = payload
        self.runtime_available = True
        return True
