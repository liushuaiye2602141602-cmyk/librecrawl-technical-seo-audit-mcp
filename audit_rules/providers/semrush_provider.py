"""Semrush Backlinks API v4 provider for the V3 pipeline."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit

from audit_rules.context import PageContext, SiteContext
from audit_rules.providers.base import DataProvider
from audit_rules.providers.semrush_client import SemrushClient


def _limit(value: object) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 100
    return max(1, min(parsed, 500))


class SemrushDataProvider(DataProvider):
    def __init__(self, api_key: str = "", target: str = "", *,
                 client: Any | None = None, lost_link_limit: int | None = None) -> None:
        self._api_key = api_key or os.getenv("SEMRUSH_API_KEY", "")
        self._target = target or os.getenv("SEMRUSH_TARGET", "")
        self._client = client
        self._lost_link_limit = _limit(
            lost_link_limit if lost_link_limit is not None
            else os.getenv("SEMRUSH_LOST_LINK_LIMIT", "100"))
        self.runtime_available = False

    @property
    def name(self) -> str:
        return "Semrush API"

    @property
    def aliases(self) -> set[str]:
        return {"Semrush API", "Semrush"}

    def is_available(self) -> bool:
        return bool(
            os.getenv("MASTER_AUDIT_V3_ENABLED", "false").lower() == "true"
            and os.getenv("MASTER_AUDIT_SEMRUSH_ENABLED", "true").lower() == "true"
            and self._api_key)

    def missing_rule_ids(self) -> list[int]:
        return [31, 77]

    def enrich_site(self, ctx: SiteContext) -> None:
        pass

    def enrich_page(self, ctx: PageContext) -> None:
        pass

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = SemrushClient(self._api_key)
        return self._client

    def _resolve_target(self, site_ctx: SiteContext) -> str:
        if self._target:
            return self._target
        parsed = urlsplit(site_ctx.base_url)
        return parsed.hostname or ""

    def collect(self, site_ctx: SiteContext, page_contexts: list[PageContext],
                shared_data: dict) -> bool:
        target = self._resolve_target(site_ctx)
        payload = {"target": target, "overview": None, "lost_links": [],
                   "lost_total": 0, "lost_truncated": False, "errors": []}
        shared_data["semrush"] = payload
        if not target:
            payload["errors"].append("target:ValueError")
            self.runtime_available = False
            return False

        client = self._get_client()
        successes = 0
        try:
            payload["overview"] = client.backlinks_overview(target)
            successes += 1
        except Exception as exc:
            payload["errors"].append(f"overview:{type(exc).__name__}")
        try:
            lost = client.lost_backlinks(target, limit=self._lost_link_limit)
            payload["lost_links"] = lost.get("links") or []
            payload["lost_total"] = int(lost.get("total", 0) or 0)
            payload["lost_truncated"] = bool(lost.get("truncated", False))
            successes += 1
        except Exception as exc:
            payload["errors"].append(f"lost_links:{type(exc).__name__}")
        self.runtime_available = successes > 0
        return self.runtime_available
