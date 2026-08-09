"""Privacy-safe, read-only WordPress administrator snapshot provider."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from audit_rules.context import PageContext, SiteContext
from audit_rules.providers.base import DataProvider


_SCHEMA = "wordpress-audit-v1"
_MAX_BYTES = 5 * 1024 * 1024
_FORBIDDEN_KEYS = {
    "api_key", "api_token", "authorization", "cookie", "email", "ip",
    "password", "secret", "token", "username", "user_login", "value",
}


class SnapshotValidationError(ValueError):
    """Raised when a privileged snapshot is unsafe or malformed."""


def _check_forbidden_keys(value) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise SnapshotValidationError("forbidden sensitive field")
            _check_forbidden_keys(item)
    elif isinstance(value, list):
        for item in value:
            _check_forbidden_keys(item)


def _non_negative_int(value, field: str) -> int:
    if isinstance(value, bool):
        raise SnapshotValidationError(f"invalid {field}")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise SnapshotValidationError(f"invalid {field}") from exc
    if number < 0:
        raise SnapshotValidationError(f"invalid {field}")
    return number


def _required_bool(record: dict, field: str) -> bool:
    value = record.get(field)
    if not isinstance(value, bool):
        raise SnapshotValidationError(f"invalid {field}")
    return value


def _component(record, family: str) -> dict:
    if not isinstance(record, dict):
        raise SnapshotValidationError(f"invalid {family} record")
    slug, version, status = record.get("slug"), record.get("version"), record.get("status")
    if not all(isinstance(item, str) and item.strip() for item in (slug, version, status)):
        raise SnapshotValidationError(f"invalid {family} record")
    if status not in {"active", "inactive"}:
        raise SnapshotValidationError(f"invalid {family} status")
    return {
        "slug": slug.strip(), "version": version.strip(), "status": status,
        "update_available": _required_bool(record, "update_available"),
        "last_updated_days": _non_negative_int(record.get("last_updated_days"), "last_updated_days"),
        "abandoned": _required_bool(record, "abandoned"),
        "vulnerable": _required_bool(record, "vulnerable"),
    }


def _normalize(raw: dict, audited_url: str, max_age_hours: int) -> dict:
    if not isinstance(raw, dict) or raw.get("schema_version") != _SCHEMA:
        raise SnapshotValidationError("unsupported schema")
    _check_forbidden_keys(raw)

    site_url = raw.get("site_url")
    snapshot_host = urlsplit(str(site_url or "")).hostname
    audited_host = urlsplit(str(audited_url or "")).hostname
    if not snapshot_host or not audited_host or snapshot_host.lower() != audited_host.lower():
        raise SnapshotValidationError("site host mismatch")

    try:
        collected = datetime.fromisoformat(str(raw.get("collected_at", "")).replace("Z", "+00:00"))
    except ValueError as exc:
        raise SnapshotValidationError("invalid collected_at") from exc
    if collected.tzinfo is None:
        raise SnapshotValidationError("collected_at must include timezone")
    age_hours = (datetime.now(timezone.utc) - collected.astimezone(timezone.utc)).total_seconds() / 3600
    if age_hours < -1 or age_hours > max_age_hours:
        raise SnapshotValidationError("snapshot outside allowed age")

    core, php = raw.get("core"), raw.get("php")
    if not isinstance(core, dict) or not isinstance(core.get("version"), str):
        raise SnapshotValidationError("invalid core record")
    if not isinstance(php, dict) or not isinstance(php.get("version"), str):
        raise SnapshotValidationError("invalid php record")
    normalized_core = {
        "version": core["version"].strip(),
        "update_available": _required_bool(core, "update_available"),
        "vulnerable": _required_bool(core, "vulnerable"),
    }

    plugins = [_component(item, "plugin") for item in raw.get("plugins", [])]
    themes = [_component(item, "theme") for item in raw.get("themes", [])]
    if not isinstance(raw.get("plugins"), list) or not isinstance(raw.get("themes"), list):
        raise SnapshotValidationError("invalid component inventory")

    cron_events = []
    if not isinstance(raw.get("cron_events"), list):
        raise SnapshotValidationError("invalid cron inventory")
    for item in raw["cron_events"]:
        if not isinstance(item, dict) or not isinstance(item.get("hook"), str) or not item["hook"].strip():
            raise SnapshotValidationError("invalid cron record")
        cron_events.append({
            "hook": item["hook"].strip(),
            "interval_seconds": _non_negative_int(item.get("interval_seconds"), "interval_seconds"),
            "overdue_seconds": _non_negative_int(item.get("overdue_seconds"), "overdue_seconds"),
        })

    autoload = raw.get("autoload")
    if not isinstance(autoload, dict) or not isinstance(autoload.get("largest_options"), list):
        raise SnapshotValidationError("invalid autoload summary")
    options = []
    for item in autoload["largest_options"]:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip():
            raise SnapshotValidationError("invalid autoload option")
        options.append({"name": item["name"].strip(),
                        "bytes": _non_negative_int(item.get("bytes"), "option bytes")})

    administrators = raw.get("administrators")
    if not isinstance(administrators, list):
        raise SnapshotValidationError("invalid administrator summary")
    without_2fa = 0
    for item in administrators:
        if not isinstance(item, dict):
            raise SnapshotValidationError("invalid administrator record")
        if not _required_bool(item, "two_factor_enabled"):
            without_2fa += 1

    return {
        "schema_version": _SCHEMA, "collected_at": collected.isoformat(),
        "site_host": snapshot_host.lower(), "core": normalized_core,
        "php": {"version": php["version"].strip()}, "plugins": plugins,
        "themes": themes, "cron_events": cron_events,
        "autoload": {
            "total_bytes": _non_negative_int(autoload.get("total_bytes"), "autoload total"),
            "largest_options": options,
        },
        "admin_total": len(administrators), "admin_without_2fa": without_2fa,
        "errors": [],
    }


class WordPressPrivilegedProvider(DataProvider):
    """Consume a local administrator-generated snapshot; perform no remote I/O."""

    def __init__(self, path: str = "", *, max_age_hours: int | None = None) -> None:
        self._path = Path(path or os.getenv("WP_AUDIT_EXPORT_PATH", ""))
        try:
            parsed_age = int(max_age_hours if max_age_hours is not None
                             else os.getenv("WP_AUDIT_MAX_AGE_HOURS", "168"))
        except (TypeError, ValueError):
            parsed_age = 168
        self._max_age_hours = max(1, min(parsed_age, 24 * 30))
        self.runtime_available = False

    @property
    def name(self) -> str:
        return "WordPress Privileged"

    def is_available(self) -> bool:
        return bool(
            os.getenv("MASTER_AUDIT_V3_ENABLED", "false").lower() == "true"
            and os.getenv("MASTER_AUDIT_WORDPRESS_ENABLED", "false").lower() == "true"
            and self._path.is_file()
        )

    def missing_rule_ids(self) -> list[int]:
        return [36, 64, 65, 68, 69]

    def enrich_site(self, ctx: SiteContext) -> None:
        pass

    def enrich_page(self, ctx: PageContext) -> None:
        pass

    def collect(self, site_ctx: SiteContext, page_contexts: list[PageContext],
                shared_data: dict) -> bool:
        try:
            if self._path.stat().st_size > _MAX_BYTES:
                raise SnapshotValidationError("snapshot exceeds size limit")
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            payload = _normalize(raw, site_ctx.base_url, self._max_age_hours)
        except (OSError, UnicodeError, json.JSONDecodeError, SnapshotValidationError) as exc:
            shared_data["wordpress_privileged"] = {
                "errors": [f"snapshot:{type(exc).__name__}"]}
            self.runtime_available = False
            return False
        shared_data["wordpress_privileged"] = payload
        site_ctx.site_profile = "wordpress"
        self.runtime_available = True
        return True
