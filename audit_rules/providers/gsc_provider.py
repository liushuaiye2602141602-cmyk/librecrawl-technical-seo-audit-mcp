"""Google Search Console data provider for the V3 audit pipeline."""

from __future__ import annotations

from datetime import date, timedelta
import os
from typing import Any

from audit_rules.context import PageContext, SiteContext
from audit_rules.providers.base import DataProvider
from audit_rules.providers.gsc_client import GSCAPIError, GSCClient


DEFAULT_INSPECTION_LIMIT = 20
MAX_INSPECTION_LIMIT = 100
DEFAULT_ANALYTICS_ROWS = 50_000


def _bounded_positive(value: object, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(parsed, maximum) if parsed > 0 else default


class GSCDataProvider(DataProvider):
    """Collect finalized Search Analytics, sitemap, and inspection evidence."""

    def __init__(self, access_token: str = "", site_url: str = "", *,
                 client: Any | None = None, today: date | None = None,
                 inspection_limit: int | None = None,
                 analytics_max_rows: int | None = None) -> None:
        self._access_token = access_token or os.getenv("GSC_ACCESS_TOKEN", "")
        self._site_url = site_url or os.getenv("GSC_SITE_URL", "")
        self._today = today or date.today()
        self._inspection_limit = _bounded_positive(
            inspection_limit if inspection_limit is not None else os.getenv("GSC_INSPECTION_LIMIT", "20"),
            DEFAULT_INSPECTION_LIMIT, MAX_INSPECTION_LIMIT)
        self._analytics_max_rows = _bounded_positive(
            analytics_max_rows if analytics_max_rows is not None else os.getenv("GSC_ANALYTICS_MAX_ROWS", "50000"),
            DEFAULT_ANALYTICS_ROWS, DEFAULT_ANALYTICS_ROWS)
        self._client = client
        self.runtime_available = False

    @property
    def name(self) -> str:
        return "GSC API"

    @property
    def aliases(self) -> set[str]:
        return {"GSC API", "GSC"}

    def is_available(self) -> bool:
        v3_enabled = os.getenv("MASTER_AUDIT_V3_ENABLED", "false").lower() == "true"
        gsc_enabled = os.getenv("MASTER_AUDIT_GSC_ENABLED", "true").lower() == "true"
        return bool(v3_enabled and gsc_enabled and self._access_token and self._site_url)

    def missing_rule_ids(self) -> list[int]:
        return [44, 52, 75, 76]

    def enrich_site(self, ctx: SiteContext) -> None:
        pass

    def enrich_page(self, ctx: PageContext) -> None:
        pass

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = GSCClient(self._access_token, self._site_url)
        return self._client

    def collect(self, site_ctx: SiteContext, page_contexts: list[PageContext],
                shared_data: dict) -> bool:
        """Populate shared and per-page GSC evidence; return runtime availability."""
        client = self._get_client()
        end = self._today - timedelta(days=3)
        current_start = end - timedelta(days=27)
        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=27)
        dimensions = ["page", "query", "country", "device"]
        errors: list[str] = []
        successes: set[str] = set()
        windows: dict[str, list[dict]] = {"current_rows": [], "previous_rows": []}

        try:
            for key, start, finish in (
                ("current_rows", current_start, end),
                ("previous_rows", previous_start, previous_end),
            ):
                raw = client.query_search_analytics(
                    start.isoformat(), finish.isoformat(), dimensions=dimensions,
                    max_rows=self._analytics_max_rows)
                windows[key] = self._normalize_rows(raw.get("rows") or [], dimensions)
            successes.add("search_analytics")
        except Exception as exc:
            errors.append(f"search_analytics:{type(exc).__name__}")

        sitemaps: list[dict] = []
        try:
            entries = client.list_sitemaps().get("sitemap") or []
            if not isinstance(entries, list):
                raise GSCAPIError("GSC Sitemaps returned invalid entries")
            sitemaps = [item for item in entries if isinstance(item, dict)]
            successes.add("sitemaps")
        except Exception as exc:
            errors.append(f"sitemaps:{type(exc).__name__}")

        eligible = sorted(
            (page for page in page_contexts if page.status_code == 200 and page.url),
            key=lambda page: page.url)[:self._inspection_limit]
        inspections: dict[str, dict] = {}
        inspection_failed = False
        for page in eligible:
            try:
                result = client.inspect_url(page.url).get("inspectionResult") or {}
                index_status = result.get("indexStatusResult") or {}
                if not isinstance(index_status, dict):
                    raise GSCAPIError("GSC URL Inspection returned invalid status")
                inspections[page.url] = index_status
            except Exception:
                inspection_failed = True
        if inspections:
            successes.add("url_inspection")
        if inspection_failed:
            errors.append("url_inspection:GSCAPIError")

        payload = {
            **windows, "sitemaps": sitemaps, "inspections": inspections,
            "inspection_attempted": len(eligible),
            "inspection_succeeded": len(inspections), "errors": errors,
            "current_start": current_start.isoformat(), "current_end": end.isoformat(),
            "previous_start": previous_start.isoformat(), "previous_end": previous_end.isoformat(),
        }
        shared_data["gsc"] = payload
        by_url: dict[str, list[dict]] = {}
        for row in windows["current_rows"]:
            if row.get("page"):
                by_url.setdefault(row["page"], []).append(row)
        for page in page_contexts:
            page.gsc_data = {"current_rows": by_url.get(page.url, []),
                             "inspection": inspections.get(page.url)}

        self.runtime_available = bool(successes)
        return self.runtime_available

    @staticmethod
    def _normalize_rows(rows: list[dict], dimensions: list[str]) -> list[dict]:
        normalized: list[dict] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            keys = row.get("keys") or []
            item = {dimension: keys[index] if index < len(keys) else ""
                    for index, dimension in enumerate(dimensions)}
            for metric in ("clicks", "impressions", "ctr", "position"):
                item[metric] = row.get(metric, 0)
            normalized.append(item)
        return normalized
