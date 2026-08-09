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
    if semrush.get("overview") is not None or semrush.get("lost_links"):
        columns = ["target", "source_url", "target_url", "domain_score", "is_lost"]
        rows = [[semrush.get("target", ""), item.get("source_url", ""),
                 item.get("target_url", ""), item.get("domain_score", ""),
                 item.get("is_lost", "")] for item in semrush.get("lost_links") or []]
        if not rows:
            rows.append([semrush.get("target", ""), "", "", "", ""])
        artifacts["backlinks_csv"] = _csv(columns, rows)

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
