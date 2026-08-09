"""Deterministic, URL-indexed comparison of portable audit snapshots."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import io
import json
from pathlib import Path
from typing import Any

from audit_rules.snapshot import validate_snapshot


CRAWL_DIFF_COLUMNS = [
    "url",
    "change_type",
    "classification",
    "field",
    "before",
    "after",
    "evidence",
]

_FIELD_CHANGE_TYPES = {
    "status": "STATUS_CHANGED",
    "indexable": "INDEXABILITY_CHANGED",
    "robots": "ROBOTS_CHANGED",
    "canonical": "CANONICAL_CHANGED",
    "title": "TITLE_CHANGED",
    "meta_description": "DESCRIPTION_CHANGED",
    "h1": "H1_CHANGED",
    "hreflang": "HREFLANG_CHANGED",
    "schema_fingerprint": "SCHEMA_CHANGED",
    "content_fingerprint": "CONTENT_CHANGED",
}

_METADATA_FIELDS = {
    "canonical",
    "title",
    "meta_description",
    "h1",
    "hreflang",
}


@dataclass(frozen=True)
class SnapshotChange:
    """One structured difference between before and after snapshots."""

    url: str
    change_type: str
    classification: str
    field: str
    before: object
    after: object
    evidence: str

    def to_dict(self) -> dict[str, str]:
        return {
            "url": self.url,
            "change_type": self.change_type,
            "classification": self.classification,
            "field": self.field,
            "before": _serialize_value(self.before),
            "after": _serialize_value(self.after),
            "evidence": self.evidence,
        }


def diff_snapshots(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    include_unchanged: bool = False,
) -> list[SnapshotChange]:
    """Compare two validated snapshots in O(pages + emitted changes)."""
    validate_snapshot(before)
    validate_snapshot(after)
    before_by_url = {page["url"]: page for page in before["pages"]}
    after_by_url = {page["url"]: page for page in after["pages"]}

    changes: list[SnapshotChange] = []
    for url in sorted(before_by_url.keys() | after_by_url.keys()):
        before_page = before_by_url.get(url)
        after_page = after_by_url.get(url)

        if before_page is None:
            changes.append(
                _make_change(
                    url,
                    "URL_ADDED",
                    "INFORMATIONAL_CHANGE",
                    "url",
                    None,
                    url,
                )
            )
            continue

        if after_page is None:
            classification = (
                "REGRESSED"
                if before_page["indexable"]
                else "INFORMATIONAL_CHANGE"
            )
            changes.append(
                _make_change(
                    url,
                    "URL_REMOVED",
                    classification,
                    "url",
                    url,
                    None,
                )
            )
            continue

        page_changes = _diff_page(url, before_page, after_page)
        if page_changes:
            changes.extend(page_changes)
        elif include_unchanged:
            changes.append(
                _make_change(
                    url,
                    "PAGE_UNCHANGED",
                    "UNCHANGED",
                    "page",
                    before_page,
                    after_page,
                )
            )

    return sorted(changes, key=lambda item: (item.url, item.change_type, item.field))


def crawl_diff_csv_to_string(changes: list[SnapshotChange]) -> str:
    """Serialize changes to the canonical crawl-diff.csv representation."""
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=CRAWL_DIFF_COLUMNS,
        lineterminator="\n",
    )
    writer.writeheader()
    for change in sorted(
        changes,
        key=lambda item: (item.url, item.change_type, item.field),
    ):
        writer.writerow(change.to_dict())
    return buffer.getvalue()


def write_crawl_diff_csv(
    changes: list[SnapshotChange],
    path: str | Path,
) -> Path:
    """Write a UTF-8 crawl diff artifact and return its path."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(crawl_diff_csv_to_string(changes), encoding="utf-8", newline="")
    return target


def _diff_page(
    url: str,
    before: dict[str, Any],
    after: dict[str, Any],
) -> list[SnapshotChange]:
    changes: list[SnapshotChange] = []
    for field, change_type in _FIELD_CHANGE_TYPES.items():
        before_value = before[field]
        after_value = after[field]
        if before_value == after_value:
            continue
        changes.append(
            _make_change(
                url,
                change_type,
                _classify_field(field, before_value, after_value),
                field,
                before_value,
                after_value,
            )
        )

    before_links = before["internal_links"]
    after_links = after["internal_links"]
    before_inbound = int(before_links.get("inbound_count", 0))
    after_inbound = int(after_links.get("inbound_count", 0))
    lost_all_inbound = before_inbound > 0 and after_inbound == 0
    lost_majority = before_inbound >= 4 and after_inbound * 2 < before_inbound
    if lost_all_inbound or lost_majority:
        changes.append(
            _make_change(
                url,
                "INTERNAL_LINK_REGRESSION",
                "REGRESSED",
                "internal_links.inbound_count",
                before_inbound,
                after_inbound,
            )
        )
    return changes


def _classify_field(field: str, before: object, after: object) -> str:
    if field == "status":
        before_good = isinstance(before, int) and 200 <= before < 300
        after_good = isinstance(after, int) and 200 <= after < 300
        if before_good and not after_good:
            return "REGRESSED"
        if not before_good and after_good:
            return "FIXED"
        return "INFORMATIONAL_CHANGE"

    if field == "indexable":
        if before is True and after is False:
            return "REGRESSED"
        if before is False and after is True:
            return "FIXED"
        return "INFORMATIONAL_CHANGE"

    if field == "robots":
        before_noindex = "noindex" in str(before).lower()
        after_noindex = "noindex" in str(after).lower()
        if not before_noindex and after_noindex:
            return "REGRESSED"
        if before_noindex and not after_noindex:
            return "FIXED"
        return "INFORMATIONAL_CHANGE"

    if field in _METADATA_FIELDS:
        if _has_value(before) and not _has_value(after):
            return "NEW_ISSUE"
        if not _has_value(before) and _has_value(after):
            return "FIXED"

    return "INFORMATIONAL_CHANGE"


def _make_change(
    url: str,
    change_type: str,
    classification: str,
    field: str,
    before: object,
    after: object,
) -> SnapshotChange:
    before_text = _serialize_value(before)
    after_text = _serialize_value(after)
    return SnapshotChange(
        url=url,
        change_type=change_type,
        classification=classification,
        field=field,
        before=before,
        after=after,
        evidence=f"{field} changed: before={before_text}; after={after_text}",
    )


def _has_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _serialize_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
