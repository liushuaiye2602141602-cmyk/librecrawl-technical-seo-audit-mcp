"""Credential-safe GA4 Admin and Data API REST client."""

from __future__ import annotations

import json
from typing import Any

import httpx


ADMIN_BASE = "https://analyticsadmin.googleapis.com/v1beta"
DATA_BASE = "https://analyticsdata.googleapis.com/v1beta"


class GA4APIError(RuntimeError):
    """Sanitized GA4 API failure."""


class GA4Client:
    def __init__(self, access_token: str, property_id: str, *,
                 transport: httpx.BaseTransport | None = None,
                 timeout: float = 30.0) -> None:
        if not access_token:
            raise ValueError("GA4 access token is required")
        raw = str(property_id).strip()
        if raw.startswith("properties/"):
            raw = raw.split("/", 1)[1]
        if not raw:
            raise ValueError("GA4 property ID is required")
        self.property_name = f"properties/{raw}"
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            transport=transport, timeout=timeout)
        self._cache: dict[str, dict[str, Any]] = {}

    def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        cache_key = json.dumps([method, url, kwargs.get("params"), kwargs.get("json")],
                               sort_keys=True, separators=(",", ":"))
        if cache_key in self._cache:
            return self._cache[cache_key]
        try:
            response = self._client.request(method, url, **kwargs)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise GA4APIError("GA4 request timed out") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 401:
                label = "authentication failed"
            elif status == 403:
                label = "authorization failed"
            elif status == 429:
                label = "quota exceeded"
            elif status >= 500:
                label = "server error"
            else:
                label = "HTTP error"
            raise GA4APIError(f"GA4 {label} (HTTP {status})") from exc
        except httpx.HTTPError as exc:
            raise GA4APIError(f"GA4 transport error ({type(exc).__name__})") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise GA4APIError("GA4 returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise GA4APIError("GA4 returned an invalid JSON object")
        self._cache[cache_key] = payload
        return payload

    def get_property(self) -> dict[str, Any]:
        return self._request("GET", f"{ADMIN_BASE}/{self.property_name}")

    def list_key_events(self) -> list[dict[str, Any]]:
        cache_key = "key_events:all"
        if cache_key in self._cache:
            return self._cache[cache_key]["items"]
        events: list[dict[str, Any]] = []
        token = ""
        while True:
            params = {"pageSize": 200}
            if token:
                params["pageToken"] = token
            payload = self._request(
                "GET", f"{ADMIN_BASE}/{self.property_name}/keyEvents", params=params)
            items = payload.get("keyEvents") or []
            if not isinstance(items, list):
                raise GA4APIError("GA4 key events returned invalid data")
            events.extend(item for item in items if isinstance(item, dict))
            token = str(payload.get("nextPageToken") or "")
            if not token:
                break
        self._cache[cache_key] = {"items": events}
        return events

    def run_report(self, start_date: str, end_date: str, *,
                   dimensions: list[str], metrics: list[str],
                   limit: int = 100_000) -> dict[str, Any]:
        body = {
            "dateRanges": [{"startDate": start_date, "endDate": end_date}],
            "dimensions": [{"name": name} for name in dimensions],
            "metrics": [{"name": name} for name in metrics],
            "limit": str(max(1, min(int(limit), 100_000))),
        }
        return self._request(
            "POST", f"{DATA_BASE}/{self.property_name}:runReport", json=body)
