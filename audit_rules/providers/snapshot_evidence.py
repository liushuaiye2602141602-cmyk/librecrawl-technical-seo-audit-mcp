"""Shared validation primitives for local external-evidence snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlsplit


MAX_SNAPSHOT_BYTES = 5 * 1024 * 1024
FORBIDDEN_KEYS = {
    "api_key", "api_token", "authorization", "body", "cookie", "cookies",
    "email", "headers", "html", "ip", "password", "raw_html",
    "rendered_html", "screenshot", "secret", "text", "token", "username",
    "value",
}


class EvidenceValidationError(ValueError):
    pass


def reject_sensitive_fields(value) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise EvidenceValidationError("forbidden sensitive field")
            reject_sensitive_fields(item)
    elif isinstance(value, list):
        for item in value:
            reject_sensitive_fields(item)


def load_snapshot(path: Path) -> dict:
    if path.stat().st_size > MAX_SNAPSHOT_BYTES:
        raise EvidenceValidationError("snapshot exceeds size limit")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise EvidenceValidationError("snapshot must be an object")
    reject_sensitive_fields(raw)
    return raw


def validate_snapshot_identity(raw: dict, *, schema: str, audited_url: str,
                               max_age_hours: int) -> tuple[str, str]:
    if raw.get("schema_version") != schema:
        raise EvidenceValidationError("unsupported schema")
    snapshot_host = urlsplit(str(raw.get("site_url") or "")).hostname
    audited_host = urlsplit(str(audited_url or "")).hostname
    if not snapshot_host or not audited_host or snapshot_host.lower() != audited_host.lower():
        raise EvidenceValidationError("site host mismatch")
    try:
        collected = datetime.fromisoformat(
            str(raw.get("collected_at", "")).replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceValidationError("invalid collected_at") from exc
    if collected.tzinfo is None:
        raise EvidenceValidationError("collected_at must include timezone")
    age = (datetime.now(timezone.utc) - collected.astimezone(timezone.utc)).total_seconds() / 3600
    if age < -1 or age > max_age_hours:
        raise EvidenceValidationError("snapshot outside allowed age")
    return snapshot_host.lower(), collected.isoformat()


def same_host_url(value, expected_host: str) -> str:
    if not isinstance(value, str):
        raise EvidenceValidationError("invalid URL")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise EvidenceValidationError("invalid URL")
    if parsed.hostname.lower() != expected_host.lower():
        raise EvidenceValidationError("cross-host URL")
    return value


def non_negative_int(value, field: str) -> int:
    if isinstance(value, bool):
        raise EvidenceValidationError(f"invalid {field}")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise EvidenceValidationError(f"invalid {field}") from exc
    if number < 0:
        raise EvidenceValidationError(f"invalid {field}")
    return number


def required_bool(value, field: str) -> bool:
    if not isinstance(value, bool):
        raise EvidenceValidationError(f"invalid {field}")
    return value
