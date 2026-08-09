"""Credential-safe Semrush Backlinks API v4 client."""

from __future__ import annotations

import json
import csv
import io
from typing import Any

import httpx


SEMRUSH_V4_BASE = "https://api.semrush.com/apis/v4/backlinks/v1"
SEMRUSH_ANALYTICS_BASE = "https://api.semrush.com/"
MAX_LOST_LINKS = 500
MAX_ANALYTICS_ROWS = 500
LOST_LINK_FIELDS = (
    "source_url,source_domain,target_url,anchor,domain_score,page_score,"
    "is_lost,is_nofollow,last_seen_at,response_code"
)


class SemrushAPIError(RuntimeError):
    """A sanitized Semrush failure safe for logs and artifacts."""


class SemrushClient:
    def __init__(self, api_key: str, *, transport: httpx.BaseTransport | None = None,
                 timeout: float = 30.0) -> None:
        if not api_key:
            raise ValueError("Semrush API key is required")
        self._api_key = api_key
        self._client = httpx.Client(
            headers={"Authorization": f"Apikey {api_key}", "Accept": "application/json"},
            transport=transport, timeout=timeout)
        self._cache: dict[str, Any] = {}

    def _request(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        cache_key = endpoint + ":" + json.dumps(params, sort_keys=True, separators=(",", ":"))
        if cache_key in self._cache:
            return self._cache[cache_key]
        try:
            response = self._client.get(f"{SEMRUSH_V4_BASE}/{endpoint}", params=params)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise SemrushAPIError("Semrush request timed out") from exc
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
            raise SemrushAPIError(f"Semrush {label} (HTTP {status})") from exc
        except httpx.HTTPError as exc:
            raise SemrushAPIError(f"Semrush transport error ({type(exc).__name__})") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise SemrushAPIError("Semrush returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise SemrushAPIError("Semrush returned an invalid JSON object")
        meta = payload.get("meta")
        if not isinstance(meta, dict) or meta.get("success") is not True:
            raise SemrushAPIError("Semrush returned an unsuccessful response")
        self._cache[cache_key] = payload
        return payload

    def backlinks_overview(self, target: str) -> dict[str, Any]:
        payload = self._request("overview", {
            "url": target, "scope": "ROOT_DOMAIN", "format": "json"})
        data = payload.get("data")
        if not isinstance(data, dict):
            raise SemrushAPIError("Semrush overview returned invalid data")
        return data

    def lost_backlinks(self, target: str, *, limit: int = 100) -> dict[str, Any]:
        bounded = max(1, min(int(limit), MAX_LOST_LINKS))
        payload = self._request("links", {
            "url": target, "scope": "ROOT_DOMAIN", "fields": LOST_LINK_FIELDS,
            "filter": "is_lost = true", "order_by": "domain_score",
            "direction": "DESC", "limit": bounded, "offset": 0, "format": "json",
        })
        data = payload.get("data")
        if not isinstance(data, list):
            raise SemrushAPIError("Semrush lost links returned invalid data")
        total = int((payload.get("meta") or {}).get("total", len(data)) or 0)
        return {
            "links": [item for item in data if isinstance(item, dict)],
            "total": total,
            "limit": bounded,
            "truncated": total > bounded,
        }

    def referring_domains(self, target: str, *, limit: int = 100) -> dict[str, Any]:
        bounded = max(1, min(int(limit), MAX_ANALYTICS_ROWS))
        payload = self._request("ref-domains", {
            "url": target, "scope": "ROOT_DOMAIN",
            "fields": "domain,domain_score,backlinks_count,first_seen_at,last_seen_at",
            "order_by": "domain_score", "direction": "DESC",
            "limit": bounded, "offset": 0, "format": "json",
        })
        data = payload.get("data")
        if not isinstance(data, list):
            raise SemrushAPIError("Semrush referring domains returned invalid data")
        total = int((payload.get("meta") or {}).get("total", len(data)) or 0)
        return {
            "domains": [item for item in data if isinstance(item, dict)],
            "total": total,
            "limit": bounded,
            "truncated": total > bounded,
        }

    def _analytics_report(
        self,
        report_type: str,
        target: str,
        *,
        database: str,
        columns: tuple[str, ...],
        limit: int,
    ) -> list[dict[str, str]]:
        bounded = max(1, min(int(limit), MAX_ANALYTICS_ROWS))
        params = {
            "type": report_type,
            "key": self._api_key,
            "domain": target,
            "database": database,
            "display_limit": bounded,
            "export_columns": ",".join(columns),
            "export_escape": 1,
        }
        cache_key = "analytics:" + json.dumps(
            {key: value for key, value in params.items() if key != "key"},
            sort_keys=True, separators=(",", ":"))
        if cache_key in self._cache:
            return self._cache[cache_key]
        try:
            response = self._client.get(SEMRUSH_ANALYTICS_BASE, params=params)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise SemrushAPIError("Semrush analytics request timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise SemrushAPIError(
                f"Semrush analytics HTTP error ({exc.response.status_code})") from exc
        except httpx.HTTPError as exc:
            raise SemrushAPIError(
                f"Semrush analytics transport error ({type(exc).__name__})") from exc
        body = response.text.lstrip("\ufeff").strip()
        if not body:
            rows: list[dict[str, str]] = []
        elif body.upper().startswith("ERROR"):
            raise SemrushAPIError("Semrush analytics returned an unsuccessful response")
        else:
            parsed = list(csv.reader(io.StringIO(body), delimiter=";"))
            rows = [dict(zip(columns, row)) for row in parsed[1:] if row]
        self._cache[cache_key] = rows
        return rows

    @staticmethod
    def _number(value: str, cast):
        try:
            return cast(value)
        except (TypeError, ValueError):
            return 0 if cast is int else 0.0

    def domain_keywords(self, target: str, *, database: str = "us",
                        limit: int = 100) -> list[dict[str, Any]]:
        """Return bounded domain keyword rankings with built-in position deltas."""
        rows = self._analytics_report(
            "domain_organic", target, database=database,
            columns=("Ph", "Po", "Pp", "Pd", "Nq", "Ur", "Tr"), limit=limit)
        return [{
            "keyword": row.get("Ph", ""),
            "position": self._number(row.get("Po", ""), int),
            "previous_position": self._number(row.get("Pp", ""), int),
            "position_change": self._number(row.get("Pd", ""), int),
            "search_volume": self._number(row.get("Nq", ""), int),
            "url": row.get("Ur", ""),
            "traffic_pct": self._number(row.get("Tr", ""), float),
        } for row in rows]

    def organic_competitors(self, target: str, *, database: str = "us",
                            limit: int = 25) -> list[dict[str, Any]]:
        """Return bounded organic-search competitor context for the target."""
        rows = self._analytics_report(
            "domain_organic_organic", target, database=database,
            columns=("Dn", "Cr", "Np", "Or", "Ot"), limit=limit)
        return [{
            "domain": row.get("Dn", ""),
            "competition_level": self._number(row.get("Cr", ""), float),
            "common_keywords": self._number(row.get("Np", ""), int),
            "organic_keywords": self._number(row.get("Or", ""), int),
            "organic_traffic": self._number(row.get("Ot", ""), int),
        } for row in rows]
