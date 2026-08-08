"""Phase 2 — Structured Data Local Checks.

Pure functions using only existing LibreCrawl export data.
NO HTTP, NO external APIs.

Rules implemented:
  - Rule 10:  Breadcrumb (BreadcrumbList schema integrity + URL-path consistency)
  - Rule 28:  Schema Conflict (conflicting JSON-LD blocks with same @type)
  - Rule 78:  Schema vs Visible Content (JSON-LD compared with on-page metadata)
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Optional
from urllib.parse import urlparse

from audit_rules.models import RuleDefinition, Finding
from audit_rules.context import SiteContext, PageContext
from audit_rules.categories import Severity


# ============================================================
# Local helpers
# ============================================================

def _mk(
    rule: RuleDefinition,
    url: str,
    detected: str,
    expected: str,
    evidence: str,
    detail: str,
    severity: Severity,
    confidence: float = 1.0,
) -> Finding:
    """Create a Finding with explicit severity (overrides rule default)."""
    return Finding(
        audit_id=rule.audit_id,
        rule_id=rule.rule_id,
        url=url,
        category=rule.category.value,
        priority=str(rule.priority.value),
        severity=str(severity.value),
        finding_type=rule.default_finding_type,
        scope=str(rule.scope.value),
        detected_value=detected,
        expected_value=expected,
        evidence=evidence,
        finding_detail=detail or evidence,
        remediation=rule.remediation,
        owner=rule.owner,
        acceptance_criteria=rule.acceptance_criteria,
        data_source=rule.required_data_sources[0] if rule.required_data_sources else "LibreCrawl",
        confidence=confidence,
    )


def _get_json_ld(ctx: PageContext) -> list[dict]:
    """Extract the JSON-LD list from a PageContext's raw export."""
    raw = getattr(ctx, "_raw_export", None) or {}
    jld = raw.get("json_ld") or raw.get("structured_data") or []
    if isinstance(jld, list):
        return [item for item in jld if isinstance(item, dict)]
    return []


def _get_og_tags(ctx: PageContext) -> dict:
    """Extract og_tags dict from a PageContext's raw export."""
    raw = getattr(ctx, "_raw_export", None) or {}
    og = raw.get("og_tags") or {}
    if isinstance(og, dict):
        return og
    return {}


def _get_twitter_tags(ctx: PageContext) -> dict:
    """Extract twitter_tags dict from a PageContext's raw export."""
    raw = getattr(ctx, "_raw_export", None) or {}
    tw = raw.get("twitter_tags") or {}
    if isinstance(tw, dict):
        return tw
    return {}


def _normalize_text(value: str) -> str:
    """Normalize text: lowercase, collapse whitespace, strip."""
    if not value:
        return ""
    return " ".join(value.lower().strip().split())


def _normalize_path_segment(segment: str) -> str:
    """Normalize URL path segment: lowercase, replace hyphens/underscores with spaces."""
    if not segment:
        return ""
    s = segment.lower().strip()
    s = s.replace("-", " ").replace("_", " ")
    return " ".join(s.split())


def _texts_match(a: str, b: str) -> tuple[str, float]:
    """Compare two text values. Returns (match_type, confidence).

    match_type: "exact" | "normalized" | "different"
    """
    if not a and not b:
        return ("exact", 1.0)
    if not a or not b:
        return ("different", 0.0)

    if a.strip() == b.strip():
        return ("exact", 1.0)

    if _normalize_text(a) == _normalize_text(b):
        return ("normalized", 0.95)

    # Punctuation-only difference
    a_alpha = re.sub(r"[^\w\s]", "", a).strip()
    b_alpha = re.sub(r"[^\w\s]", "", b).strip()
    if a_alpha and b_alpha and _normalize_text(a_alpha) == _normalize_text(b_alpha):
        return ("normalized", 0.85)

    return ("different", 0.0)


# ============================================================
# Rule 10 — Breadcrumb
# ============================================================

def check_breadcrumb(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 10: Validate BreadcrumbList JSON-LD schema and URL-path consistency.

    Checks:
      - itemListElement exists and has >= 2 items
      - First item matches site root (no URL or root URL)
      - Last item has no URL or matches the current page URL
      - Position numbering is sequential (1, 2, 3, ...)
      - Breadcrumb item names match URL path segments (OPPORTUNITY on mismatch)

    Pages without BreadcrumbList schema are NOT flagged (it is optional).
    """
    findings: list[Finding] = []
    base_url = (site_ctx.base_url or "").rstrip("/")

    for ctx in page_contexts:
        if ctx.status_code != 200:
            continue

        json_ld = _get_json_ld(ctx)
        breadcrumbs = [
            bl for bl in json_ld
            if isinstance(bl, dict) and bl.get("@type") == "BreadcrumbList"
        ]

        if not breadcrumbs:
            continue  # Optional schema — no finding

        page_url = ctx.url or ""
        parsed_page = urlparse(page_url)
        path_segments_raw = [s for s in (parsed_page.path or "/").split("/") if s]
        path_segments_norm = [_normalize_path_segment(s) for s in path_segments_raw]

        for bc_block in breadcrumbs:
            block_id = bc_block.get("@id", "no-id")

            # --- itemListElement check ---
            item_list = bc_block.get("itemListElement")
            if not isinstance(item_list, list) or len(item_list) == 0:
                findings.append(_mk(
                    rule, url=page_url,
                    detected="BreadcrumbList has no itemListElement array",
                    expected="itemListElement with 2+ items",
                    evidence=f"@id={block_id}, @type=BreadcrumbList",
                    detail="BreadcrumbList schema is missing itemListElement — "
                           "Google may not display breadcrumbs in search results.",
                    severity=Severity.WARNING,
                ))
                continue

            item_count = len(item_list)

            if item_count < 2:
                findings.append(_mk(
                    rule, url=page_url,
                    detected=f"Only {item_count} breadcrumb item(s)",
                    expected="At least 2 breadcrumb items",
                    evidence=f"@id={block_id}, itemListElement count={item_count}",
                    detail=f"BreadcrumbList has only {item_count} item(s) — "
                           "Google requires at least 2 items for breadcrumb rich results.",
                    severity=Severity.WARNING,
                ))

            # --- Position numbering check ---
            positions = []
            for item in item_list:
                if isinstance(item, dict):
                    pos = item.get("position")
                    if pos is not None:
                        try:
                            positions.append(int(pos))
                        except (ValueError, TypeError):
                            positions.append(None)
                    else:
                        positions.append(None)
                else:
                    positions.append(None)

            expected_positions = list(range(1, item_count + 1))
            if positions != expected_positions:
                findings.append(_mk(
                    rule, url=page_url,
                    detected=f"Position numbering: {positions}",
                    expected=f"Sequential 1-{item_count}: {expected_positions}",
                    evidence=f"@id={block_id}, positions={positions}",
                    detail="Breadcrumb position numbering is broken — "
                           "Google uses position to order breadcrumb trail items.",
                    severity=Severity.WARNING,
                ))

            # --- First and last item URL checks ---
            first_item = item_list[0] if isinstance(item_list[0], dict) else {}
            last_item = item_list[-1] if isinstance(item_list[-1], dict) else {}

            # First item: no URL or matches site root
            first_url = (
                first_item.get("item")
                or first_item.get("id")
                or first_item.get("url")
                or ""
            ).strip()
            if first_url:
                first_url_norm = first_url.rstrip("/")
                if base_url and first_url_norm != base_url:
                    findings.append(_mk(
                        rule, url=page_url,
                        detected=f"First breadcrumb item URL: {first_url}",
                        expected=f"Site root: {base_url} or omit URL",
                        evidence=f"@id={block_id}, first_item.item={first_url}",
                        detail=f"First breadcrumb item points to '{first_url}' "
                               "instead of the site root. Google expects the first "
                               "breadcrumb to represent the home page.",
                        severity=Severity.WARNING,
                    ))

            # Last item: no URL or matches current page
            last_url = (
                last_item.get("item")
                or last_item.get("id")
                or last_item.get("url")
                or ""
            ).strip()
            if last_url:
                last_url_norm = last_url.rstrip("/")
                page_url_norm = page_url.rstrip("/")
                if last_url_norm != page_url_norm:
                    findings.append(_mk(
                        rule, url=page_url,
                        detected=f"Last breadcrumb item URL: {last_url}",
                        expected=f"Current page: {page_url} or omit URL",
                        evidence=f"@id={block_id}, last_item.item={last_url}",
                        detail="Last breadcrumb item should link to the current "
                               "page (or have no URL) — the current page in a "
                               "breadcrumb trail should be self-referencing.",
                        severity=Severity.WARNING,
                    ))

            # --- Extract breadcrumb item names ---
            bc_names = []
            for item in item_list:
                if isinstance(item, dict):
                    name = item.get("name")
                    if not name and isinstance(item.get("item"), dict):
                        name = item["item"].get("name")
                    bc_names.append(str(name).strip() if name else "")
                else:
                    bc_names.append("")

            # --- URL-path consistency ---
            # breadcrumb[0] = "Home" → root (no path segment)
            # breadcrumb[i>0] should match path_segment[i-1]
            for i, bc_name in enumerate(bc_names):
                if i == 0:
                    continue  # Skip "Home" / root item
                if not bc_name:
                    continue

                path_idx = i - 1
                if path_idx >= len(path_segments_norm):
                    break

                bc_norm = _normalize_text(bc_name)
                path_norm = path_segments_norm[path_idx]
                if not bc_norm or not path_norm:
                    continue

                # Direct match or word-level overlap
                bc_words = set(bc_norm.split())
                path_words = set(path_norm.split())
                overlap = bc_words & path_words

                if bc_norm != path_norm and not overlap:
                    findings.append(_mk(
                        rule, url=page_url,
                        detected=(
                            f"Breadcrumb #{i + 1} name: '{bc_name}' vs "
                            f"URL path segment: '{path_segments_raw[path_idx]}'"
                        ),
                        expected="Breadcrumb names should correspond to URL path segments",
                        evidence=(
                            f"@id={block_id}, "
                            f"bc[{i}]='{bc_name}', "
                            f"path[{path_idx}]='{path_segments_raw[path_idx]}'"
                        ),
                        detail=(
                            f"Breadcrumb item '{bc_name}' does not match URL path "
                            f"segment '{path_segments_raw[path_idx]}' — inconsistent "
                            "navigation hierarchy may confuse search engines."
                        ),
                        severity=Severity.OPPORTUNITY,
                    ))

    return findings


# ============================================================
# Rule 28 — Schema Conflict
# ============================================================

def check_schema_conflict(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 28: Detect conflicting JSON-LD blocks with the same @type.

    Multiple entities of the same @type are LEGAL — only flag when key
    properties CONFLICT (different values) across different @id blocks.
    This is about conflicting information, not duplicate entity counts.

    Checks:
      - Organization: name, url, logo, sameAs conflicts
      - Product:      name, sku, brand conflicts
      - Breadcrumb:   different itemCount, different item names
      - WebSite:      name, url, potentialAction conflicts
    """
    findings: list[Finding] = []

    # Collect all JSON-LD blocks grouped by @type
    type_to_blocks: dict[str, list[tuple[str, dict, str]]] = defaultdict(list)

    for ctx in page_contexts:
        if ctx.status_code != 200:
            continue
        json_ld = _get_json_ld(ctx)
        for block in json_ld:
            at_type = block.get("@type", "")
            if isinstance(at_type, list):
                for t in at_type:
                    if isinstance(t, str) and t.strip():
                        bid = block.get("@id", "no-id")
                        type_to_blocks[t.strip()].append((ctx.url, block, bid))
            elif isinstance(at_type, str) and at_type.strip():
                bid = block.get("@id", "no-id")
                type_to_blocks[at_type.strip()].append((ctx.url, block, bid))

    # Run conflict detection per type
    _check_organization_conflicts(rule, type_to_blocks, findings)
    _check_product_conflicts(rule, type_to_blocks, findings)
    _check_breadcrumb_conflicts(rule, type_to_blocks, findings)
    _check_website_conflicts(rule, type_to_blocks, findings)

    return findings


# -- Organization conflict detection --

def _check_organization_conflicts(
    rule: RuleDefinition,
    type_to_blocks: dict[str, list[tuple[str, dict, str]]],
    findings: list[Finding],
) -> None:
    """Flag conflicting Organization JSON-LD blocks."""
    org_blocks = type_to_blocks.get("Organization", [])
    if len(org_blocks) < 2:
        return

    id_groups: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for url, block, bid in org_blocks:
        id_groups[bid].append((url, block))

    valid_ids = [uid for uid in id_groups if uid and uid != "no-id"]
    if len(valid_ids) < 2:
        return

    org_key_props = ["name", "url", "logo", "sameAs"]

    for i in range(len(valid_ids)):
        for j in range(i + 1, len(valid_ids)):
            id_a = valid_ids[i]
            id_b = valid_ids[j]
            blocks_a = id_groups[id_a]
            blocks_b = id_groups[id_b]

            for prop in org_key_props:
                vals_a = _collect_prop_values(blocks_a, prop)
                vals_b = _collect_prop_values(blocks_b, prop)

                if not vals_a or not vals_b:
                    continue

                for va in vals_a:
                    for vb in vals_b:
                        mtype, _ = _texts_match(va, vb)
                        if mtype == "different":
                            url_a = blocks_a[0][0]
                            sev = Severity.ERROR if prop in ("name", "url") else Severity.WARNING
                            findings.append(_mk(
                                rule, url=url_a,
                                detected=(
                                    f"Conflicting Organization '{prop}': "
                                    f"'{va}' vs '{vb}'"
                                ),
                                expected=(
                                    f"Consistent '{prop}' across Organization "
                                    "blocks, or merge into single @id"
                                ),
                                evidence=(
                                    f"entity_type=Organization, property={prop}, "
                                    f"value_a={va}, value_b={vb}, "
                                    f"block_ids=[{id_a}, {id_b}]"
                                ),
                                detail=(
                                    f"Two Organization blocks (@id={id_a} and "
                                    f"@id={id_b}) have different '{prop}' values "
                                    f"('{va}' vs '{vb}'). "
                                    f"{'Google may display the wrong organization name or URL in knowledge panels.' if prop in ('name', 'url') else 'Inconsistent organization metadata may confuse search engines.'}"
                                ),
                                severity=sev,
                            ))
                            break  # One conflict per property pair


# -- Product conflict detection --

def _check_product_conflicts(
    rule: RuleDefinition,
    type_to_blocks: dict[str, list[tuple[str, dict, str]]],
    findings: list[Finding],
) -> None:
    """Flag conflicting Product JSON-LD blocks."""
    product_blocks = type_to_blocks.get("Product", [])
    if len(product_blocks) < 2:
        return

    id_groups: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for url, block, bid in product_blocks:
        id_groups[bid].append((url, block))

    valid_ids = [uid for uid in id_groups if uid and uid != "no-id"]
    if len(valid_ids) < 2:
        return

    product_key_props = ["name", "sku", "brand"]

    for i in range(len(valid_ids)):
        for j in range(i + 1, len(valid_ids)):
            id_a = valid_ids[i]
            id_b = valid_ids[j]
            blocks_a = id_groups[id_a]
            blocks_b = id_groups[id_b]

            for prop in product_key_props:
                vals_a = _collect_prop_values(blocks_a, prop)
                vals_b = _collect_prop_values(blocks_b, prop)

                if not vals_a or not vals_b:
                    continue

                for va in vals_a:
                    for vb in vals_b:
                        mtype, _ = _texts_match(va, vb)
                        if mtype == "different":
                            url_a = blocks_a[0][0]
                            findings.append(_mk(
                                rule, url=url_a,
                                detected=(
                                    f"Conflicting Product '{prop}': "
                                    f"'{va}' vs '{vb}'"
                                ),
                                expected=(
                                    f"Consistent '{prop}' across Product blocks, "
                                    "or use separate @id for distinct products"
                                ),
                                evidence=(
                                    f"entity_type=Product, property={prop}, "
                                    f"value_a={va}, value_b={vb}, "
                                    f"block_ids=[{id_a}, {id_b}]"
                                ),
                                detail=(
                                    f"Two Product blocks (@id={id_a} and @id={id_b}) "
                                    f"have different '{prop}' values "
                                    f"('{va}' vs '{vb}'). "
                                    f"{'Conflicting SKU or brand data can cause Merchant Center disapprovals.' if prop in ('sku', 'brand') else 'Conflicting product names may cause Google to display incorrect product information in rich results.'}"
                                ),
                                severity=Severity.WARNING,
                            ))
                            break


# -- Breadcrumb conflict detection --

def _check_breadcrumb_conflicts(
    rule: RuleDefinition,
    type_to_blocks: dict[str, list[tuple[str, dict, str]]],
    findings: list[Finding],
) -> None:
    """Flag conflicting BreadcrumbList structure."""
    bc_blocks = type_to_blocks.get("BreadcrumbList", [])
    if len(bc_blocks) < 2:
        return

    id_groups: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for url, block, bid in bc_blocks:
        id_groups[bid].append((url, block))

    valid_ids = [uid for uid in id_groups if uid and uid != "no-id"]
    if len(valid_ids) < 2:
        return

    # Extract structure per @id
    structures: dict[str, dict] = {}
    for uid in valid_ids:
        blocks = id_groups[uid]
        for _, block in blocks:
            item_list = block.get("itemListElement", [])
            if isinstance(item_list, list):
                item_names = []
                for item in item_list:
                    if isinstance(item, dict):
                        name = item.get("name", "")
                        item_names.append(str(name).strip() if name else "")
                structures[uid] = {
                    "itemCount": len(item_list),
                    "item_names": item_names,
                }
                break  # First block determines structure for this @id

    ids_list = list(structures.keys())
    for i in range(len(ids_list)):
        for j in range(i + 1, len(ids_list)):
            id_a = ids_list[i]
            id_b = ids_list[j]
            sa = structures.get(id_a, {})
            sb = structures.get(id_b, {})

            if sa.get("itemCount") != sb.get("itemCount"):
                url_a = id_groups[id_a][0][0] if id_groups[id_a] else ""
                findings.append(_mk(
                    rule, url=url_a,
                    detected=(
                        f"Different itemCount: {sa.get('itemCount')} "
                        f"vs {sb.get('itemCount')}"
                    ),
                    expected="Consistent BreadcrumbList structure on a page",
                    evidence=(
                        f"entity_type=BreadcrumbList, property=itemCount, "
                        f"value_a={sa.get('itemCount')}, "
                        f"value_b={sb.get('itemCount')}, "
                        f"block_ids=[{id_a}, {id_b}]"
                    ),
                    detail=(
                        f"Two BreadcrumbList blocks on the same page have "
                        f"different item counts ({sa.get('itemCount')} vs "
                        f"{sb.get('itemCount')}) — inconsistent breadcrumb "
                        "structure may confuse Google."
                    ),
                    severity=Severity.WARNING,
                ))

            # Compare item names at same position
            names_a = sa.get("item_names", [])
            names_b = sb.get("item_names", [])
            for idx in range(min(len(names_a), len(names_b))):
                name_a = names_a[idx]
                name_b = names_b[idx]
                if name_a and name_b:
                    mtype, _ = _texts_match(name_a, name_b)
                    if mtype == "different":
                        url_a = id_groups[id_a][0][0] if id_groups[id_a] else ""
                        findings.append(_mk(
                            rule, url=url_a,
                            detected=(
                                f"Different item name at position {idx + 1}: "
                                f"'{name_a}' vs '{name_b}'"
                            ),
                            expected="Consistent breadcrumb item names",
                            evidence=(
                                f"entity_type=BreadcrumbList, "
                                f"property=itemListElement[{idx}].name, "
                                f"value_a={name_a}, value_b={name_b}, "
                                f"block_ids=[{id_a}, {id_b}]"
                            ),
                            detail=(
                                f"Two BreadcrumbList blocks use different names "
                                f"for position {idx + 1} ('{name_a}' vs "
                                f"'{name_b}') — Google may pick either one."
                            ),
                            severity=Severity.WARNING,
                        ))


# -- WebSite conflict detection --

def _check_website_conflicts(
    rule: RuleDefinition,
    type_to_blocks: dict[str, list[tuple[str, dict, str]]],
    findings: list[Finding],
) -> None:
    """Flag conflicting WebSite JSON-LD blocks."""
    ws_blocks = type_to_blocks.get("WebSite", [])
    if len(ws_blocks) < 2:
        return

    id_groups: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for url, block, bid in ws_blocks:
        id_groups[bid].append((url, block))

    valid_ids = [uid for uid in id_groups if uid and uid != "no-id"]
    if len(valid_ids) < 2:
        return

    website_key_props = ["name", "url"]

    for i in range(len(valid_ids)):
        for j in range(i + 1, len(valid_ids)):
            id_a = valid_ids[i]
            id_b = valid_ids[j]
            blocks_a = id_groups[id_a]
            blocks_b = id_groups[id_b]

            for prop in website_key_props:
                vals_a = _collect_prop_values(blocks_a, prop)
                vals_b = _collect_prop_values(blocks_b, prop)

                if not vals_a or not vals_b:
                    continue

                for va in vals_a:
                    for vb in vals_b:
                        mtype, _ = _texts_match(va, vb)
                        if mtype == "different":
                            url_a = blocks_a[0][0]
                            findings.append(_mk(
                                rule, url=url_a,
                                detected=(
                                    f"Conflicting WebSite '{prop}': "
                                    f"'{va}' vs '{vb}'"
                                ),
                                expected=f"Consistent '{prop}' across WebSite blocks",
                                evidence=(
                                    f"entity_type=WebSite, property={prop}, "
                                    f"value_a={va}, value_b={vb}, "
                                    f"block_ids=[{id_a}, {id_b}]"
                                ),
                                detail=(
                                    f"Two WebSite blocks (@id={id_a} and @id={id_b}) "
                                    f"have different '{prop}' values — Sitelinks "
                                    "search box may not work correctly."
                                ),
                                severity=Severity.WARNING,
                            ))
                            break

    # Compare potentialAction (Sitelinks SearchBox)
    actions_by_id: dict[str, str] = {}
    for uid in valid_ids:
        blocks = id_groups[uid]
        for _, block in blocks:
            pa = block.get("potentialAction")
            if isinstance(pa, dict):
                target = pa.get("target", {})
                if isinstance(target, dict):
                    entry = target.get("urlTemplate", "")
                    if entry:
                        actions_by_id[uid] = str(entry)
                        break

    ids_with_actions = list(actions_by_id.keys())
    for i in range(len(ids_with_actions)):
        for j in range(i + 1, len(ids_with_actions)):
            id_a = ids_with_actions[i]
            id_b = ids_with_actions[j]
            if actions_by_id[id_a] != actions_by_id[id_b]:
                url_a = id_groups[id_a][0][0] if id_groups[id_a] else ""
                findings.append(_mk(
                    rule, url=url_a,
                    detected=(
                        f"Conflicting WebSite potentialAction: "
                        f"'{actions_by_id[id_a]}' vs '{actions_by_id[id_b]}'"
                    ),
                    expected="Consistent Sitelinks SearchBox configuration",
                    evidence=(
                        f"entity_type=WebSite, "
                        f"property=potentialAction.target.urlTemplate, "
                        f"value_a={actions_by_id[id_a]}, "
                        f"value_b={actions_by_id[id_b]}, "
                        f"block_ids=[{id_a}, {id_b}]"
                    ),
                    detail=(
                        "Conflicting potentialAction in WebSite schema — "
                        "Sitelinks SearchBox may use the wrong search URL."
                    ),
                    severity=Severity.WARNING,
                ))


# -- Shared helpers for conflict detection --

def _collect_prop_values(blocks: list[tuple[str, dict]], prop: str) -> set[str]:
    """Collect non-empty string values for a property from a list of blocks."""
    values: set[str] = set()
    for _, block in blocks:
        v = _extract_prop_value(block, prop)
        if v:
            values.add(v)
    return values


def _extract_prop_value(block: dict, prop: str) -> str:
    """Extract a scalar string value from a JSON-LD block property.

    Handles nested objects (e.g. brand → {"@type": "Brand", "name": "Apple"}),
    lists, and numeric values.
    """
    val = block.get(prop)
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, dict):
        return str(val.get("name", val.get("url", ""))).strip()
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, list) and len(val) > 0:
        first = val[0]
        if isinstance(first, str):
            return first.strip()
        if isinstance(first, dict):
            return str(first.get("name", first.get("url", ""))).strip()
        return str(first).strip()
    return ""


# ============================================================
# Rule 78 — Schema vs Visible Content
# ============================================================

def check_schema_vs_visible(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 78: Compare JSON-LD schema values with visible on-page metadata.

    NO body_text — compare against title, meta_description, og_tags,
    twitter_tags, h1, and canonical_url only.

    Allowances:
      - Whitespace / case → OK (no finding)
      - Currency formatting → OK
      - Punctuation only → INFO
      - Semantic difference → WARNING
      - Missing corresponding metadata → OPPORTUNITY
    """
    findings: list[Finding] = []

    for ctx in page_contexts:
        if ctx.status_code != 200:
            continue

        json_ld = _get_json_ld(ctx)
        if not json_ld:
            continue

        og_tags = _get_og_tags(ctx)
        tw_tags = _get_twitter_tags(ctx)
        page_url = ctx.url or ""

        for block in json_ld:
            at_type = block.get("@type", "")
            types = at_type if isinstance(at_type, list) else [at_type]

            for t in types:
                if not isinstance(t, str):
                    continue
                t = t.strip()

                if t == "Organization":
                    findings.extend(
                        _compare_organization(rule, block, ctx, og_tags, page_url)
                    )
                elif t == "Product":
                    findings.extend(
                        _compare_product(rule, block, ctx, og_tags, tw_tags, page_url)
                    )
                elif t == "Article":
                    findings.extend(
                        _compare_article(rule, block, ctx, og_tags, page_url)
                    )

    return findings


def _compare_organization(
    rule: RuleDefinition,
    block: dict,
    ctx: PageContext,
    og_tags: dict,
    page_url: str,
) -> list[Finding]:
    """Compare Organization schema against visible metadata."""
    findings: list[Finding] = []
    block_id = block.get("@id", "no-id")

    # --- name vs og:title / og:site_name / title ---
    schema_name = (block.get("name") or "").strip()
    if schema_name:
        candidates = [
            ("og:title", og_tags.get("og:title") or og_tags.get("title") or ""),
            ("og:site_name", og_tags.get("og:site_name") or og_tags.get("site_name") or ""),
            ("title tag", (ctx.title or "").strip()),
        ]
        best_type, best_val, best_label = _best_visible_match(schema_name, candidates)

        if best_type == "different" and best_val:
            findings.append(_mk(
                rule, url=page_url,
                detected=(
                    f"Organization schema name='{schema_name}' vs "
                    f"{best_label}='{best_val}'"
                ),
                expected="Schema name should match visible page metadata",
                evidence=(
                    f"schema_value={schema_name}, visible_value={best_val}, "
                    f"match_type=different, confidence=0.0"
                ),
                detail=(
                    f"Organization schema 'name' ('{schema_name}') differs from "
                    f"visible '{best_label}' ('{best_val}') — Google may flag "
                    "this as inconsistent structured data."
                ),
                severity=Severity.WARNING,
            ))
        elif best_type == "normalized" and best_val:
            findings.append(_mk(
                rule, url=page_url,
                detected=(
                    f"Organization schema name='{schema_name}' vs "
                    f"{best_label}='{best_val}' (normalized match)"
                ),
                expected="Exact match preferred for schema-to-visible consistency",
                evidence=(
                    f"schema_value={schema_name}, visible_value={best_val}, "
                    f"match_type=normalized, confidence=0.85"
                ),
                detail=(
                    f"Organization schema 'name' differs from '{best_label}' "
                    "only in formatting — not an error, but exact match is preferred."
                ),
                severity=Severity.INFO,
                confidence=0.85,
            ))
        elif best_val == "":
            findings.append(_mk(
                rule, url=page_url,
                detected=(
                    f"Organization schema name='{schema_name}' — "
                    "no visible title/og:site_name for comparison"
                ),
                expected="Visible page title and og:site_name available for cross-validation",
                evidence=f"schema_value={schema_name}, visible_value=(missing), match_type=missing",
                detail=(
                    f"Organization schema has 'name'='{schema_name}' but page "
                    "has no og:title, og:site_name, or title tag to compare against."
                ),
                severity=Severity.OPPORTUNITY,
            ))

    # --- url vs canonical_url ---
    schema_url = (block.get("url") or "").strip()
    if schema_url:
        canonical = (ctx.canonical_url or "").strip()
        if canonical:
            mtype, conf = _texts_match(schema_url, canonical)
            if mtype == "different":
                findings.append(_mk(
                    rule, url=page_url,
                    detected=(
                        f"Organization schema url='{schema_url}' vs "
                        f"canonical='{canonical}'"
                    ),
                    expected="Schema url should match canonical URL",
                    evidence=(
                        f"schema_value={schema_url}, visible_value={canonical}, "
                        f"match_type=different, confidence=0.0"
                    ),
                    detail=(
                        f"Organization schema 'url' ('{schema_url}') does not "
                        f"match canonical URL ('{canonical}') — Google may "
                        "interpret this as a URL inconsistency."
                    ),
                    severity=Severity.WARNING,
                ))
            elif mtype == "normalized":
                findings.append(_mk(
                    rule, url=page_url,
                    detected=(
                        f"Organization schema url='{schema_url}' vs "
                        f"canonical='{canonical}' (normalized match)"
                    ),
                    expected="Exact URL match for schema and canonical",
                    evidence=(
                        f"schema_value={schema_url}, visible_value={canonical}, "
                        f"match_type=normalized, confidence=0.85"
                    ),
                    detail=(
                        "Organization schema 'url' differs from canonical only "
                        "in trailing slash or protocol — not critical but should "
                        "be consistent."
                    ),
                    severity=Severity.INFO,
                    confidence=0.85,
                ))
        else:
            findings.append(_mk(
                rule, url=page_url,
                detected=(
                    f"Organization schema url='{schema_url}' — "
                    "no canonical URL for comparison"
                ),
                expected="Canonical URL available for cross-validation",
                evidence=f"schema_value={schema_url}, visible_value=(missing)",
                detail=(
                    f"Organization schema has 'url'='{schema_url}' but page has "
                    "no canonical URL to compare against."
                ),
                severity=Severity.OPPORTUNITY,
            ))

    # --- description vs meta_description / og:description ---
    schema_desc = (block.get("description") or "").strip()
    if schema_desc:
        desc_candidates = [
            ("meta description", (ctx.meta_description or "").strip()),
            (
                "og:description",
                og_tags.get("og:description") or og_tags.get("description") or "",
            ),
        ]
        best_type, best_val, best_label = _best_visible_match(
            schema_desc, desc_candidates
        )

        if best_type == "different" and best_val:
            findings.append(_mk(
                rule, url=page_url,
                detected=(
                    f"Organization schema description differs from {best_label}"
                ),
                expected="Schema description should match visible meta description",
                evidence=(
                    f"schema_value={schema_desc[:120]}, "
                    f"visible_value={best_val[:120]}, "
                    f"match_type=different, confidence=0.0"
                ),
                detail=(
                    f"Organization schema 'description' differs from visible "
                    f"'{best_label}' — inconsistent description may affect rich "
                    "result display."
                ),
                severity=Severity.WARNING,
            ))
        elif best_type == "normalized" and best_val:
            findings.append(_mk(
                rule, url=page_url,
                detected=(
                    f"Organization schema description vs {best_label} "
                    "(normalized match)"
                ),
                expected="Exact description match preferred",
                evidence="match_type=normalized",
                detail=(
                    "Organization schema description matches after normalization "
                    "— minor formatting difference only."
                ),
                severity=Severity.INFO,
                confidence=0.85,
            ))

    return findings


def _compare_product(
    rule: RuleDefinition,
    block: dict,
    ctx: PageContext,
    og_tags: dict,
    tw_tags: dict,
    page_url: str,
) -> list[Finding]:
    """Compare Product schema against visible metadata."""
    findings: list[Finding] = []
    block_id = block.get("@id", "no-id")

    # --- name vs og:title / title / h1 ---
    schema_name = (block.get("name") or "").strip()
    if schema_name:
        candidates = [
            ("og:title", og_tags.get("og:title") or og_tags.get("title") or ""),
            ("title tag", (ctx.title or "").strip()),
            ("h1", (ctx.h1 or "").strip()),
        ]
        best_type, best_val, best_label = _best_visible_match(
            schema_name, candidates
        )

        if best_type == "different" and best_val:
            findings.append(_mk(
                rule, url=page_url,
                detected=(
                    f"Product schema name='{schema_name}' vs "
                    f"{best_label}='{best_val}'"
                ),
                expected="Schema product name should match visible page title/h1",
                evidence=(
                    f"schema_value={schema_name}, visible_value={best_val}, "
                    f"match_type=different, confidence=0.0"
                ),
                detail=(
                    f"Product schema 'name' ('{schema_name}') differs from "
                    f"'{best_label}' ('{best_val}') — Google may flag this as "
                    "inconsistent product data."
                ),
                severity=Severity.WARNING,
            ))
        elif best_type == "normalized" and best_val:
            findings.append(_mk(
                rule, url=page_url,
                detected=(
                    f"Product schema name='{schema_name}' vs "
                    f"{best_label}='{best_val}' (normalized match)"
                ),
                expected="Exact match preferred",
                evidence="match_type=normalized, confidence=0.85",
                detail=(
                    f"Product schema 'name' differs from '{best_label}' only "
                    "in formatting — not critical."
                ),
                severity=Severity.INFO,
                confidence=0.85,
            ))
        elif best_val == "":
            findings.append(_mk(
                rule, url=page_url,
                detected=(
                    f"Product schema name='{schema_name}' — "
                    "no visible title/h1 for comparison"
                ),
                expected="Visible title and h1 available for cross-validation",
                evidence=f"schema_value={schema_name}, visible_value=(missing)",
                detail=(
                    f"Product schema has 'name'='{schema_name}' but page has "
                    "no title, h1, or og:title to compare against."
                ),
                severity=Severity.OPPORTUNITY,
            ))

    # --- offers.price vs og:product:price:amount ---
    offers = block.get("offers")
    if isinstance(offers, dict):
        schema_price = _extract_price(offers)
    elif isinstance(offers, list) and len(offers) > 0 and isinstance(offers[0], dict):
        schema_price = _extract_price(offers[0])
    else:
        schema_price = ""

    if schema_price:
        og_price = (
            og_tags.get("og:product:price:amount")
            or og_tags.get("product:price:amount")
            or og_tags.get("og:price:amount")
            or ""
        ).strip()

        tw_price = ""
        if not og_price and tw_tags:
            label1 = (
                tw_tags.get("twitter:label1") or tw_tags.get("label1") or ""
            ).lower().strip()
            if "price" in label1:
                tw_price = (
                    tw_tags.get("twitter:data1") or tw_tags.get("data1") or ""
                ).strip()

        visible_price = og_price or tw_price

        if visible_price:
            schema_price_norm = _normalize_price(schema_price)
            visible_price_norm = _normalize_price(visible_price)

            if schema_price_norm != visible_price_norm:
                findings.append(_mk(
                    rule, url=page_url,
                    detected=(
                        f"Product schema price='{schema_price}' vs "
                        f"visible price='{visible_price}'"
                    ),
                    expected="Schema price should match visible price metadata",
                    evidence=(
                        f"schema_value={schema_price}, "
                        f"visible_value={visible_price}, "
                        f"match_type=different, confidence=0.0"
                    ),
                    detail=(
                        f"Product schema 'offers.price' ('{schema_price}') "
                        f"differs from visible price ('{visible_price}') — "
                        "price mismatch can cause Google Merchant Center "
                        "disapprovals."
                    ),
                    severity=Severity.WARNING,
                ))
            elif schema_price.strip() != visible_price.strip():
                findings.append(_mk(
                    rule, url=page_url,
                    detected=(
                        f"Product schema price='{schema_price}' vs "
                        f"visible price='{visible_price}' (format difference)"
                    ),
                    expected="Consistent currency formatting",
                    evidence=(
                        f"schema_value={schema_price}, "
                        f"visible_value={visible_price}, "
                        f"match_type=normalized"
                    ),
                    detail=(
                        "Product schema price matches visible price after "
                        "currency formatting normalization."
                    ),
                    severity=Severity.INFO,
                    confidence=0.9,
                ))

    return findings


def _compare_article(
    rule: RuleDefinition,
    block: dict,
    ctx: PageContext,
    og_tags: dict,
    page_url: str,
) -> list[Finding]:
    """Compare Article schema against visible metadata."""
    findings: list[Finding] = []
    block_id = block.get("@id", "no-id")

    # --- headline vs h1 / og:title / title ---
    schema_headline = (block.get("headline") or "").strip()
    if schema_headline:
        candidates = [
            ("h1", (ctx.h1 or "").strip()),
            ("og:title", og_tags.get("og:title") or og_tags.get("title") or ""),
            ("title tag", (ctx.title or "").strip()),
        ]
        best_type, best_val, best_label = _best_visible_match(
            schema_headline, candidates
        )

        if best_type == "different" and best_val:
            findings.append(_mk(
                rule, url=page_url,
                detected=(
                    f"Article schema headline='{schema_headline}' vs "
                    f"{best_label}='{best_val}'"
                ),
                expected="Schema headline should match visible heading/title",
                evidence=(
                    f"schema_value={schema_headline}, visible_value={best_val}, "
                    f"match_type=different, confidence=0.0"
                ),
                detail=(
                    f"Article schema 'headline' ('{schema_headline}') differs "
                    f"from '{best_label}' ('{best_val}') — Google may flag "
                    "inconsistent article structured data."
                ),
                severity=Severity.WARNING,
            ))
        elif best_type == "normalized" and best_val:
            findings.append(_mk(
                rule, url=page_url,
                detected=(
                    f"Article schema headline='{schema_headline}' vs "
                    f"{best_label}='{best_val}' (normalized match)"
                ),
                expected="Exact match preferred",
                evidence="match_type=normalized, confidence=0.85",
                detail=(
                    f"Article headline differs from '{best_label}' only in "
                    "formatting."
                ),
                severity=Severity.INFO,
                confidence=0.85,
            ))
        elif best_val == "":
            findings.append(_mk(
                rule, url=page_url,
                detected=(
                    f"Article schema headline='{schema_headline}' — "
                    "no visible h1/og:title/title for comparison"
                ),
                expected="Visible headline available for cross-validation",
                evidence=f"schema_value={schema_headline}, visible_value=(missing)",
                detail=(
                    f"Article schema has 'headline'='{schema_headline}' but "
                    "page has no h1, title, or og:title to compare against."
                ),
                severity=Severity.OPPORTUNITY,
            ))

    return findings


# ============================================================
# Cross-check helpers
# ============================================================

def _best_visible_match(
    schema_value: str,
    candidates: list[tuple[str, str]],
) -> tuple[str, str, str]:
    """Find best match between schema value and visible candidates.

    Returns: (match_type, best_candidate_value, best_candidate_label)
    Priority: exact > normalized > different
    """
    best_type = "different"
    best_val = ""
    best_label = ""

    match_rank = {"exact": 3, "normalized": 2, "different": 1}

    for label, candidate_val in candidates:
        if not candidate_val or not candidate_val.strip():
            continue
        mtype, _ = _texts_match(schema_value, candidate_val)
        # Pick first candidate always (best_val empty), then only upgrade
        if best_val == "" or match_rank.get(mtype, 1) > match_rank.get(best_type, 0):
            best_type = mtype
            best_val = candidate_val.strip()
            best_label = label
        if mtype == "exact":
            break  # Cannot improve

    return best_type, best_val, best_label


def _extract_price(offers: dict) -> str:
    """Extract price string from an offers dict (handles priceSpecification)."""
    if not isinstance(offers, dict):
        return ""
    price = offers.get("price")
    if price is None:
        price_spec = offers.get("priceSpecification")
        if isinstance(price_spec, dict):
            price = price_spec.get("price")
    if price is None:
        return ""
    if isinstance(price, (int, float)):
        return str(price)
    return str(price).strip()


def _normalize_price(price: str) -> str:
    """Normalize price: strip currency symbols/codes, parse as float.

    Returns a normalized numeric string (e.g. "19.99") or the
    lowercased original if not parseable as a number.
    """
    if not price:
        return ""
    cleaned = re.sub(r"[$€£¥]\s*", "", price)
    cleaned = re.sub(
        r"\s*(USD|EUR|GBP|JPY|CNY|AUD|CAD|INR)\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = cleaned.strip()
    try:
        num = float(cleaned.replace(",", ""))
        if num == int(num):
            return str(int(num))
        return f"{num:.2f}".rstrip("0").rstrip(".")
    except (ValueError, TypeError):
        return cleaned.lower().strip()
