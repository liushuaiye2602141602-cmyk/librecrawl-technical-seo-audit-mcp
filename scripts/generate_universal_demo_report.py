"""Generate the Universal Master SEO Diagnostic Report demo.

Offline only: the demo uses the REAL Master 80-rule definitions (names,
categories, remediation, owners, acceptance criteria) with SYNTHETIC website
evidence. No live crawl, no client data, no placeholder rule names.

Output: reports/universal-demo-<date>/ (DOCX + machine artifacts + ZIP).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

DEMO_URL = "https://demo-client.example/"
DEMO_SITE_NAME = "Demo Client"

# Deterministic synthetic scenario per audit id.
SCENARIOS = {
    6: {"result": "FAIL", "affected": 12,
        "state": ("http 与 www 均 301 到 https 规范主机；但 non-www 主机返回 "
                  "200 未跳转，12 个 URL 受影响。"),
        "diagnosis": "检测到确认问题：non-www 主机未 301 到规范主机。",
        "evidence": ("12 URLs on the non-www host return 200 without "
                     "redirect; canonical targets https://www.")},
    15: {"result": "FAIL", "affected": 8,
         "state": ("8 个归档/标签页面缺失主 H1，页面标题与正文主题不明确。"),
         "diagnosis": "检测到确认问题：8 个页面缺失清晰主 H1。",
         "evidence": "H1 missing on 8 archive/tag pages."},
    13: {"result": "WARNING", "affected": 6,
         "state": ("6 组页面共享重复 Title，模板化输出导致标题不唯一。"),
         "diagnosis": "检测到需要处理的风险：重复 Title 影响唯一性。",
         "evidence": "6 duplicate title groups detected."},
    79: {"result": "WARNING", "affected": 120,
         "state": ("120 个页面存在图片缺少描述性 ALT，共 480 个实例候选；"
                   "装饰性图片需人工分类。"),
         "diagnosis": "检测到需要处理的风险：图片 ALT 大面积缺失。",
         "evidence": ("480 missing-alt candidate instances across 120 pages; "
                      "decorative vs informative requires review.")},
    14: {"result": "OPPORTUNITY", "affected": 45,
         "state": ("45 个产品页面 Meta Description 为空或过短，可补充转化导向描述。"),
         "diagnosis": "检测到有证据支持的优化机会。",
         "evidence": "45 product pages missing or too-short meta description."},
    32: {"result": "OPPORTUNITY", "affected": 1,
         "state": ("站点使用大量产品图片，但未提供媒体 sitemap。"),
         "diagnosis": "检测到有证据支持的优化机会。",
         "evidence": "Media sitemap not present."},
    20: {"result": "UNKNOWN", "execution": "NOT_CHECKED", "affected": 0,
         "limitations": "Data source unavailable: Server Logs",
         "state": "Not verified — 需要服务器日志/TTFB 字段数据。",
         "diagnosis": "数据不足，无法判定。",
         "evidence": "Server logs / TTFB field data required."},
    34: {"result": "UNKNOWN", "execution": "NOT_CHECKED", "affected": 0,
         "limitations": "Data source unavailable: GSC, GA4",
         "state": "Not verified — 需要 GSC/GA4 配置数据。",
         "diagnosis": "数据不足，无法判定。",
         "evidence": "GSC / GA4 configuration data required."},
    46: {"result": "UNKNOWN", "execution": "NOT_CHECKED", "affected": 0,
         "limitations": "Data source unavailable: Rendered DOM Snapshots",
         "state": "Not verified — 需要渲染 DOM 快照。",
         "diagnosis": "数据不足，无法判定。",
         "evidence": "Rendered DOM snapshot required."},
    29: {"result": "UNKNOWN", "execution": "NOT_APPLICABLE", "affected": 0,
         "limitations": "Single-language site (en-US only)",
         "state": "不适用：站点仅单一语言，无多语言 hreflang 结构。",
         "diagnosis": "不适用。",
         "evidence": "Single-language site detected."},
    59: {"result": "UNKNOWN", "execution": "NOT_APPLICABLE", "affected": 0,
         "limitations": "Single-language site (en-US only)",
         "state": "不适用：站点仅单一语言，无语言代码匹配问题。",
         "diagnosis": "不适用。",
         "evidence": "Single-language site detected."},
    53: {"result": "MANUAL_REVIEW_REQUIRED",
         "execution": "NOT_CHECKED", "affected": 0,
         "limitations": "Manual Review required: 搜索意图匹配",
         "state": "待人工评审：判断落地页类型与 SERP 主流意图是否匹配。",
         "diagnosis": "需要人工评审。",
         "evidence": "Manual review worksheet required.",
         "manual": {
             "why": "搜索意图匹配需要人工判断。",
             "review": "检查主要关键词落地页类型与 SERP 意图。",
             "evidence": "人工评审工作表 / SERP 观察。",
             "pass": "主要关键词落地页类型与 SERP 意图明显一致。",
         }},
}


def _registry():
    from audit_rules.registry import load_registry
    return {rule.audit_id: rule for rule in load_registry()}


def _synthetic_state(audit_id: int, rule, result: str) -> str:
    scenario = SCENARIOS.get(audit_id)
    if scenario:
        return scenario["state"]
    if result == "PASS":
        return (f"检查范围内未发现 {rule.title} 对应的问题；"
                "代表性页面抽查正常。")
    return "检查范围内发现需要处理的情况（见证据）。"


def _representative_urls(audit_id: int, affected: int) -> list[str]:
    if affected <= 0:
        return []
    pages = ["about", "products/apple-sorter", "products/tomato-grader",
             "products/onion-peeler", "contact"]
    urls = [f"{DEMO_URL}{page}" for page in pages[:min(5, max(1, affected))]]
    if affected > 5:
        urls.append(f"… 共 {affected} 个 URL（完整清单见 Detailed URL Findings）")
    return urls


def _build_items() -> list[dict]:
    rules = _registry()
    items = []
    for audit_id in range(1, 81):
        rule = rules[audit_id]
        scenario = SCENARIOS.get(audit_id, {})
        result = scenario.get("result", "PASS")
        execution = scenario.get("execution",
                                 "EXECUTED_FULL"
                                 if result in ("PASS", "FAIL", "WARNING",
                                               "OPPORTUNITY")
                                 else "NOT_CHECKED")
        affected = int(scenario.get("affected", 0))
        items.append({
            "audit_id": audit_id,
            "category": rule.category.value,
            "check": rule.title,
            "what_checked": str(rule.description or rule.title),
            "execution": execution,
            "result": result,
            "priority": rule.priority.value,
            "confidence": "1.00",
            "data_source": (rule.required_data_sources[0]
                            if rule.required_data_sources else "LibreCrawl"),
            "actual_state": _synthetic_state(audit_id, rule, result),
            "diagnosis": scenario.get(
                "diagnosis",
                "检查范围内未发现该规则对应的问题，状态健康。"
                if result == "PASS" else "见证据。"),
            "evidence": scenario.get(
                "evidence", f"{rule.title} — 代表性证据见页面抽查。"),
            "affected_urls": affected,
            "representative": _representative_urls(audit_id, affected),
            "seo_impact": (
                "影响该规则对应指标的抓取、索引或用户体验；"
                "按整改建议处理后复测验收。"
                if result != "PASS" else "该规则当前健康，无需处理。"),
            "fix": rule.remediation,
            "owner": rule.owner,
            "acceptance": rule.acceptance_criteria,
            "limitations": scenario.get("limitations", ""),
            "observed": "",
            "manual": scenario.get("manual", {}),
            "is_pass": result == "PASS",
            "action_required": "None" if result == "PASS" else "Fix",
        })
    return items


def _tasks() -> list[dict]:
    rules = _registry()
    rows = []
    for audit_id, task_type in (
        (6, "REMEDIATION"), (15, "REMEDIATION"),
        (14, "OPTIMIZATION"), (32, "OPTIMIZATION"),
        (20, "DATA_REQUIRED"), (34, "DATA_REQUIRED"), (46, "DATA_REQUIRED"),
        (53, "MANUAL_REVIEW"),
    ):
        rule = rules[audit_id]
        rows.append({
            "task_type": task_type,
            "audit_id": audit_id,
            "rule_id": rule.rule_id,
            "priority": rule.priority.value,
            "severity": rule.severity.value,
            "url": _representative_urls(audit_id, 1)[0] if SCENARIOS.get(
                audit_id, {}).get("affected", 0) else DEMO_URL,
            "finding": SCENARIOS[audit_id].get("diagnosis", ""),
            "evidence": SCENARIOS[audit_id].get("evidence", ""),
            "remediation": rule.remediation,
            "owner": rule.owner,
            "acceptance_criteria": rule.acceptance_criteria,
            "confidence": "1.0",
            "affected_url_count": int(
                SCENARIOS[audit_id].get("affected", 0)),
            "affected_urls_sample": _representative_urls(audit_id, 1)[0]
            if SCENARIOS[audit_id].get("affected", 0) else DEMO_URL,
            "status": "Open",
        })
    return rows


def _metrics() -> dict:
    return {
        "audit_rows": 80, "matrix_rows": 80, "coverage_rows": 80,
        "finding_rows": 8, "task_rows": 8, "manual_rows": 1,
        "performance_rows": 0, "pdf_pages": 0,
        "confirmed_remediation": 2, "optimization": 2,
        "data_required": 3, "manual_review_actions": 1,
        "p0": 1, "p1": 1, "p2": 4, "p3": 2,
        "score": 88.08, "coverage_pct": 61.25, "confidence_pct": 84.79,
    }


def _technology_profile() -> dict:
    return {
        "schema_version": "technology-profile-v1",
        "detector_version": "1.2.0",
        "signature_registry_version": "1.2.0",
        "source_url": DEMO_URL,
        "detections": [
            {"category": "CMS", "technology_name": "WordPress",
             "status": "DETECTED", "confidence": "High",
             "confidence_score": 0.82, "version": "Unknown",
             "detection_sources": [
                 {"signal_type": "asset_path",
                  "signal_value": "/wp-content/themes/demo/theme.css",
                  "source_url": DEMO_URL, "source_scope": "multi_page",
                  "strength": "strong", "provenance": "local_crawl",
                  "pattern": r"/wp-content/"},
                 {"signal_type": "asset_path",
                  "signal_value": "/wp-includes/js/jquery.js",
                  "source_url": DEMO_URL, "source_scope": "multi_page",
                  "strength": "strong", "provenance": "local_crawl",
                  "pattern": r"/wp-includes/"},
             ], "limitations": []},
            {"category": "Ecommerce", "technology_name": "WooCommerce",
             "status": "UNKNOWN", "confidence": "Medium",
             "confidence_score": 0.55, "version": "Unknown",
             "detection_sources": [
                 {"signal_type": "url_pattern",
                  "signal_value": "/product/apple-sorter/",
                  "source_url": DEMO_URL, "source_scope": "single_page",
                  "strength": "medium", "provenance": "local_crawl",
                  "pattern": r"/product/"},
             ], "limitations": []},
            {"category": "SEO Technology", "technology_name": "Yoast SEO",
             "status": "UNKNOWN", "confidence": "Low",
             "confidence_score": 0.35, "version": "Unknown",
             "detection_sources": [
                 {"signal_type": "robots_meta",
                  "signal_value": "index, follow, max-image-preview:large",
                  "source_url": DEMO_URL, "source_scope": "multi_page",
                  "strength": "weak", "provenance": "local_crawl",
                  "pattern": r"max-image-preview:large"},
             ], "limitations": []},
            {"category": "Analytics", "technology_name": "GA4",
             "status": "DETECTED", "confidence": "High",
             "confidence_score": 0.82, "version": "Unknown",
             "detection_sources": [
                 {"signal_type": "analytics_fingerprint",
                  "signal_value": "ga4_id",
                  "source_url": DEMO_URL, "source_scope": "multi_page",
                  "strength": "strong", "provenance": "local_crawl",
                  "pattern": r"ga4_id"},
             ], "limitations": []},
        ],
        "risk_correlations": [],
        "detection_status": "COMPLETE",
        "limitations": [],
    }


def _readme(demo_date: str) -> str:
    return f"""UNIVERSAL MASTER SEO DIAGNOSTIC REPORT — 客户说明
Audit Date: {demo_date}

开始阅读：
  01_Master_SEO_Diagnostic_Report.docx（主报告，Word 可编辑）

各文件用途：
  01_Master_SEO_Diagnostic_Report.docx — 主交付报告
  04_Remediation_Tasks.csv — 整改任务清单
  05_Manual_Review.csv — 人工评审清单
  07_Audit_Score.json — 评分/覆盖/置信度
  08_80_Rule_Coverage.csv — 80 规则覆盖矩阵
  09_Technology_Profile.json — 网站技术画像
  metrics.json — 报告统计口径（唯一计数源）

结果含义：
  PASS — 已检查且健康，无需整改（可查看为什么通过及维护建议）。
  FAIL — 已确认问题，必须整改；每条均给出问题、位置、影响、动作、负责人与验收标准。
  WARNING — 需要关注并处理的风险/观测。
  OPPORTUNITY — 有证据支持的优化机会（非缺陷）。
  UNKNOWN / NOT_CHECKED — 当前证据不足，无法判定；报告会说明所需数据与如何完成检测。
  NOT_APPLICABLE — 该规则不适用于当前网站架构（附原因）。
  MANUAL_REVIEW_REQUIRED — 需要人工评审后才能判定。

整改工作流：
  1. 打开 01 报告 → “Remediation Priority Plan”/“Remediation Checklist”。
  2. 按 P0→P1→P2→P3 与负责人逐条执行。
  3. 在 Checklist 中把状态改为 In Progress → Fixed → Verified（Word 可编辑）。
  4. 完成后按 “Acceptance & Recheck” 复测：修复→spot-check→重跑审计→对比
     Result/Affected/Evidence/Score/Coverage→仅当验收标准满足才标记 Verified。

评分说明：
  Score = 已执行规则的加权健康度；Coverage = 实际完成检查的程度；
  Confidence = 结论可靠程度。Score 不是 Google 官方评分，也不是排名预测。

本报告为演示版（Synthetic Offline Dataset），不代表任何真实客户网站。
"""


def main() -> None:
    from audit_rules.docx_report import build_universal_docx
    from audit_rules.report_view import build_report_view

    demo_date = os.environ.get("DEMO_DATE", date.today().isoformat())
    out = REPO / "reports" / f"universal-demo-{demo_date}"
    out.mkdir(parents=True, exist_ok=True)
    items = _build_items()
    tasks = _tasks()
    metrics = _metrics()
    tech = _technology_profile()
    view = build_report_view(
        items, tasks, metrics, manual_rows=[{"audit_id": 53}],
        technology_profile=tech, technology_risks=[],
        domain=DEMO_URL, audit_date=demo_date, pages_crawled=228,
        run_metadata={"run_id": "universal-demo", "replay_sha256": ""},
    )
    docx_path = out / "01_Master_SEO_Diagnostic_Report.docx"
    build_universal_docx(
        str(docx_path), view_model=view,
        items=items, task_rows=tasks, metrics=metrics,
        result_counts=view.result_distribution,
        execution_counts=view.execution_distribution,
        manual_rows=[{"audit_id": 53, "rule": "搜索意图匹配",
                      "scope": "SITE", "status": "PENDING"}],
        schema_distribution={},
        technology_profile=tech, technology_risks=[],
        domain=DEMO_URL, audit_date=demo_date,
        site_name=DEMO_SITE_NAME, pages_crawled=228,
    )
    (out / "09_Technology_Profile.json").write_text(
        json.dumps(tech, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "07_Audit_Score.json").write_text(
        json.dumps({
            "schema_version": "audit-score-v1",
            "overall_score": metrics["score"],
            "coverage_pct": metrics["coverage_pct"],
            "confidence": {"label": "High", "pct": metrics["confidence_pct"]},
            "executed_rules": 61,
            "eligible_rules": 80,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "08_80_Rule_Coverage.csv").write_text(
        "audit_id,rule_id,execution_status,result_status\n"
        + "\n".join(
            f"{i+1},{_registry()[i+1].rule_id},{items[i]['execution']},"
            f"{items[i]['result']}" for i in range(80)) + "\n",
        encoding="utf-8")
    (out / "04_Remediation_Tasks.csv").write_text(
        "task_type,audit_id,priority,finding,remediation,owner,"
        "acceptance_criteria,status\n"
        + "\n".join(
            f"{t['task_type']},{t['audit_id']},{t['priority']},"
            f"\"{t['finding']}\",\"{t['remediation']}\",{t['owner']},"
            f"\"{t['acceptance_criteria']}\",{t['status']}"
            for t in tasks) + "\n",
        encoding="utf-8")
    (out / "05_Manual_Review.csv").write_text(
        "Audit ID,Rule,Scope,Why Manual,What To Review,Required Evidence,"
        "Pass Criteria,Status\n"
        "53,搜索意图匹配,SITE,搜索意图匹配需要人工判断,"
        "检查主要关键词落地页类型与 SERP 意图,人工评审工作表,"
        "主要关键词落地页类型与 SERP 意图明显一致,PENDING\n",
        encoding="utf-8")
    (out / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    (out / "README.txt").write_text(_readme(demo_date), encoding="utf-8")
    zip_path = out.with_name(f"universal-demo-{demo_date}.zip")
    files = sorted(p for p in out.rglob("*") if p.is_file())
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED,
                         compresslevel=6) as archive:
        for path in files:
            archive.write(path, path.relative_to(out).as_posix())
    print("demo dir:", out)
    print("zip:", zip_path)
    print("zip sha256:",
          hashlib.sha256(zip_path.read_bytes()).hexdigest())
    print("docx:", docx_path)


if __name__ == "__main__":
    main()
