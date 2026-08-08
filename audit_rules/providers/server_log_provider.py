"""Streaming Apache/Nginx/JSON access-log provider."""

from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlsplit

from audit_rules.context import PageContext, SiteContext
from audit_rules.providers.base import DataProvider


_COMBINED = re.compile(
    r'^\S+\s+\S+\s+\S+\s+\[[^]]+\]\s+"(?P<method>\S+)\s+(?P<target>\S+)\s+[^"]+"\s+'
    r'(?P<status>\d{3})\s+\S+\s+"[^"]*"\s+"(?P<ua>[^"]*)"')
_FACETS = {"color", "size", "brand", "sort", "order", "filter", "price", "material", "rating"}
_SESSIONS = {"phpsessid", "jsessionid", "sid", "sessionid", "session_id", "aspsessionid"}


def _bot_class(user_agent: str) -> str:
    lower = user_agent.lower()
    for needle, label in (
        ("googlebot", "Googlebot"), ("bingbot", "Bingbot"),
        ("yandexbot", "YandexBot"), ("baiduspider", "Baiduspider")):
        if needle in lower:
            return label
    return "OtherBot" if any(token in lower for token in ("bot", "crawler", "spider")) else "Human/Other"


def normalize_log_target(target: str) -> str:
    parsed = urlsplit(target)
    path = parsed.path or "/"
    names = sorted({str(key).lower() for key, _ in parse_qsl(parsed.query, keep_blank_values=True)})
    return path + ("?" + "&".join(names) if names else "")


def _is_waste_target(target: str) -> bool:
    parsed = urlsplit(target)
    path = parsed.path.lower()
    names = set(parse_qsl(parsed.query, keep_blank_values=True))
    # Normalized targets contain bare names, which parse_qsl represents with empty values.
    keys = {str(key).lower() for key, _ in names}
    return bool(
        re.search(r"/(?:search|s)/?$", path)
        or keys & _SESSIONS
        or keys & {"q", "query", "search", "s"}
        or len(keys & _FACETS) >= 4
        or len(keys) >= 6)


def parse_log_line(line: str) -> dict | None:
    """Parse one log line into a privacy-safe normalized record."""
    raw = line.strip()
    if not raw:
        return None
    if raw.startswith("{"):
        try:
            item = json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            return None
        if not isinstance(item, dict):
            return None
        method = item.get("request_method") or item.get("method")
        target = item.get("request_uri") or item.get("request") or item.get("uri")
        status = item.get("status") or item.get("status_code")
        ua = item.get("http_user_agent") or item.get("user_agent") or ""
        duration = item.get("request_time")
        try:
            duration_ms = round(float(duration) * 1000) if duration is not None else None
            status_num = int(status)
        except (TypeError, ValueError):
            return None
    else:
        match = _COMBINED.match(raw)
        if not match:
            return None
        method, target, status_num, ua = (
            match.group("method"), match.group("target"),
            int(match.group("status")), match.group("ua"))
        duration_ms = None
    if not method or not target:
        return None
    return {"method": str(method), "target": normalize_log_target(str(target)),
            "status": status_num, "bot": _bot_class(str(ua)),
            "response_time_ms": duration_ms}


class ServerLogDataProvider(DataProvider):
    def __init__(self, path: str = "", *, max_lines: int | None = None) -> None:
        self._path = Path(path or os.getenv("SERVER_LOG_PATH", ""))
        try:
            parsed = int(max_lines if max_lines is not None else os.getenv("SERVER_LOG_MAX_LINES", "1000000"))
        except (TypeError, ValueError):
            parsed = 1_000_000
        self._max_lines = max(1, min(parsed, 5_000_000))
        self.runtime_available = False

    @property
    def name(self) -> str:
        return "Server Logs"

    def is_available(self) -> bool:
        return bool(
            os.getenv("MASTER_AUDIT_V3_ENABLED", "false").lower() == "true"
            and os.getenv("MASTER_AUDIT_SERVER_LOGS_ENABLED", "true").lower() == "true"
            and self._path.is_file())

    def missing_rule_ids(self) -> list[int]:
        return [5, 20, 33]

    def enrich_site(self, ctx: SiteContext) -> None:
        pass

    def enrich_page(self, ctx: PageContext) -> None:
        pass

    def collect(self, site_ctx: SiteContext, page_contexts: list[PageContext],
                shared_data: dict) -> bool:
        status_counts: Counter[str] = Counter()
        bot_counts: Counter[str] = Counter()
        url_counts: Counter[str] = Counter()
        bot_url_counts: Counter[str] = Counter()
        waste_bot_counts: Counter[str] = Counter()
        durations: list[int] = []
        processed = valid = malformed = 0
        truncated = False
        try:
            with self._path.open("r", encoding="utf-8", errors="replace") as stream:
                for index, line in enumerate(stream):
                    if index >= self._max_lines:
                        truncated = True
                        break
                    processed += 1
                    record = parse_log_line(line)
                    if record is None:
                        malformed += 1
                        continue
                    valid += 1
                    status_counts[str(record["status"])] += 1
                    url_counts[record["target"]] += 1
                    bot = record["bot"]
                    if bot != "Human/Other":
                        bot_counts[bot] += 1
                        bot_url_counts[f"{bot}|{record['target']}"] += 1
                        if _is_waste_target(record["target"]):
                            waste_bot_counts[record["target"]] += 1
                    if record["response_time_ms"] is not None:
                        durations.append(record["response_time_ms"])
        except OSError as exc:
            shared_data["server_logs"] = {"errors": [f"read:{type(exc).__name__}"]}
            self.runtime_available = False
            return False
        durations.sort()
        p95 = durations[min(len(durations) - 1, int(len(durations) * 0.95))] if durations else None
        payload = {
            "processed_lines": processed, "valid_lines": valid,
            "malformed_lines": malformed, "truncated": truncated,
            "status_counts": dict(status_counts), "bot_counts": dict(bot_counts),
            "url_counts": dict(url_counts), "bot_url_counts": dict(bot_url_counts),
            "waste_bot_counts": dict(waste_bot_counts),
            "response_time_p95_ms": p95, "errors": [],
        }
        shared_data["server_logs"] = payload
        self.runtime_available = valid > 0
        return self.runtime_available
