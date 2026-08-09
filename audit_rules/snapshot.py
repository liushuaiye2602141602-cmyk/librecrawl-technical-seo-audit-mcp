"""Portable, versioned audit snapshot construction and persistence."""

from __future__ import annotations

from io import BytesIO
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from audit_rules.context import PageContext, SiteContext


SCHEMA_VERSION = 1
SNAPSHOT_FILENAME = "audit-snapshot-v1.json.gz"


class SnapshotValidationError(ValueError):
    """Raised when a snapshot does not satisfy the supported schema."""


_ROOT_REQUIRED_FIELDS = {
    "schema_version",
    "created_at",
    "base_url",
    "site_profile",
    "pages",
    "summary",
}

_PAGE_REQUIRED_FIELDS = {
    "url",
    "status",
    "indexable",
    "robots",
    "title",
    "meta_description",
    "h1",
    "canonical",
    "hreflang",
    "schema_fingerprint",
    "content_fingerprint",
    "internal_links",
    "technical_signals",
}


def build_snapshot(
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic v1 snapshot from normalized audit contexts."""
    created = created_at or datetime.now(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    pages = [
        _normalize_page(page)
        for page in sorted(page_contexts, key=lambda item: _normalize_url(item.url))
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": created,
        "base_url": _normalize_url(site_ctx.base_url),
        "site_profile": site_ctx.site_profile,
        "pages": pages,
        "summary": {
            "page_count": len(pages),
            "indexable_count": sum(1 for page in pages if page["indexable"]),
        },
    }


def build_snapshot_from_export(
    export_data: dict[str, Any],
    base_url: str = "",
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build a snapshot from existing LibreCrawl export data without refetching."""
    from audit_rules.providers.librecrawl_provider import LibreCrawlDataProvider

    provider = LibreCrawlDataProvider(
        export_data.get("pages") or [],
        export_data.get("site_check") or {},
        export_data.get("links") or [],
    )
    site_ctx, page_contexts = provider.create_contexts(
        base_url,
        export_data.get("completeness"),
    )
    return build_snapshot(site_ctx, page_contexts, created_at=created_at)


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    """Validate the supported v1 contract while allowing additive fields."""
    if not isinstance(snapshot, dict):
        raise SnapshotValidationError("Snapshot root must be an object")

    version = snapshot.get("schema_version")
    if version != SCHEMA_VERSION:
        raise SnapshotValidationError(
            f"Unsupported snapshot schema version: {version}"
        )

    missing_root = sorted(_ROOT_REQUIRED_FIELDS - snapshot.keys())
    if missing_root:
        raise SnapshotValidationError(
            f"Snapshot missing required fields: {', '.join(missing_root)}"
        )

    pages = snapshot.get("pages")
    if not isinstance(pages, list):
        raise SnapshotValidationError("Snapshot pages must be a list")

    seen_urls: set[str] = set()
    for index, page in enumerate(pages):
        if not isinstance(page, dict):
            raise SnapshotValidationError(f"Snapshot page {index} must be an object")
        missing_page = sorted(_PAGE_REQUIRED_FIELDS - page.keys())
        if missing_page:
            raise SnapshotValidationError(
                f"Snapshot page {index} missing required fields: "
                f"{', '.join(missing_page)}"
            )
        url = page.get("url")
        if not isinstance(url, str) or not url:
            raise SnapshotValidationError(
                f"Snapshot page {index} URL must be a non-empty string"
            )
        if url in seen_urls:
            raise SnapshotValidationError(f"Snapshot contains duplicate URL: {url}")
        seen_urls.add(url)
        status = page.get("status")
        if isinstance(status, bool) or not isinstance(status, int):
            raise SnapshotValidationError(
                f"Snapshot page {url} status must be an integer"
            )
        if not isinstance(page.get("indexable"), bool):
            raise SnapshotValidationError(
                f"Snapshot page {url} indexable must be a boolean"
            )


def write_snapshot(snapshot: dict[str, Any], path: str | Path) -> Path:
    """Validate and write a deterministic gzip-compressed JSON snapshot."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(snapshot_to_gzip_bytes(snapshot))
    return target


def load_snapshot(path: str | Path) -> dict[str, Any]:
    """Load and validate a v1 gzip snapshot, preserving additive fields."""
    source = Path(path)
    try:
        snapshot = _decode_snapshot(source.read_bytes())
        validate_snapshot(snapshot)
        return snapshot
    except SnapshotValidationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError) as exc:
        raise SnapshotValidationError(
            f"Unable to load snapshot {source}: {exc}"
        ) from exc


def snapshot_to_gzip_bytes(snapshot: dict[str, Any]) -> bytes:
    """Validate and encode a snapshot as deterministic gzip-compressed JSON."""
    validate_snapshot(snapshot)
    return _encode_snapshot(snapshot)


def snapshot_from_gzip_bytes(payload: bytes) -> dict[str, Any]:
    """Decode and validate an in-memory gzip snapshot payload."""
    try:
        snapshot = _decode_snapshot(payload)
        validate_snapshot(snapshot)
        return snapshot
    except SnapshotValidationError:
        raise
    except (OSError, EOFError, UnicodeError, json.JSONDecodeError, TypeError) as exc:
        raise SnapshotValidationError(
            f"Unable to decode snapshot bytes: {exc}"
        ) from exc


def _normalize_page(ctx: PageContext) -> dict[str, Any]:
    robots = _normalize_text(ctx.robots).lower()
    hreflang = sorted(
        (
            {
                "lang": _normalize_text(item.get("lang")).lower(),
                "url": _normalize_url(item.get("url")),
            }
            for item in (ctx.hreflang_summary or [])
            if isinstance(item, dict)
        ),
        key=lambda item: (item["lang"], item["url"]),
    )
    schema_types = sorted(
        _normalize_text(schema_type)
        for schema_type in (ctx.json_ld_types or [])
        if _normalize_text(schema_type)
    )
    internal_targets = sorted(
        {
            _normalize_url(link.get("url"))
            for link in (ctx.links_detailed or [])
            if isinstance(link, dict)
            and link.get("is_internal", True)
            and _normalize_url(link.get("url"))
        }
    )
    content_source = ctx.content_hash or ctx.body_text or {
        "title": _normalize_text(ctx.title),
        "meta_description": _normalize_text(ctx.meta_description),
        "h1": _normalize_text(ctx.h1),
        "word_count": ctx.word_count,
    }
    return {
        "url": _normalize_url(ctx.url),
        "status": int(ctx.status_code),
        "indexable": 200 <= int(ctx.status_code) < 300 and "noindex" not in robots,
        "robots": robots,
        "title": _normalize_text(ctx.title),
        "meta_description": _normalize_text(ctx.meta_description),
        "h1": _normalize_text(ctx.h1),
        "canonical": _normalize_url(ctx.canonical_url),
        "hreflang": hreflang,
        "schema_fingerprint": _fingerprint(schema_types),
        "content_fingerprint": _fingerprint(content_source),
        "internal_links": {
            "inbound_count": int(ctx.linked_from_count),
            "outbound_count": int(ctx.internal_links_count),
            "target_count": len(internal_targets),
            "targets_fingerprint": _fingerprint(internal_targets),
        },
        "technical_signals": {
            "lang": _normalize_text(ctx.lang).lower(),
            "viewport": _normalize_text(ctx.viewport),
            "word_count": int(ctx.word_count),
            "response_time_ms": int(ctx.response_time_ms),
        },
    }


def _fingerprint(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _encode_snapshot(snapshot: dict[str, Any]) -> bytes:
    payload = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    buffer = BytesIO()
    with gzip.GzipFile(
        filename="",
        mode="wb",
        fileobj=buffer,
        mtime=0,
    ) as compressed:
        compressed.write(payload)
    return buffer.getvalue()


def _decode_snapshot(payload: bytes) -> dict[str, Any]:
    with gzip.GzipFile(fileobj=BytesIO(payload), mode="rb") as compressed:
        data = compressed.read()
    decoded = json.loads(data.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise SnapshotValidationError("Snapshot root must be an object")
    return decoded


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _normalize_url(value: object) -> str:
    raw = _normalize_text(value)
    if not raw:
        return ""
    parts = urlsplit(raw)
    if not parts.scheme or not parts.netloc:
        return raw.split("#", 1)[0]
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    if scheme == "http" and netloc.endswith(":80"):
        netloc = netloc[:-3]
    elif scheme == "https" and netloc.endswith(":443"):
        netloc = netloc[:-4]
    path = "" if parts.path in ("", "/") else parts.path
    return urlunsplit((scheme, netloc, path, parts.query, ""))
