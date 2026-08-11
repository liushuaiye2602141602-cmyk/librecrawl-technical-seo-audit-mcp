"""Universal Master SEO Diagnostic Report — view model.

Separates presentation from diagnosis: this module owns human labels, scope
summaries, key findings, remediation planning, the remediation checklist,
score explanation, client-safe evidence, and report metadata. Rule detection
and scoring never live here and never change because of a wording change.

Contract:
  diagnostic data -> ReportViewModel -> DOCX renderer
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit


REPORT_SCHEMA_VERSION = "universal-report-v1"
REPORT_TEMPLATE_VERSION = "1.0.0"


LABELS: dict[str, dict[str, str]] = {
    "zh-CN": {
        "site": "网站",
        "score": "SEO 健康评分",
        "coverage": "检测覆盖率",
        "confidence": "结论置信度",
        "pages_crawled": "抓取页面数",
        "confirmed_issues": "确认问题",
        "warnings": "警告",
        "optimization": "优化机会",
        "manual_review": "人工评审",
        "data_required": "数据缺口",
        "key_findings": "重点发现 / 需要关注",
        "remediation_plan": "整改优先级计划",
        "checklist": "整改清单",
        "recheck": "复测工作流",
        "not_checked": "未检测",
        "not_applicable": "不适用",
        "required_data": "所需数据",
        "how_to_complete": "如何完成检测",
        "not_verified": "未验证",
        "why_not_applicable": "不适用原因",
        "action_priority": "行动优先级",
        "rule_priority": "规则优先级",
        "affected_scope": "影响范围",
        "what_to_do": "建议动作",
        "how_to_verify": "如何验证",
        "owner": "负责人",
        "status": "状态",
        "evidence": "证据",
        "why_it_matters": "为什么重要",
        "representative_urls": "代表性 URL",
    },
    "en-US": {
        "site": "Site",
        "score": "SEO Health Score",
        "coverage": "Coverage",
        "confidence": "Confidence",
        "pages_crawled": "Pages Crawled",
        "confirmed_issues": "Confirmed Issues",
        "warnings": "Warnings",
        "optimization": "Optimization Opportunities",
        "manual_review": "Manual Review",
        "data_required": "Data Required",
        "key_findings": "Key Findings / What Needs Attention",
        "remediation_plan": "Remediation Priority Plan",
        "checklist": "Remediation Checklist",
        "recheck": "Recheck Workflow",
        "not_checked": "Not Checked",
        "not_applicable": "Not Applicable",
        "required_data": "Required Data",
        "how_to_complete": "How To Complete",
        "not_verified": "Not Verified",
        "why_not_applicable": "Why Not Applicable",
        "action_priority": "Action Priority",
        "rule_priority": "Rule Priority",
        "affected_scope": "Affected Scope",
        "what_to_do": "What To Do",
        "how_to_verify": "How To Verify",
        "owner": "Owner",
        "status": "Status",
        "evidence": "Evidence",
        "why_it_matters": "Why It Matters",
        "representative_urls": "Representative URLs",
    },
}


def label(language: str, key: str) -> str:
    return LABELS.get(language, LABELS["zh-CN"]).get(key, key)


_WINDOWS_PATH_RE = re.compile(
    r"(?i)(?:[a-z]:\\[^\s\"']+|\\\\[^\s\"']+)")
_TOKEN_RE = re.compile(
    r"(?i)(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AIza[0-9A-Za-z_-]{20,}|eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.["
    r"A-Za-z0-9_-]+)")
_RAW_DICT_RE = re.compile(r"\{['\"][^}\n]{2,}['\"]:")
_SENSITIVE_WORDS = (
    "authorization", "set-cookie", "x-api-key", "bearer ", "secret",
    "password=", "access_token=", "-----begin",
)


def client_safe_text(value: Any) -> str:
    """Strip paths/tokens/raw dicts/sensitive values from client text."""
    text = str(value or "")
    text = _WINDOWS_PATH_RE.sub("[local path]", text)
    text = _TOKEN_RE.sub("[token]", text)
    text = _RAW_DICT_RE.sub("[raw object]", text)
    lowered = text.lower()
    if any(marker in lowered for marker in _SENSITIVE_WORDS):
        return "[sensitive value hidden]"
    return text


def shareable_safety_scan(text: str) -> list[str]:
    """Scan client-facing text for anything that must never ship.

    Returns a list of violations (empty = safe). Checks local paths, tokens,
    raw dicts, secrets, internal placeholders, debug markers, and generic
    junk strings.
    """
    violations: list[str] = []
    lowered = str(text or "").lower()
    if _WINDOWS_PATH_RE.search(text):
        violations.append("local path")
    if _TOKEN_RE.search(text):
        violations.append("token")
    if _RAW_DICT_RE.search(text):
        violations.append("raw dict")
    for marker in _SENSITIVE_WORDS:
        if marker in lowered:
            violations.append(f"sensitive marker: {marker.strip()}")
    for marker in (
        "traceback", "nonetype", "none type", "\\u", "{'", "'}", "d:\\\\",
        "c:\\\\", "internal: ", "debug", "todo", "tbd", "example.com",
        "lorem", "placeholder text",
    ):
        if marker in lowered:
            violations.append(f"debug/placeholder marker: {marker}")
    for token in ("SITE", "PAGE", "TEMPLATE"):
        if re.search(rf"(?<![\w/]){token}(?![\w/])", text):
            violations.append(f"internal scope token: {token}")
    return sorted(set(violations))


def compact_evidence(evidence: str, limit: int = 5) -> str:
    """Compress large evidence to count + top examples + artifact reference."""
    lines = [line for line in str(evidence or "").splitlines() if line.strip()]
    if len(lines) <= limit:
        return str(evidence or "")
    top = "\n".join(lines[:limit])
    return (
        f"{top}\n… 共 {len(lines)} 条 evidence；完整清单见 "
        "Detailed URL Findings CSV / 09_Technology_Profile.json"
    )


def _scope_summary(item: dict) -> str:
    execution = str(item.get("execution") or "")
    affected = int(item.get("affected_urls") or 0)
    if execution == "NOT_CHECKED":
        return "not checked"
    if execution == "NOT_APPLICABLE":
        return "not applicable"
    if affected > 0:
        return f"{affected} pages"
    return "site-wide"


def _result_order(result: str) -> int:
    return {"FAIL": 0, "WARNING": 1, "OPPORTUNITY": 2}.get(result, 9)


def _action_priority(result: str, rule_priority: str) -> str:
    if result == "NOT_APPLICABLE":
        return "N/A"
    if result == "FAIL":
        return {"Critical": "P0", "High": "P1", "Medium": "P2", "Low": "P3"}.get(
            rule_priority, "P2")
    if result == "WARNING":
        return {"Critical": "P1", "High": "P1", "Medium": "P2", "Low": "P3"}.get(
            rule_priority, "P2")
    if result == "OPPORTUNITY":
        return "P2"
    if result == "MANUAL_REVIEW_REQUIRED":
        return "Manual Review"
    if result == "UNKNOWN":
        return "Data gap"
    return "None"


def client_scope(value: str) -> str:
    """Replace internal scope tokens with human wording."""
    return {
        "SITE": "Site-wide / 全站",
        "PAGE": "Page-level / 页面级",
        "TEMPLATE": "Template-level / 模板级",
    }.get(str(value or "").upper(), str(value or "") or "site-wide")


FINAL_ACCEPTANCE_OVERRIDES: dict[int, str] = {
    1: ("/robots.txt 返回 200；重要页面未被错误 Disallow；robots 规则与预期抓取策略"
        "一致；如包含 Sitemap 声明，则地址有效。"),
    2: ("Automated/Crawl Acceptance: 重要 Sitemap URL 为 200 + Indexable + "
        "Canonical。\nExternal Validation: GSC/Bing submission/processing "
        "status requires external data and remains not checked."),
}


def _final_acceptance(audit_id: int, fallback: str) -> str:
    return FINAL_ACCEPTANCE_OVERRIDES.get(int(audit_id or 0), fallback)


def _result_diagnosis(result: str) -> str:
    """Result-consistent default diagnosis when the item lacks one."""
    return {
        "FAIL": "检测到确认问题，需要整改。",
        "WARNING": "检测到需要关注并处理的风险/观测。",
        "OPPORTUNITY": "检测到有证据支持的优化机会。",
        "PASS": "检查范围内未发现该规则对应的问题，状态健康。",
        "UNKNOWN": "当前证据不足以判定，结果未验证。",
        "NOT_APPLICABLE": "该规则不适用于当前网站架构。",
        "MANUAL_REVIEW_REQUIRED": "需要人工评审后才能判定。",
    }.get(result, "待判定。")


def _primary_action(execution: str, result: str, item: dict) -> str:
    """Execution-precedence primary action.

    NOT_APPLICABLE -> no action; NOT_CHECKED -> obtain the data / complete
    the check; executed rules -> result-driven action.
    """
    if execution == "NOT_APPLICABLE":
        return "No action required for the current site architecture."
    if result == "MANUAL_REVIEW_REQUIRED":
        manual = item.get("manual") or {}
        review = str(manual.get("review") or item.get("limitations") or "")
        return (f"Complete the manual review: "
                f"{review or 'perform the named manual review.'}")
    if execution == "NOT_CHECKED" or result == "UNKNOWN":
        required = _required_data_for(item)
        return f"Provide {required} and re-run the audit."
    if result == "PASS":
        return str(item.get("fix") or "") or "No remediation required."
    fix = str(item.get("fix") or "").strip()
    if not fix or "no remediation required" in fix.lower():
        if result == "WARNING":
            return "评估并缓解该规则范围内的风险（按规则整改建议执行）。"
        if result == "OPPORTUNITY":
            return "按规则优化建议执行（例如补充缺失信号/结构）。"
        return "按规则整改建议执行并复测。"
    return fix


def _potential_remediation(execution: str, result: str, item: dict) -> str:
    """Labeled potential remediation used only when a condition is confirmed."""
    if execution in ("NOT_APPLICABLE",):
        return ""
    fix = str(item.get("fix") or "").strip()
    if execution == "NOT_CHECKED" or result == "UNKNOWN":
        if not fix or "no remediation" in fix.lower():
            return ""
        return "Potential Remediation If Confirmed: " + fix
    if result == "MANUAL_REVIEW_REQUIRED":
        if not fix or "no remediation" in fix.lower():
            return ""
        return "Potential Remediation If Confirmed: " + fix
    return ""


def _acceptance(execution: str, result: str, audit_id: int,
                item_acceptance: str) -> str:
    """Acceptance wording that matches execution+result semantics."""
    if execution == "NOT_APPLICABLE":
        return ("Not applicable — no remediation/recheck required unless "
                "site architecture changes.")
    acceptance = str(item_acceptance or "").strip()
    if audit_id in FINAL_ACCEPTANCE_OVERRIDES:
        acceptance = _final_acceptance(audit_id, acceptance)
    if result == "PASS":
        return acceptance or "当前状态满足该规则要求。"
    if result == "UNKNOWN":
        return "Not yet verified（需先提供所需数据/完成人工检查）。"
    if result == "MANUAL_REVIEW_REQUIRED":
        return "待人工评审完成后按评审标准验收。"
    # FAIL / WARNING / OPPORTUNITY: acceptance describes the TARGET state
    # after remediation; never claim it is currently met.
    target = acceptance
    for claim in (" are met.", " is met.", "已满足", "达标", "已达成"):
        target = target.replace(claim, "")
    target = target.replace("Acceptance criteria for this rule", "验收标准")
    target = target.strip().strip("。.")
    if not target:
        target = "按规则验收标准复测确认。"
    return "修复/优化后的验收目标：" + target + "。"


def _why_not_applicable(item: dict) -> str:
    limitation = str(item.get("limitations") or "")
    if "WordPress" in limitation or "wordpress" in limitation:
        return ("Site is not WordPress (or the WordPress-specific rule does "
                "not apply to the detected stack).")
    if "multilingual" in limitation or "hreflang" in limitation:
        return "No multilingual structure detected."
    return limitation or "Current site architecture does not use this feature."


def _required_data_for(item: dict) -> str:
    limitation = str(item.get("limitations") or "")
    mapping = {
        "GSC": "Google Search Console (GSC)",
        "GA4": "GA4",
        "Semrush": "Semrush",
        "Server Logs": "Server Logs",
        "PageSpeed": "PageSpeed Insights (field/CrUX data)",
        "WordPress Privileged": "WordPress Admin / privileged snapshot",
        "Rendered DOM": "Rendered DOM / browser audit",
        "SnapshotBaseline": "Previous audit snapshot baseline",
        "Availability": "Availability monitoring data",
    }
    required = [value for key, value in mapping.items() if key in limitation]
    return ", ".join(required) if required else (
        limitation or "Additional external data")


def _how_to_complete(item: dict) -> str:
    required = _required_data_for(item)
    return (
        f"Provide {required} and re-run the audit (or complete the manual "
        "review) so this rule can be evaluated."
    )


@dataclass
class ReportViewModel:
    domain: str
    site_name: str
    audit_date: str
    pages_crawled: int
    score: float
    coverage_pct: float
    confidence_label: str
    confidence_pct: float
    audience: str
    language: str
    audit_items: list[dict] = field(default_factory=list)
    result_distribution: dict = field(default_factory=dict)
    execution_distribution: dict = field(default_factory=dict)
    task_counts: dict = field(default_factory=dict)
    management_summary: list[str] = field(default_factory=list)
    key_findings: list[dict] = field(default_factory=list)
    remediation_plan: list[dict] = field(default_factory=list)
    checklist_rows: list[dict] = field(default_factory=list)
    manual_review_rows: list[dict] = field(default_factory=list)
    roadmap: dict = field(default_factory=dict)
    responsibility: list[dict] = field(default_factory=list)
    recheck_steps: list[str] = field(default_factory=list)
    score_explanation: list[str] = field(default_factory=list)
    explanations: list[str] = field(default_factory=list)
    technology_observations: list[dict] = field(default_factory=list)
    technology_risks: list[dict] = field(default_factory=list)
    report_metadata: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)

    @property
    def diagnosis_signature(self) -> str:
        """Identical across audience modes: same SEO Result set."""
        return "|".join(
            f"{item['audit_id']}:{item['result']}:{item['execution']}"
            for item in self.audit_items
        )


def build_report_view(
    items: list[dict],
    task_rows: list[dict],
    metrics: dict,
    manual_rows: list[dict],
    technology_profile: dict | None,
    technology_risks: list[dict],
    *,
    domain: str,
    audit_date: str,
    site_name: str = "",
    pages_crawled: int = 0,
    audience: str = "client",
    language: str = "zh-CN",
    run_metadata: dict | None = None,
) -> ReportViewModel:
    """Build the presentation view model from current-run diagnostic data."""
    hostname = urlsplit(domain or "https://example.com/").hostname or "Website"
    site_name = site_name.strip() or hostname.split(".")[0].capitalize()
    pages_crawled = int(pages_crawled or len(items) or 0)
    score = float(metrics.get("score") or 0)
    coverage_pct = float(metrics.get("coverage_pct") or 0)
    confidence_pct = float(metrics.get("confidence_pct") or 0)
    confidence_label = "High" if confidence_pct >= 80 else (
        "Medium" if confidence_pct >= 50 else "Low")

    audit_items = [_actionable_audit(item) for item in items]
    result_distribution = _distribution(audit_items, "result")
    execution_distribution = _distribution(audit_items, "execution")
    task_counts = _task_counts(task_rows)
    key_findings = _build_key_findings(audit_items)
    remediation_plan = _build_remediation_plan(task_rows)
    checklist_rows = _build_checklist(task_rows)
    management_summary = _build_management_summary(
        score, coverage_pct, confidence_label, confidence_pct,
        pages_crawled, result_distribution, execution_distribution,
        task_counts, audit_items)
    score_explanation, explanations = _build_score_explanation(
        score, coverage_pct, confidence_label, confidence_pct)
    recheck_steps = _build_recheck_steps()
    responsibility = _build_responsibility(task_rows)
    roadmap = _build_roadmap(task_rows, audit_items)
    technology_observations = _technology_observations(technology_profile)
    client_manual_rows = [
        dict(row, scope=client_scope(row.get("scope")))
        for row in (manual_rows or [])
    ]

    metadata = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_template_version": REPORT_TEMPLATE_VERSION,
        "source_url": domain,
        "audit_date": audit_date,
        "pages_crawled": pages_crawled,
        "audience": audience,
        "language": language,
        "run_id": (run_metadata or {}).get("run_id", ""),
        "replay_sha256": (run_metadata or {}).get("replay_sha256", ""),
    }
    return ReportViewModel(
        domain=hostname,
        site_name=site_name,
        audit_date=audit_date,
        pages_crawled=pages_crawled,
        score=score,
        coverage_pct=coverage_pct,
        confidence_label=confidence_label,
        confidence_pct=confidence_pct,
        audience=audience,
        language=language,
        audit_items=audit_items,
        result_distribution=result_distribution,
        execution_distribution=execution_distribution,
        task_counts=task_counts,
        management_summary=management_summary,
        key_findings=key_findings,
        remediation_plan=remediation_plan,
        checklist_rows=checklist_rows,
        manual_review_rows=client_manual_rows,
        roadmap=roadmap,
        responsibility=responsibility,
        recheck_steps=recheck_steps,
        score_explanation=score_explanation,
        explanations=explanations,
        technology_observations=technology_observations,
        technology_risks=list(technology_risks or []),
        report_metadata=metadata,
        metrics=dict(metrics),
    )


def _actionable_audit(item: dict) -> dict:
    result = str(item.get("result") or "UNKNOWN")
    execution = str(item.get("execution") or "NOT_CHECKED")
    rule_priority = str(item.get("priority") or "")
    audit_id = int(item.get("audit_id") or 0)
    action_priority = (
        "N/A" if execution == "NOT_APPLICABLE"
        else _action_priority(result, rule_priority))
    enriched = dict(item)
    enriched["action_priority"] = action_priority
    enriched["summary_action"] = _summary_action(execution, result)
    enriched["scope"] = client_scope(_scope_summary(item))
    enriched["representative"] = (item.get("representative") or [])[:5]
    enriched["why_it_matters"] = str(
        item.get("seo_impact") or item.get("why_it_matters") or "")
    enriched["what_to_do"] = _primary_action(execution, result, item)
    potential = _potential_remediation(execution, result, item)
    if potential:
        enriched["what_to_do"] += "\n" + potential
    enriched["how_to_verify"] = _acceptance(
        execution, result, audit_id, str(item.get("acceptance") or ""))
    enriched["evidence"] = compact_evidence(item.get("evidence") or "")
    diagnosis = str(item.get("diagnosis") or "").strip()
    if execution == "NOT_APPLICABLE":
        enriched["diagnosis"] = "不适用。"
        enriched["actual_state"] = "Not applicable"
        enriched["why_not_applicable"] = _why_not_applicable(item)
        enriched["current_state"] = "Not applicable"
        enriched.pop("required_data", None)
        enriched.pop("how_to_complete", None)
        enriched.pop("not_verified", None)
    elif result == "MANUAL_REVIEW_REQUIRED":
        enriched["not_verified"] = True
        enriched["current_state"] = "Pending manual review"
        if not diagnosis:
            enriched["diagnosis"] = "需要人工评审。"
    elif execution == "NOT_CHECKED" or result == "UNKNOWN":
        enriched["required_data"] = _required_data_for(item)
        enriched["how_to_complete"] = _how_to_complete(item)
        enriched["not_verified"] = True
        enriched["current_state"] = "Not verified"
        if not diagnosis:
            enriched["diagnosis"] = "数据不足，无法判定。"
    elif result in ("FAIL", "WARNING", "OPPORTUNITY") and (
            not diagnosis or diagnosis == "Normal"):
        enriched["diagnosis"] = _result_diagnosis(result)
    elif not diagnosis:
        enriched["diagnosis"] = _result_diagnosis(result)
    if result == "PASS":
        enriched["why_pass"] = (
            "The checked scope showed no actionable defect in this rule's "
            "evidence; maintain the current implementation.")
    return enriched


def _summary_action(execution: str, result: str) -> str:
    """Execution-precedence summary action label."""
    if execution == "NOT_APPLICABLE":
        return "None / N/A"
    if execution == "NOT_CHECKED":
        return "Data Required / Manual completion"
    if result == "FAIL":
        return "Fix"
    if result == "WARNING":
        return "Mitigate / Review"
    if result == "OPPORTUNITY":
        return "Optimize"
    if result == "MANUAL_REVIEW_REQUIRED":
        return "Manual Review"
    return "None"


def _distribution(audit_items: list[dict], key: str) -> dict:
    counts: dict[str, int] = {}
    for item in audit_items:
        value = str(item.get(key) or "UNKNOWN")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _task_counts(task_rows: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for row in task_rows:
        task_type = str(row.get("task_type") or "MONITORING")
        counts[task_type] = counts.get(task_type, 0) + 1
    return counts


def _build_key_findings(items: list[dict], limit: int = 15) -> list[dict]:
    candidates = [
        item for item in items
        if item.get("result") in ("FAIL", "WARNING", "OPPORTUNITY")
        and item.get("execution") in ("EXECUTED_FULL", "EXECUTED_PARTIAL")
    ]
    ranked = sorted(
        candidates,
        key=lambda item: (
            _result_order(str(item.get("result"))),
            -int(item.get("affected_urls") or 0),
            int(item.get("audit_id") or 0),
        ),
    )
    findings = []
    for item in ranked[:limit]:
        findings.append({
            "priority": _action_priority(
                str(item.get("result")), str(item.get("priority") or "")),
            "audit_id": item.get("audit_id"),
            "check": item.get("check", ""),
            "result": item.get("result"),
            "issue": item.get("check", ""),
            "why_it_matters": str(
                item.get("seo_impact") or item.get("why_it_matters") or ""),
            "affected_scope": _scope_summary(item),
            "recommended_action": str(item.get("what_to_do") or ""),
        })
    return findings


def _build_remediation_plan(task_rows: list[dict]) -> list[dict]:
    action_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    rule_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    rule_priority = {
        "Critical": "P0", "High": "P1", "Medium": "P2", "Low": "P3",
    }
    ordered = sorted(
        task_rows,
        key=lambda row: (
            action_order.get(
                _action_priority(
                    _task_result_for(row),
                    str(row.get("priority") or "")), 9),
            rule_order.get(str(row.get("priority")), 9),
            str(row.get("task_type") or ""),
            int(row.get("audit_id") or 0),
        ),
    )
    plan = []
    for index, row in enumerate(ordered, start=1):
        audit_id = int(row.get("audit_id") or 0)
        plan.append({
            "order": index,
            "action_priority": _action_priority(
                _task_result_for(row), str(row.get("priority") or "")),
            "rule_priority": rule_priority.get(
                str(row.get("priority")), str(row.get("priority") or "")),
            "audit_id": audit_id,
            "problem": str(row.get("finding") or ""),
            "scope": str(row.get("affected_url_count") or row.get("url") or ""),
            "action": str(row.get("remediation") or ""),
            "owner": str(row.get("owner") or ""),
            "verify": str(row.get("acceptance_criteria") or ""),
            "status": "Open",
        })
    return plan


def _task_result_for(row: dict) -> str:
    """Map a task to the result its audit would carry (for consistency)."""
    task_type = str(row.get("task_type") or "")
    if task_type == "REMEDIATION":
        return "FAIL"
    if task_type == "OPTIMIZATION":
        return "OPPORTUNITY"
    if task_type in ("DATA_REQUIRED",):
        return "UNKNOWN"
    if task_type in ("MANUAL_REVIEW",):
        return "MANUAL_REVIEW_REQUIRED"
    return "PASS"


def _build_checklist(task_rows: list[dict]) -> list[dict]:
    rows = []
    for row in task_rows:
        audit_id = int(row.get("audit_id") or 0)
        action_priority = _action_priority(
            _task_result_for(row), str(row.get("priority") or ""))
        rule_priority = str(row.get("priority") or "")
        rows.append({
            "checkbox": "☐",
            "audit_id": audit_id,
            "action_priority": action_priority,
            "rule_priority": rule_priority,
            "problem": str(row.get("finding") or ""),
            "scope": str(row.get("affected_url_count") or row.get("url") or ""),
            "action": str(row.get("remediation") or ""),
            "owner": str(row.get("owner") or ""),
            "verification": str(row.get("acceptance_criteria") or ""),
            "status": "Open",
        })
    return rows


def _build_management_summary(
    score, coverage_pct, confidence_label, confidence_pct,
    pages_crawled, result_distribution, execution_distribution,
    task_counts, audit_items,
) -> list[str]:
    fail_audits = result_distribution.get("FAIL", 0)
    warning_audits = result_distribution.get("WARNING", 0)
    opportunity_audits = result_distribution.get("OPPORTUNITY", 0)
    unknown_audits = result_distribution.get("UNKNOWN", 0)
    remediation_tasks = task_counts.get("REMEDIATION", 0)
    optimization_tasks = task_counts.get("OPTIMIZATION", 0)
    data_required_tasks = task_counts.get("DATA_REQUIRED", 0)
    manual_tasks = task_counts.get("MANUAL_REVIEW", 0)
    total_audits = len(audit_items)
    return [
        f"SEO 健康评分: {score:.2f} / 100（仅统计已执行规则）",
        f"检测覆盖率: {coverage_pct:.2f}%（实际完成自动/部分检查的程度）",
        f"结论置信度: {confidence_label}（{confidence_pct:.2f}%）",
        f"抓取页面数: {pages_crawled}",
        f"审计状态（共 {total_audits} 项）— 失败审计: {fail_audits} · "
        f"警告审计: {warning_audits} · 机会审计: {opportunity_audits} · "
        f"未验证/人工: {unknown_audits}",
        f"整改任务（REMEDIATION tasks）: {remediation_tasks} 条",
        f"优化任务（OPTIMIZATION tasks）: {optimization_tasks} 条",
        f"数据缺口任务（DATA_REQUIRED tasks）: {data_required_tasks} 条",
        f"人工评审任务（MANUAL_REVIEW tasks）: {manual_tasks} 条",
    ]


def _build_score_explanation(score, coverage_pct, confidence_label,
                             confidence_pct):
    score_text = (
        "评分 = 已执行规则的加权健康情况；它衡量“已检查范围内”的健康度，"
        "不是 Google 官方评分，也不是排名预测。")
    coverage_text = (
        "覆盖率 = 实际完成自动/部分检查的程度；外部数据缺失的规则保持 "
        "NOT_CHECKED，不进入 PASS/FAIL。")
    confidence_text = (
        "置信度 = 结论可依赖程度；缺少字段数据（如 CrUX）时，"
        "不会声明真实的 Core Web Vitals PASS。")
    return [score_text], [score_text, coverage_text, confidence_text]


def _build_recheck_steps() -> list[str]:
    return [
        "1. 按整改清单完成修复。",
        "2. 对受影响 URL 进行 spot-check。",
        "3. 重新运行审计（同一规则集）。",
        "4. 对比 Result / Affected Count / Evidence / Score / Coverage。",
        "5. 仅当 Acceptance Criteria 真正满足时，标记为 Verified。",
    ]


def _build_responsibility(task_rows: list[dict]) -> list[dict]:
    groups: dict[str, int] = {}
    for row in task_rows:
        owner = str(row.get("owner") or "SEO")
        groups[owner] = groups.get(owner, 0) + 1
    return [
        {"owner": owner, "task_count": count}
        for owner, count in sorted(groups.items(), key=lambda kv: -kv[1])
    ]


def _build_roadmap(task_rows: list[dict], audit_items: list[dict]) -> dict:
    titles = {
        int(item.get("audit_id") or 0): str(item.get("check") or "")
        for item in audit_items
    }

    def entry(row: dict) -> str:
        audit_id = int(row.get("audit_id") or 0)
        title = titles.get(audit_id, "")
        problem = str(row.get("finding") or "")
        action = str(row.get("remediation") or "")
        label = f"{title}" if title else f"Audit #{audit_id}"
        return f"#{audit_id} — {label}: {problem} {action}".strip()

    immediate = [
        entry(row) for row in task_rows
        if str(row.get("priority")) == "Critical"
        and str(row.get("task_type")) == "REMEDIATION"
    ]
    short_term = [
        entry(row) for row in task_rows
        if str(row.get("priority")) == "High"
        or (str(row.get("priority")) == "Critical"
            and str(row.get("task_type")) != "REMEDIATION")
    ]
    medium_term = [
        entry(row) for row in task_rows
        if not (str(row.get("priority")) == "Critical"
                and str(row.get("task_type")) == "REMEDIATION")
        and not (str(row.get("priority")) == "High"
                 or (str(row.get("priority")) == "Critical"
                     and str(row.get("task_type")) != "REMEDIATION"))
    ]
    data_collection = [
        (f"#{item['audit_id']} — {item['check']}: "
         f"Collect {item.get('required_data', 'required data')}.")
        for item in audit_items
        if item.get("execution") == "NOT_CHECKED"
        and item.get("result") == "UNKNOWN"
    ]
    return {
        "immediate": immediate,
        "short_term": short_term,
        "medium_term": medium_term,
        "data_collection": data_collection,
    }


def _technology_evidence(detection: dict) -> list[str]:
    sources = detection.get("detection_sources") or []
    lines = []
    for source in sources[:2]:
        if isinstance(source, dict):
            signal_type = str(source.get("signal_type") or "signal")
            signal_value = str(source.get("signal_value") or "").strip()
            if signal_value:
                lines.append(f"{signal_type}: {signal_value[:80]}")
    if lines:
        return lines
    status = str(detection.get("status") or "UNKNOWN")
    if status == "DETECTED":
        return ["Vendor-specific signature observed "
                "(details in 09_Technology_Profile.json)"]
    return ["Observable signals present but not vendor-confirmed "
            "(details in 09_Technology_Profile.json)"]


def _technology_observations(profile: dict | None) -> list[dict]:
    observations = []
    for detection in (profile or {}).get("detections") or []:
        status = str(detection.get("status") or "UNKNOWN")
        confidence = str(detection.get("confidence") or "Low")
        if status == "DETECTED" and confidence == "High":
            presentation = "confirmed"
        elif status == "DETECTED" and confidence == "Medium":
            presentation = "confirmed (medium evidence)"
        else:
            presentation = "Not Confirmed"
        observations.append({
            "technology": detection.get("technology_name", ""),
            "category": detection.get("category", ""),
            "status": status,
            "confidence": confidence,
            "version": detection.get("version", "Unknown"),
            "presentation": presentation,
            "evidence": _technology_evidence(detection),
        })
    return observations
