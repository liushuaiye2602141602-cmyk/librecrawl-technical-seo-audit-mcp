"""Versioned, credential-free inputs for offline Master Audit replay."""

from __future__ import annotations

import base64
import binascii
from dataclasses import asdict, dataclass, is_dataclass
import gzip
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import parse_qsl, urlsplit


SCHEMA_VERSION = "1.0"
ARTIFACT_TYPE = "audit_replay"

SAFE_RESPONSE_HEADERS = frozenset({
    "age",
    "cache-control",
    "content-language",
    "content-security-policy",
    "content-type",
    "etag",
    "last-modified",
    "link",
    "referrer-policy",
    "strict-transport-security",
    "x-content-type-options",
    "x-frame-options",
    "x-robots-tag",
})

# Current LibreCrawl EXPORT_FIELDS, sitemap-fill additions, and normalized
# crawl evidence read by PageContext/adapters. Unknown fields are deliberately
# excluded from the v1 contract instead of being copied opportunistically.
REPLAY_PAGE_FIELDS = frozenset({
    "analytics", "broken_images", "canonical_url", "charset", "content_hash",
    "depth", "error_type", "external_links", "generator", "h1", "h2", "h3",
    "hreflang", "images", "internal_links", "issues_detected", "json_ld",
    "lang", "linked_from", "links_detailed", "meta_description", "mixed_content",
    "mixed_content_urls", "og_tags", "redirects", "response_time_ms", "robots",
    "size", "source", "status_code", "structured_data", "title", "twitter_tags",
    "url", "viewport", "word_count",
})

REPLAY_LINK_FIELDS = frozenset({
    "anchor", "error", "is_internal", "rel", "redirect_chain", "source_url",
    "status_class", "status_code", "target_url",
})
REPLAY_PAGE_LINK_FIELDS = frozenset({
    "anchor", "error", "is_internal", "rel", "redirect_chain", "status_code",
    "url",
})

REQUIRED_OBJECT_FIELDS = frozenset({
    "crawl_metadata", "counts", "site_data", "sitemap_reconciliation",
    "crawl_completeness", "provider_evidence",
})
REQUIRED_LIST_FIELDS = frozenset({"pages", "links"})
REQUIRED_CRAWL_METADATA_FIELDS = frozenset({
    "crawl_parameters", "truncation_status",
})
_SENSITIVE_KEYS = frozenset({
    "authorization", "proxy_authorization", "cookie", "set_cookie",
    "www_authenticate", "api_key", "x_api_key", "access_token",
    "refresh_token", "session_token", "password", "private_key",
    "client_secret", "oauth_token", "auth", "credential", "credentials",
    "secret", "session", "token",
})
_CREDENTIAL_QUERY_KEYS = frozenset({
    "access_token", "api_key", "apikey", "auth", "authorization",
    "client_secret", "credential", "key", "oauth_token", "password",
    "secret", "session", "session_token", "sessionid", "sid", "phpsessid",
    "jsessionid", "token", "sig", "signature", "x_amz_credential",
    "x_amz_signature", "x_goog_credential", "x_goog_signature",
    "awsaccesskeyid",
})
_TOKEN_VALUE_RE = re.compile(
    r"(?i)(?:^|[^A-Za-z0-9_])(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AIza[0-9A-Za-z_-]{20,})|"
    r"(?:^|\s)eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"
)
_BASIC_AUTH_RE = re.compile(
    r"(?<![A-Za-z0-9])basic\s+([A-Za-z0-9+/]+={0,2})(?![A-Za-z0-9+/=])",
    flags=re.IGNORECASE,
)
_BEARER_AUTH_RE = re.compile(
    r"(?<![A-Za-z0-9])bearer\s+([A-Za-z0-9._~+/\-]+={0,})(?![A-Za-z0-9._~+/=\-])",
    flags=re.IGNORECASE,
)

_PROVIDER_DATA_FIELDS = {
    "gsc": frozenset({
        "current_rows", "previous_rows", "sitemaps", "inspections",
        "inspection_eligible", "inspection_attempted", "inspection_succeeded",
        "current_start", "current_end", "previous_start", "previous_end", "errors",
    }),
    "ga4": frozenset({
        "property", "key_events", "daily_activity", "event_counts",
        "start_date", "end_date", "errors",
    }),
    "semrush": frozenset({
        "target", "database", "overview", "lost_links", "lost_total",
        "lost_truncated", "referring_domains", "referring_domains_total",
        "referring_domains_truncated", "domain_keywords", "organic_competitors",
        "errors",
    }),
    "server_logs": frozenset({
        "processed_lines", "valid_lines", "malformed_lines", "truncated",
        "status_counts", "bot_counts", "url_counts", "bot_url_counts",
        "waste_bot_counts", "response_time_p95_ms", "errors",
    }),
    "wordpress_privileged": frozenset({
        "schema_version", "collected_at", "site_host", "core", "php", "plugins",
        "themes", "cron_events", "autoload", "admin_total", "admin_without_2fa",
        "errors",
    }),
    "render_snapshot": frozenset({
        "schema_version", "collected_at", "site_host", "pages", "errors",
    }),
    "availability_snapshot": frozenset({
        "schema_version", "collected_at", "site_host", "window_hours", "endpoints",
        "errors",
    }),
}

_PROVIDER_RUNTIME = {
    "gsc": ("GSC API", {"GSC API", "GSC"}),
    "ga4": ("GA4 API", {"GA4 API", "GA4"}),
    "semrush": ("Semrush API", {"Semrush API", "Semrush"}),
    "server_logs": ("Server Logs", {"Server Logs"}),
    "wordpress_privileged": ("WordPress Privileged", {"WordPress Privileged"}),
    "render_snapshot": ("Rendered DOM Snapshot", {"Rendered DOM Snapshot"}),
    "availability_snapshot": ("Availability Monitor", {"Availability Monitor"}),
}


class ReplayValidationError(ValueError):
    """Raised when an audit replay document violates the v1 contract."""


@dataclass(frozen=True)
class ReplayValidationResult:
    valid: bool
    page_count: int
    link_count: int


def _json_safe_header_value(value: Any) -> str | list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return str(value)


def sanitize_response_headers(headers: dict | None) -> dict[str, str | list[str]]:
    """Retain only credential-free response headers used by audit rules."""
    if not isinstance(headers, dict):
        return {}
    safe = {}
    for name, value in headers.items():
        normalized = str(name).strip().lower()
        safe_value = _json_safe_header_value(value)
        values = safe_value if isinstance(safe_value, list) else [safe_value]
        if (normalized in SAFE_RESPONSE_HEADERS
                and not any(_string_contains_credential(item) for item in values)):
            safe[normalized] = safe_value
    return dict(sorted(safe.items()))


def _normalized_key(value: Any) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _is_sensitive_key(value: Any) -> bool:
    normalized = _normalized_key(value)
    if normalized in _SENSITIVE_KEYS:
        return True
    return any(marker in normalized for marker in (
        "api_key", "access_token", "refresh_token", "session_token",
        "client_secret", "private_key", "authorization", "credential",
    ))


def _string_contains_credential(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    if (_is_authorization_value(text) or _TOKEN_VALUE_RE.search(text)
            or "-----BEGIN PRIVATE KEY-----" in text):
        return True
    link_targets = re.findall(r"<([^>]+)>", text)
    if any(_string_contains_credential(target) for target in link_targets):
        return True
    try:
        parsed = urlsplit(text)
    except ValueError:
        return False
    if parsed.username is not None or parsed.password is not None:
        return True
    def sensitive_parameter(key: str) -> bool:
        normalized = _normalized_key(key)
        return (normalized in _CREDENTIAL_QUERY_KEYS
                or _is_sensitive_key(normalized)
                or normalized.endswith("_signature")
                or normalized.endswith("_credential"))
    return any(
        sensitive_parameter(key)
        for component in (parsed.query, parsed.fragment)
        for key, _ in parse_qsl(component, keep_blank_values=True)
    )


def _is_authorization_value(value: str) -> bool:
    """Recognize Basic/Bearer values in text without matching ordinary prose."""
    for basic_match in _BASIC_AUTH_RE.finditer(value):
        token = basic_match.group(1)
        padded_token = token + ("=" * (-len(token) % 4))
        try:
            decoded = base64.b64decode(padded_token, validate=True)
        except (binascii.Error, ValueError):
            continue
        if b":" in decoded:
            return True
    for bearer_match in _BEARER_AUTH_RE.finditer(value):
        token = bearer_match.group(1)
        normalized_token = token.rstrip(".")
        complete_value = (
            bearer_match.start() == 0
            and bearer_match.end() == len(value)
            and token == normalized_token
        )
        explicit_header = re.search(
            r'''["']?authorization["']?\s*:\s*["']?\s*$''',
            value[:bearer_match.start()],
            flags=re.IGNORECASE,
        ) is not None
        token_like = (
            len(normalized_token) >= 15
            or re.fullmatch(
                r"[A-Za-z0-9_-]{2,}(?:\.[A-Za-z0-9_-]{2,})+",
                normalized_token,
            ) is not None
        )
        if complete_value or explicit_header or token_like:
            return True
    return False


def _sanitize_json(value: Any) -> Any:
    """Recursively remove credential-bearing keys from normalized evidence."""
    if isinstance(value, dict):
        safe = {}
        for key, item in value.items():
            if _is_sensitive_key(key):
                continue
            if isinstance(item, str) and _string_contains_credential(item):
                continue
            safe[str(key)] = _sanitize_json(item)
        return safe
    if isinstance(value, list):
        return [_sanitize_json(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_json(item) for item in value]
    return value


def _sanitize_provider_data(name: str, payload: dict) -> dict:
    allowed = _PROVIDER_DATA_FIELDS[name]
    return {
        key: _sanitize_json(payload[key]) for key in sorted(allowed)
        if key in payload
    }


def _provider_has_evidence(
    name: str, payload: dict, *, collection_success: bool = False,
) -> bool:
    if collection_success:
        return True
    if name == "gsc":
        return any(bool(payload.get(key)) for key in (
            "current_rows", "previous_rows", "sitemaps", "inspections"))
    if name == "ga4":
        return payload.get("property") is not None or any(bool(payload.get(key)) for key in (
            "key_events", "daily_activity", "event_counts"))
    if name == "semrush":
        return bool(payload.get("overview")) or any(bool(payload.get(key)) for key in (
            "lost_links", "referring_domains", "domain_keywords", "organic_competitors"))
    if name == "server_logs":
        return isinstance(payload.get("valid_lines"), int) and payload["valid_lines"] > 0
    if name == "wordpress_privileged":
        return payload.get("schema_version") == "wordpress-audit-v1" and bool(payload.get("core"))
    if name == "render_snapshot":
        return payload.get("schema_version") == "render-audit-v1" and bool(payload.get("pages"))
    if name == "availability_snapshot":
        return (payload.get("schema_version") == "availability-monitor-v1"
                and bool(payload.get("endpoints")))
    return False


def _provider_runtime_succeeded(providers: dict, name: str) -> bool:
    expected_name = _PROVIDER_RUNTIME[name][0]
    for provider in providers.values():
        if getattr(provider, "name", "") == expected_name:
            return getattr(provider, "runtime_available", None) is True
    return False


def _page_record(page: dict) -> dict:
    record = {
        key: _sanitize_json(value) for key, value in page.items()
        if key in REPLAY_PAGE_FIELDS
    }
    headers = page.get("response_headers") or page.get("headers")
    if headers is not None:
        record["response_headers"] = sanitize_response_headers(headers)
    if isinstance(record.get("links_detailed"), list):
        record["links_detailed"] = [
            _page_link_record(item) for item in record["links_detailed"]
            if isinstance(item, dict) and _page_link_record(item).get("url")
        ]
    return record


def _page_link_record(link: dict) -> dict:
    target = str(link.get("target_url") or link.get("to") or
                 link.get("url") or link.get("href") or "")
    record = {
        "url": target,
        "anchor": _sanitize_json(link.get("anchor") or link.get("anchor_text") or ""),
        "rel": _sanitize_json(link.get("rel") or ""),
    }
    for key in ("is_internal", "status_code", "redirect_chain", "error"):
        if key in link:
            record[key] = _sanitize_json(link[key])
    return record


def _link_record(link: dict, *, default_source: str = "") -> dict:
    source = str(link.get("source_url") or link.get("from") or default_source)
    target = str(link.get("target_url") or link.get("to") or
                 link.get("url") or link.get("href") or "")
    record = {
        "source_url": source,
        "target_url": target,
        "anchor": _sanitize_json(link.get("anchor") or link.get("anchor_text") or ""),
        "rel": _sanitize_json(link.get("rel") or ""),
    }
    for key in ("is_internal", "status_code", "status_class", "redirect_chain", "error"):
        if key in link:
            record[key] = _sanitize_json(link[key])
    return record


def _link_sort_key(link: dict) -> tuple[str, ...]:
    return (
        str(link.get("source_url") or link.get("from") or ""),
        str(link.get("target_url") or link.get("to") or link.get("url") or
            link.get("href") or ""),
        str(link.get("anchor") or link.get("anchor_text") or ""),
        str(link.get("rel") or ""),
    )


def _normalized_links(pages: list[dict], links: list[dict]) -> list[dict]:
    candidates = [_link_record(link) for link in links]
    for page in pages:
        source_url = str(page.get("url") or "")
        for detail in page.get("links_detailed") or []:
            if not isinstance(detail, dict):
                continue
            target_url = str(
                detail.get("target_url") or detail.get("url") or
                detail.get("href") or ""
            )
            if not source_url or not target_url:
                continue
            record = _link_record(detail, default_source=source_url)
            candidates.append(record)
    unique = {}
    for record in candidates:
        if not record.get("source_url") or not record.get("target_url"):
            continue
        identity = tuple(record.get(key) for key in (
            "source_url", "target_url", "anchor", "rel"))
        if identity not in unique:
            unique[identity] = record
        else:
            for key, value in record.items():
                if key not in unique[identity] or unique[identity][key] in (None, "", []):
                    unique[identity][key] = value
    return sorted(unique.values(), key=_link_sort_key)


def build_replay_document(
    *,
    source_url: str,
    git_head: str,
    generated_at: str,
    crawl_metadata: dict,
    pages: list[dict],
    links: list[dict],
    site_data: dict,
    sitemap_reconciliation: dict,
    crawl_completeness: dict,
    provider_evidence: dict | None = None,
) -> dict:
    """Build a stable v1 replay document from current normalized inputs."""
    page_records = sorted(
        (_page_record(page) for page in pages),
        key=lambda page: str(page.get("url") or ""),
    )
    link_records = _normalized_links(pages, links)
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": ARTIFACT_TYPE,
        "generated_at": generated_at,
        "source_url": source_url,
        "git_head": git_head,
        "crawl_metadata": _sanitize_json(crawl_metadata),
        "counts": {"pages": len(page_records), "links": len(link_records)},
        "pages": page_records,
        "links": link_records,
        "site_data": _sanitize_json(site_data),
        "sitemap_reconciliation": _sanitize_json(sitemap_reconciliation),
        "crawl_completeness": _sanitize_json(crawl_completeness),
        "provider_evidence": _sanitize_json(provider_evidence or {}),
    }


def build_provider_evidence(audit_runner: Any) -> dict:
    """Serialize only normalized evidence already collected by this audit."""
    providers = getattr(audit_runner, "providers", {}) or {}
    pagespeed = providers.get("PageSpeed API")
    cache = getattr(pagespeed, "_cache", {}) if pagespeed is not None else {}
    strategies = list(getattr(pagespeed, "_strategies", []) or ["mobile"])
    snapshots = []
    for snapshot in cache.values():
        if is_dataclass(snapshot):
            row = asdict(snapshot)
        elif isinstance(snapshot, dict):
            row = dict(snapshot)
        else:
            continue
        snapshots.append(_sanitize_json(row))
    snapshots.sort(key=lambda row: (
        str(row.get("strategy") or ""), str(row.get("url") or "")))
    collected = sorted(
        str(row.get("fetch_timestamp") or "")
        for row in snapshots if row.get("fetch_timestamp")
    )
    successful_snapshots = [
        row for row in snapshots if row.get("psi_status") == "success"
    ]
    evidence = {
        "pagespeed": {
            "status": "CHECKED" if successful_snapshots else "LIVE_VALIDATION_PENDING",
            "strategy": strategies[0] if strategies else "mobile",
            "snapshots": snapshots,
            "collected_at": collected[-1] if collected else "",
        },
        "provider_status": {
            "ga4": "LIVE_VALIDATION_PENDING",
            "gsc": "LIVE_VALIDATION_PENDING",
            "semrush": "LIVE_VALIDATION_PENDING",
            "server_logs": "LIVE_VALIDATION_PENDING",
            "wordpress_privileged": "LIVE_VALIDATION_PENDING",
            "render_snapshot": "LIVE_VALIDATION_PENDING",
            "availability_snapshot": "LIVE_VALIDATION_PENDING",
        },
    }
    shared_data = getattr(audit_runner, "last_shared_data", {}) or {}
    for name in _PROVIDER_DATA_FIELDS:
        payload = shared_data.get(name)
        if not isinstance(payload, dict):
            continue
        collection_success = _provider_runtime_succeeded(providers, name)
        has_evidence = _provider_has_evidence(
            name, payload, collection_success=collection_success)
        status = "CHECKED" if has_evidence else "UNAVAILABLE"
        evidence["provider_status"][name] = status
        if has_evidence:
            evidence[name] = {
                "status": status,
                "collection_success": True,
                "data": _sanitize_provider_data(name, payload),
            }
    return evidence


def _performance_snapshot(record: dict):
    from dataclasses import fields
    from audit_rules.providers.performance_snapshot import (
        FontIssue, ImageOpportunity, LayoutShiftElement, PerformanceSnapshot,
        RenderBlockingResource, ThirdPartyEntity,
    )

    nested = {
        "render_blocking_resources": RenderBlockingResource,
        "image_opportunities": ImageOpportunity,
        "third_party_entities": ThirdPartyEntity,
        "font_display_issues": FontIssue,
        "layout_shift_elements": LayoutShiftElement,
    }
    allowed = {item.name for item in fields(PerformanceSnapshot)}
    values = {key: value for key, value in record.items() if key in allowed}
    for key, model in nested.items():
        rows = values.get(key)
        if isinstance(rows, list):
            model_fields = {item.name for item in fields(model)}
            values[key] = [model(**{
                item_key: item_value for item_key, item_value in row.items()
                if item_key in model_fields
            }) for row in rows if isinstance(row, dict)]
    return PerformanceSnapshot(**values)


def _valid_performance_snapshot_record(record: Any) -> bool:
    from dataclasses import fields
    from audit_rules.providers.performance_snapshot import (
        FontIssue, ImageOpportunity, LayoutShiftElement, PerformanceSnapshot,
        RenderBlockingResource, ThirdPartyEntity,
    )

    if not isinstance(record, dict):
        return False
    allowed = {item.name for item in fields(PerformanceSnapshot)}
    if set(record) - allowed:
        return False
    nested = {
        "render_blocking_resources": RenderBlockingResource,
        "image_opportunities": ImageOpportunity,
        "third_party_entities": ThirdPartyEntity,
        "font_display_issues": FontIssue,
        "layout_shift_elements": LayoutShiftElement,
    }
    for key, model in nested.items():
        if key not in record:
            continue
        rows = record[key]
        model_fields = {item.name for item in fields(model)}
        if (not isinstance(rows, list) or any(
            not isinstance(row, dict) or set(row) - model_fields for row in rows
        )):
            return False
    return True


class _ReplayPageSpeedProvider:
    name = "PageSpeed API"
    aliases = {"PageSpeed API"}

    def __init__(self, evidence: dict):
        rows = evidence.get("snapshots") if isinstance(evidence, dict) else []
        snapshots = [_performance_snapshot(row) for row in (rows or [])
                     if isinstance(row, dict)]
        self._cache = {
            (snapshot.url.rstrip("/").lower(), snapshot.strategy): snapshot
            for snapshot in snapshots
        }
        strategy = str(evidence.get("strategy") or "mobile")
        self._strategies = [strategy]
        self._sample_limit = max(1, len(snapshots))

    def is_available(self) -> bool:
        return bool(self._cache)

    def clear_cache(self) -> None:
        # Replay cache is immutable audit evidence, not a cross-audit live cache.
        return None

    def get_snapshot(self, url: str, strategy: str = "mobile"):
        return self._cache.get((url.rstrip("/").lower(), strategy))


class _ReplayEvidenceProvider:
    def __init__(self, key: str, payload: dict):
        self.key = key
        self.payload = payload
        self.name, self.aliases = _PROVIDER_RUNTIME[key]

    def is_available(self) -> bool:
        return True

    def collect(self, site_ctx, page_contexts, shared_data: dict) -> bool:
        shared_data[self.key] = self.payload
        if self.key == "gsc":
            by_url: dict[str, list[dict]] = {}
            for row in self.payload.get("current_rows") or []:
                if isinstance(row, dict) and row.get("page"):
                    by_url.setdefault(row["page"], []).append(row)
            inspections = self.payload.get("inspections") or {}
            for page in page_contexts:
                page.gsc_data = {
                    "current_rows": by_url.get(page.url, []),
                    "inspection": inspections.get(page.url),
                }
        elif self.key == "wordpress_privileged":
            site_ctx.site_profile = "wordpress"
        return True


def build_replay_providers(document: dict) -> dict:
    """Build offline-only providers from validated normalized evidence."""
    validate_replay_document(document)
    evidence = document["provider_evidence"]
    providers = {}
    pagespeed = evidence.get("pagespeed")
    if isinstance(pagespeed, dict) and pagespeed.get("status") == "CHECKED":
        provider = _ReplayPageSpeedProvider(pagespeed)
        if provider.is_available():
            providers[provider.name] = provider
    statuses = evidence.get("provider_status") or {}
    for key in _PROVIDER_DATA_FIELDS:
        record = evidence.get(key)
        if statuses.get(key) != "CHECKED" or not isinstance(record, dict):
            continue
        payload = record.get("data")
        if (record.get("collection_success") is True and isinstance(payload, dict)
                and _provider_has_evidence(key, payload, collection_success=True)):
            provider = _ReplayEvidenceProvider(key, payload)
            providers[provider.name] = provider
    return providers


def replay_pipeline_inputs(document: dict) -> tuple[dict, dict]:
    """Map a validated replay document back to current pipeline input shapes."""
    validate_replay_document(document)
    export_data = {
        "site_check": document["site_data"],
        "pages": document["pages"],
        "links": document["links"],
        "completeness": document["crawl_completeness"],
        "sitemap_reconciliation": document["sitemap_reconciliation"],
    }
    evidence = document["provider_evidence"]
    existing_data = {"replay_provider_evidence": evidence}
    statuses = evidence.get("provider_status") or {}
    for key in _PROVIDER_DATA_FIELDS:
        record = evidence.get(key)
        if statuses.get(key) == "CHECKED" and isinstance(record, dict):
            payload = record.get("data")
            if isinstance(payload, dict):
                existing_data[key] = payload
    return export_data, existing_data


def run_replay_pipeline(document: dict):
    """Execute the real RuleRunner without network or credential access."""
    from audit_rules.registry import load_registry
    from audit_rules.runner import RuleRunner

    export_data, existing_data = replay_pipeline_inputs(document)
    runner = RuleRunner(load_registry(), providers=build_replay_providers(document))
    return runner.run_from_export(
        export_data, base_url=document["source_url"], existing_data=existing_data)


def _contains_credentials(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            _is_sensitive_key(key) or _contains_credentials(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_credentials(item) for item in value)
    if isinstance(value, str):
        return _string_contains_credential(value)
    return False


def validate_replay_document(
    document: dict,
    *,
    expected_source_url: str = "",
    expected_completed_pages: int | None = None,
) -> ReplayValidationResult:
    """Validate the minimum supported replay v1 integrity contract."""
    if document.get("schema_version") != SCHEMA_VERSION:
        raise ReplayValidationError("unsupported schema_version")
    if document.get("artifact_type") != ARTIFACT_TYPE:
        raise ReplayValidationError("unsupported artifact_type")
    if expected_source_url and document.get("source_url") != expected_source_url:
        raise ReplayValidationError("source_url mismatch")
    for field in REQUIRED_OBJECT_FIELDS:
        if not isinstance(document.get(field), dict):
            raise ReplayValidationError(f"missing replay object: {field}")
    for field in REQUIRED_LIST_FIELDS:
        if not isinstance(document.get(field), list):
            raise ReplayValidationError(f"missing replay collection: {field}")
    crawl_metadata = document["crawl_metadata"]
    missing_metadata = sorted(REQUIRED_CRAWL_METADATA_FIELDS - crawl_metadata.keys())
    if missing_metadata:
        raise ReplayValidationError("missing crawl_metadata fields")
    pages = document.get("pages")
    links = document.get("links")
    counts = document.get("counts")
    if counts.get("pages") != len(pages) or counts.get("links") != len(links):
        raise ReplayValidationError("replay count mismatch")
    allowed_page_fields = REPLAY_PAGE_FIELDS | {"response_headers"}
    for page in pages:
        if not isinstance(page, dict) or set(page) - allowed_page_fields:
            raise ReplayValidationError("page field outside replay allowlist")
        headers = page.get("response_headers", {})
        if not isinstance(headers, dict) or any(
            str(name).lower() not in SAFE_RESPONSE_HEADERS for name in headers
        ):
            raise ReplayValidationError("response header outside replay allowlist")
        details = page.get("links_detailed", [])
        if not isinstance(details, list) or any(
            not isinstance(item, dict) or set(item) - REPLAY_PAGE_LINK_FIELDS
            for item in details
        ):
            raise ReplayValidationError("page link field outside replay allowlist")
    for link in links:
        if not isinstance(link, dict) or set(link) - REPLAY_LINK_FIELDS:
            raise ReplayValidationError("link field outside replay allowlist")
    if _contains_credentials(document):
        raise ReplayValidationError("credential-like replay data detected")
    evidence = document["provider_evidence"]
    allowed_evidence = {"pagespeed", "provider_status"} | set(_PROVIDER_DATA_FIELDS)
    if set(evidence) - allowed_evidence:
        raise ReplayValidationError("provider evidence field outside replay allowlist")
    statuses = evidence.get("provider_status", {})
    if statuses and (not isinstance(statuses, dict)
                     or set(statuses) - set(_PROVIDER_DATA_FIELDS)):
        raise ReplayValidationError("provider status field outside replay allowlist")
    valid_statuses = {
        "CHECKED", "UNAVAILABLE", "LIVE_VALIDATION_PENDING", "NOT_CHECKED",
    }
    if any(status not in valid_statuses for status in statuses.values()):
        raise ReplayValidationError("provider status is invalid")
    for name in _PROVIDER_DATA_FIELDS:
        record = evidence.get(name)
        if statuses.get(name) == "CHECKED" and record is None:
            raise ReplayValidationError("provider status lacks replay evidence")
        if record is None:
            continue
        if (statuses.get(name) != "CHECKED" or not isinstance(record, dict)
                or set(record) - {"status", "collection_success", "data"}
                or record.get("status") != "CHECKED"
                or record.get("collection_success") is not True
                or not isinstance(record.get("data"), dict)
                or set(record["data"]) - _PROVIDER_DATA_FIELDS[name]
                or not _provider_has_evidence(
                    name, record["data"], collection_success=True)):
            raise ReplayValidationError("provider evidence field outside replay allowlist")
    pagespeed = evidence.get("pagespeed")
    if pagespeed is not None:
        if not isinstance(pagespeed, dict) or set(pagespeed) - {
            "status", "strategy", "snapshots", "collected_at"
        } or not isinstance(pagespeed.get("snapshots"), list) or any(
            not _valid_performance_snapshot_record(row)
            for row in pagespeed.get("snapshots", [])
        ):
            raise ReplayValidationError("pagespeed evidence field outside replay allowlist")
        psi_status = pagespeed.get("status")
        successful = any(
            row.get("psi_status") == "success" for row in pagespeed["snapshots"]
        )
        if (psi_status not in valid_statuses
                or (psi_status == "CHECKED") != successful):
            raise ReplayValidationError("pagespeed status does not match replay evidence")
    urls = [str(page.get("url") or "") for page in pages if isinstance(page, dict)]
    if len(urls) != len(pages) or any(not url for url in urls) or len(set(urls)) != len(urls):
        raise ReplayValidationError("page URLs must be non-empty and unique")
    if urls != sorted(urls):
        raise ReplayValidationError("pages are not in stable URL order")
    completeness = document["crawl_completeness"]
    if completeness.get("audit_complete") is True:
        completed_pages = completeness.get("pages_crawled")
        if completed_pages != len(pages):
            raise ReplayValidationError("REPLAY_ARTIFACT_INCOMPLETE")
    if expected_completed_pages is not None and len(pages) != expected_completed_pages:
        raise ReplayValidationError("REPLAY_ARTIFACT_INCOMPLETE")
    return ReplayValidationResult(True, len(pages), len(links))


def load_replay_artifact(
    path: str | Path,
    *,
    expected_source_url: str = "",
    expected_completed_pages: int | None = None,
) -> dict:
    """Load and validate a gzip-compressed replay artifact."""
    source = Path(path)
    with gzip.open(source, "rt", encoding="utf-8") as stream:
        document = json.load(stream)
    validate_replay_document(
        document,
        expected_source_url=expected_source_url,
        expected_completed_pages=expected_completed_pages,
    )
    return document


def write_replay_artifact(
    document: dict,
    path: str | Path,
    *,
    expected_source_url: str = "",
    expected_completed_pages: int | None = None,
) -> ReplayValidationResult:
    """Write deterministic gzip bytes, reload them, and validate before return."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    with target.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            zipped.write(payload)
    loaded = load_replay_artifact(
        target,
        expected_source_url=expected_source_url,
        expected_completed_pages=expected_completed_pages,
    )
    return validate_replay_document(
        loaded,
        expected_source_url=expected_source_url,
        expected_completed_pages=expected_completed_pages,
    )
