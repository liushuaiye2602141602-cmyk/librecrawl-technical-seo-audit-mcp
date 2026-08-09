"""Deterministic, privacy-safe artifacts from normalized provider evidence."""

import csv
import io
import json


def _safe(value):
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


def _csv(columns: list[str], rows: list[list]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows([[_safe(value) for value in row] for row in rows])
    return output.getvalue()


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def build_external_artifacts(data: dict) -> dict[str, str]:
    """Return artifacts only for providers that collected normalized evidence."""
    artifacts = {}
    gsc = data.get("gsc") or {}
    if gsc.get("current_rows") is not None and not (
            gsc.get("errors") and not gsc.get("current_rows") and not gsc.get("previous_rows")):
        columns = ["period", "page", "query", "country", "device",
                   "clicks", "impressions", "ctr", "position"]
        rows = []
        for period, key in (("current", "current_rows"), ("previous", "previous_rows")):
            for item in gsc.get(key) or []:
                rows.append([period] + [item.get(column, "") for column in columns[1:]])
        artifacts["search_performance_csv"] = _csv(columns, rows)

    semrush = data.get("semrush") or {}
    if (semrush.get("overview") is not None or semrush.get("lost_links")
            or semrush.get("referring_domains")
            or semrush.get("domain_keywords") or semrush.get("organic_competitors")):
        columns = [
            "record_type", "target", "source_url", "target_url", "domain_score",
            "is_lost", "keyword", "position", "previous_position", "position_change",
            "search_volume", "traffic_pct", "competitor_domain", "competition_level",
            "common_keywords", "organic_keywords", "organic_traffic", "referring_backlinks",
            "aggregate_backlinks", "aggregate_domains", "authority_score", "new_count",
            "lost_count",
        ]
        target = semrush.get("target", "")
        records = []
        overview = semrush.get("overview")
        if isinstance(overview, dict):
            records.append({
                "record_type": "overview", "target": target,
                "aggregate_backlinks": overview.get("backlinks_count", ""),
                "aggregate_domains": overview.get("domains_count", ""),
                "authority_score": overview.get("score", ""),
                "new_count": overview.get("new_count", ""),
                "lost_count": overview.get("lost_count", ""),
            })
        records.extend({
            "record_type": "lost_backlink", "target": target,
            "source_url": item.get("source_url", ""),
            "target_url": item.get("target_url", ""),
            "domain_score": item.get("domain_score", ""),
            "is_lost": item.get("is_lost", ""),
        } for item in semrush.get("lost_links") or [])
        records.extend({
            "record_type": "referring_domain", "target": target,
            "domain_score": item.get("domain_score", ""),
            "competitor_domain": item.get("domain", ""),
            "referring_backlinks": item.get("backlinks_count", ""),
        } for item in semrush.get("referring_domains") or [])
        records.extend({
            "record_type": "domain_keyword", "target": target,
            "target_url": item.get("url", ""), "keyword": item.get("keyword", ""),
            "position": item.get("position", ""),
            "previous_position": item.get("previous_position", ""),
            "position_change": item.get("position_change", ""),
            "search_volume": item.get("search_volume", ""),
            "traffic_pct": item.get("traffic_pct", ""),
        } for item in semrush.get("domain_keywords") or [])
        records.extend({
            "record_type": "organic_competitor", "target": target,
            "competitor_domain": item.get("domain", ""),
            "competition_level": item.get("competition_level", ""),
            "common_keywords": item.get("common_keywords", ""),
            "organic_keywords": item.get("organic_keywords", ""),
            "organic_traffic": item.get("organic_traffic", ""),
        } for item in semrush.get("organic_competitors") or [])
        artifacts["backlinks_csv"] = _csv(
            columns, [[record.get(column, "") for column in columns] for record in records])

    logs = data.get("server_logs") or {}
    if logs.get("processed_lines") is not None:
        rows = [["summary", key, logs.get(key, "")] for key in (
            "processed_lines", "valid_lines", "malformed_lines", "truncated",
            "response_time_p95_ms")]
        for key in ("status_counts", "bot_counts", "waste_bot_counts"):
            rows.extend([key, label, value] for label, value in sorted((logs.get(key) or {}).items()))
        artifacts["server_log_analysis_csv"] = _csv(["metric", "label", "value"], rows)

    for source, kind in (
        ("wordpress_privileged", "wordpress_audit_json"),
        ("ga4", "ga4_audit_json"),
        ("render_snapshot", "render_audit_json"),
        ("availability_snapshot", "availability_audit_json"),
    ):
        payload = data.get(source)
        if isinstance(payload, dict) and any(key != "errors" for key in payload):
            artifacts[kind] = _json(payload)
    return artifacts
