"""Google Analytics 4 provider for the V3 pipeline."""

from __future__ import annotations

from datetime import date, timedelta
import os
from typing import Any

from audit_rules.context import PageContext, SiteContext
from audit_rules.providers.base import DataProvider
from audit_rules.providers.ga4_client import GA4Client


class GA4DataProvider(DataProvider):
    def __init__(self, access_token: str = "", property_id: str = "", *,
                 client: Any | None = None, today: date | None = None) -> None:
        self._access_token = access_token or os.getenv("GA4_ACCESS_TOKEN", "")
        self._property_id = property_id or os.getenv("GA4_PROPERTY_ID", "")
        self._client = client
        self._today = today or date.today()
        self.runtime_available = False

    @property
    def name(self) -> str:
        return "GA4 API"

    @property
    def aliases(self) -> set[str]:
        return {"GA4 API", "GA4"}

    def is_available(self) -> bool:
        return bool(
            os.getenv("MASTER_AUDIT_V3_ENABLED", "false").lower() == "true"
            and os.getenv("MASTER_AUDIT_GA4_ENABLED", "true").lower() == "true"
            and self._access_token and self._property_id)

    def missing_rule_ids(self) -> list[int]:
        return [34, 35]

    def enrich_site(self, ctx: SiteContext) -> None:
        pass

    def enrich_page(self, ctx: PageContext) -> None:
        pass

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = GA4Client(self._access_token, self._property_id)
        return self._client

    @staticmethod
    def _rows(report: dict, dimensions: list[str], metrics: list[str]) -> list[dict]:
        result: list[dict] = []
        for row in report.get("rows") or []:
            dimension_values = row.get("dimensionValues") or []
            metric_values = row.get("metricValues") or []
            item = {name: (dimension_values[index].get("value", "")
                           if index < len(dimension_values) else "")
                    for index, name in enumerate(dimensions)}
            for index, name in enumerate(metrics):
                raw = (metric_values[index].get("value", "0")
                       if index < len(metric_values) else "0")
                try:
                    numeric = float(raw)
                    item[name] = int(numeric) if numeric.is_integer() else numeric
                except (TypeError, ValueError):
                    item[name] = 0
            result.append(item)
        return result

    def collect(self, site_ctx: SiteContext, page_contexts: list[PageContext],
                shared_data: dict) -> bool:
        client = self._get_client()
        end = self._today - timedelta(days=4)
        start = end - timedelta(days=27)
        payload = {"property": None, "key_events": [], "daily_activity": [],
                   "event_counts": {}, "start_date": start.isoformat(),
                   "end_date": end.isoformat(), "errors": []}
        successes = 0
        try:
            payload["property"] = client.get_property()
            successes += 1
        except Exception as exc:
            payload["errors"].append(f"property:{type(exc).__name__}")
        try:
            payload["key_events"] = client.list_key_events()
            successes += 1
        except Exception as exc:
            payload["errors"].append(f"key_events:{type(exc).__name__}")
        try:
            report = client.run_report(
                start.isoformat(), end.isoformat(), dimensions=["date"],
                metrics=["sessions", "totalUsers"])
            payload["daily_activity"] = self._rows(
                report, ["date"], ["sessions", "totalUsers"])
            successes += 1
        except Exception as exc:
            payload["errors"].append(f"daily_activity:{type(exc).__name__}")
        try:
            report = client.run_report(
                start.isoformat(), end.isoformat(), dimensions=["eventName"],
                metrics=["eventCount"])
            event_rows = self._rows(report, ["eventName"], ["eventCount"])
            payload["event_counts"] = {
                row["eventName"]: int(row["eventCount"])
                for row in event_rows if row.get("eventName")}
            successes += 1
        except Exception as exc:
            payload["errors"].append(f"event_counts:{type(exc).__name__}")
        shared_data["ga4"] = payload
        self.runtime_available = successes > 0
        return self.runtime_available
