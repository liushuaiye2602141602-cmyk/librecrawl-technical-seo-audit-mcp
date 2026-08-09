"""Provider for privacy-safe raw-vs-rendered page summary snapshots."""

from __future__ import annotations

import json
import os
from pathlib import Path

from audit_rules.context import PageContext, SiteContext
from audit_rules.providers.base import DataProvider
from audit_rules.providers.snapshot_evidence import (
    EvidenceValidationError, load_snapshot, non_negative_int, required_bool,
    same_host_url, validate_snapshot_identity,
)


class RenderSnapshotProvider(DataProvider):
    def __init__(self, path: str = "", *, max_age_hours: int | None = None) -> None:
        self._path = Path(path or os.getenv("JS_RENDER_AUDIT_PATH", ""))
        try:
            age = int(max_age_hours if max_age_hours is not None
                      else os.getenv("JS_RENDER_MAX_AGE_HOURS", "168"))
        except (TypeError, ValueError):
            age = 168
        self._max_age_hours = max(1, min(age, 24 * 30))
        self.runtime_available = False

    @property
    def name(self) -> str:
        return "Rendered DOM Snapshot"

    def is_available(self) -> bool:
        return bool(
            os.getenv("MASTER_AUDIT_V3_ENABLED", "false").lower() == "true"
            and os.getenv("MASTER_AUDIT_RENDER_ENABLED", "false").lower() == "true"
            and self._path.is_file())

    def missing_rule_ids(self) -> list[int]:
        return [46, 48]

    def enrich_site(self, ctx: SiteContext) -> None:
        pass

    def enrich_page(self, ctx: PageContext) -> None:
        pass

    def collect(self, site_ctx: SiteContext, page_contexts: list[PageContext],
                shared_data: dict) -> bool:
        try:
            raw = load_snapshot(self._path)
            host, collected = validate_snapshot_identity(
                raw, schema="render-audit-v1", audited_url=site_ctx.base_url,
                max_age_hours=self._max_age_hours)
            pages = raw.get("pages")
            if not isinstance(pages, list) or not 1 <= len(pages) <= 500:
                raise EvidenceValidationError("invalid page summary count")
            normalized = []
            for item in pages:
                if not isinstance(item, dict):
                    raise EvidenceValidationError("invalid page summary")
                normalized.append({
                    "url": same_host_url(item.get("url"), host),
                    "raw_text_chars": non_negative_int(item.get("raw_text_chars"), "raw_text_chars"),
                    "rendered_text_chars": non_negative_int(item.get("rendered_text_chars"), "rendered_text_chars"),
                    "raw_internal_links": non_negative_int(item.get("raw_internal_links"), "raw_internal_links"),
                    "rendered_internal_links": non_negative_int(item.get("rendered_internal_links"), "rendered_internal_links"),
                    "initial_items": non_negative_int(item.get("initial_items"), "initial_items"),
                    "after_scroll_items": non_negative_int(item.get("after_scroll_items"), "after_scroll_items"),
                    "load_more_requires_interaction": required_bool(item.get("load_more_requires_interaction"), "load_more_requires_interaction"),
                    "crawlable_pagination_fallback": required_bool(item.get("crawlable_pagination_fallback"), "crawlable_pagination_fallback"),
                    "lazy_images_without_fallback": non_negative_int(item.get("lazy_images_without_fallback"), "lazy_images_without_fallback"),
                })
            payload = {"schema_version": "render-audit-v1", "collected_at": collected,
                       "site_host": host, "pages": normalized, "errors": []}
        except (OSError, UnicodeError, json.JSONDecodeError, EvidenceValidationError) as exc:
            shared_data["render_snapshot"] = {"errors": [f"snapshot:{type(exc).__name__}"]}
            self.runtime_available = False
            return False
        shared_data["render_snapshot"] = payload
        self.runtime_available = True
        return True
