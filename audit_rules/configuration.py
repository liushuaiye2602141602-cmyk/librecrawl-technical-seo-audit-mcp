"""Validated environment defaults for audit orchestration controls."""

from __future__ import annotations

import os
from typing import Mapping


def _number(env: Mapping[str, str], name: str, default, minimum, maximum,
            cast, errors: list[str]):
    raw = env.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = cast(raw)
        if value < minimum or value > maximum:
            raise ValueError
        return value
    except (TypeError, ValueError):
        errors.append(
            f"{name} must be between {minimum} and {maximum}; using default {default}")
        return default


def _boolean(env: Mapping[str, str], name: str, default: bool,
             errors: list[str]) -> bool:
    raw = env.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    normalized = str(raw).strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    errors.append(f"{name} must be true or false; using default {str(default).lower()}")
    return default


def load_operational_settings(
    environ: Mapping[str, str] | None = None,
) -> tuple[dict, list[str]]:
    """Return safe runner settings and non-fatal, operator-facing errors."""
    env = os.environ if environ is None else environ
    errors: list[str] = []
    settings = {
        "fetch_timeout_s": _number(
            env, "AUDIT_FETCH_TIMEOUT_SECONDS", 20.0, 1.0, 120.0, float, errors),
        "fetch_workers": _number(
            env, "AUDIT_FETCH_WORKERS", 4, 1, 32, int, errors),
        "external_fetch_workers": _number(
            env, "AUDIT_EXTERNAL_FETCH_WORKERS", 8, 1, 32, int, errors),
        "fetch_delay_ms": _number(
            env, "AUDIT_FETCH_DELAY_MS", 500.0, 0.0, 10_000.0, float, errors),
        "content_check_limit": _number(
            env, "AUDIT_CONTENT_SAMPLE_LIMIT", 500, 0, 100_000, int, errors),
        "extended_check_limit": _number(
            env, "AUDIT_EXTENDED_SAMPLE_LIMIT", 500, 0, 100_000, int, errors),
        "report_pdf_enabled": _boolean(
            env, "AUDIT_REPORT_PDF_ENABLED", True, errors),
        "master_report_enabled": _boolean(
            env, "AUDIT_MASTER_REPORT_ENABLED", True, errors),
        "fill_sitemap_orphans": _boolean(
            env, "AUDIT_FILL_SITEMAP_ORPHANS", True, errors),
    }
    return settings, errors
