"""Credential-safe Google Search Console REST client."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import httpx


SEARCH_CONSOLE_BASE = "https://searchconsole.googleapis.com"
WEBMASTERS_BASE = f"{SEARCH_CONSOLE_BASE}/webmasters/v3"
MAX_PAGE_SIZE = 25_000
DEFAULT_MAX_ROWS = 50_000


class GSCAPIError(RuntimeError):
    """A sanitized Search Console API failure safe for logs and artifacts."""


class GSCClient:
    """Small synchronous client for the read-only Search Console APIs."""

    def __init__(
        self,
        access_token: str,
        site_url: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        if not access_token:
            raise ValueError("GSC access token is required")
        if not site_url:
            raise ValueError("GSC site URL is required")
        self.site_url = site_url
        self._client = httpx.Client(
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=timeout,
            transport=transport,
        )
        self._cache: dict[str, dict[str, Any]] = {}

    @property
    def _encoded_site_url(self) -> str:
        return quote(self.site_url, safe="")

    def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self._client.request(method, url, **kwargs)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise GSCAPIError("GSC request timed out") from exc
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
            raise GSCAPIError(f"GSC {label} (HTTP {status})") from exc
        except httpx.HTTPError as exc:
            raise GSCAPIError(f"GSC transport error ({type(exc).__name__})") from exc

        try:
            payload = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise GSCAPIError("GSC returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise GSCAPIError("GSC returned an invalid JSON object")
        return payload

    def query_search_analytics(
        self,
        start_date: str,
        end_date: str,
        *,
        dimensions: list[str] | None = None,
        search_type: str = "web",
        data_state: str = "final",
        row_limit: int = MAX_PAGE_SIZE,
        max_rows: int = DEFAULT_MAX_ROWS,
    ) -> dict[str, Any]:
        """Return paged Search Analytics rows for one finalized date window."""
        page_size = max(1, min(int(row_limit), MAX_PAGE_SIZE))
        total_limit = max(1, int(max_rows))
        base_body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": list(dimensions or []),
            "type": search_type,
            "dataState": data_state,
            "rowLimit": page_size,
        }
        cache_key = json.dumps(
            {**base_body, "maxRows": total_limit}, sort_keys=True, separators=(",", ":")
        )
        if cache_key in self._cache:
            return self._cache[cache_key]

        url = (
            f"{WEBMASTERS_BASE}/sites/{self._encoded_site_url}"
            "/searchAnalytics/query"
        )
        rows: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {}
        start_row = 0
        while len(rows) < total_limit:
            body = {**base_body, "startRow": start_row}
            payload = self._request("POST", url, json=body)
            page_rows = payload.get("rows") or []
            if not isinstance(page_rows, list):
                raise GSCAPIError("GSC Search Analytics returned invalid rows")
            rows.extend(row for row in page_rows if isinstance(row, dict))
            metadata = payload.get("metadata") or metadata
            if not page_rows or len(page_rows) < page_size:
                break
            start_row += page_size

        result = {"rows": rows[:total_limit]}
        if metadata:
            result["metadata"] = metadata
        self._cache[cache_key] = result
        return result

    def inspect_url(self, inspection_url: str, *, language_code: str = "en-US") -> dict[str, Any]:
        cache_key = f"inspect:{inspection_url}:{language_code}"
        if cache_key not in self._cache:
            self._cache[cache_key] = self._request(
                "POST",
                f"{SEARCH_CONSOLE_BASE}/v1/urlInspection/index:inspect",
                json={
                    "inspectionUrl": inspection_url,
                    "siteUrl": self.site_url,
                    "languageCode": language_code,
                },
            )
        return self._cache[cache_key]

    def list_sitemaps(self) -> dict[str, Any]:
        cache_key = "sitemaps"
        if cache_key not in self._cache:
            self._cache[cache_key] = self._request(
                "GET", f"{WEBMASTERS_BASE}/sites/{self._encoded_site_url}/sitemaps"
            )
        return self._cache[cache_key]
