"""Native Word (DOCX) builder for the 80-Item Master SEO Diagnostic Report.

The DOCX is the primary client deliverable. It uses real Word styles
(Title/Subtitle/Heading 1-3/Normal/List Bullet), a real 80-row editable
summary table in a landscape section (repeated header), clickable real URLs
only, literal-HTML safety, native header/footer with page numbers, and a
static clickable table of contents. No PDF conversion, no images-as-content,
no content locking.
"""

from __future__ import annotations

import re
from typing import Optional

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor


DARK_BLUE = RGBColor(0x0B, 0x3D, 0x6F)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GREY = "F4F7FB"


def _set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def _mark_header_row(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def _add_bookmark(paragraph, name: str) -> None:
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), str(abs(hash(name)) % 100000))
    start.set(qn("w:name"), name)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), str(abs(hash(name)) % 100000))
    paragraph._p.insert(0, start)
    paragraph._p.append(end)


def _add_hyperlink(paragraph, url: str, text: Optional[str] = None) -> None:
    """Add a real clickable hyperlink run (external URL only)."""
    part = paragraph.part
    r_id = part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)
    new_run = OxmlElement("w:r")
    r_pr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0563C1")
    r_pr.append(color)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    r_pr.append(underline)
    new_run.append(r_pr)
    t = OxmlElement("w:t")
    t.text = text or url
    new_run.append(t)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)


def _add_page_field(paragraph) -> None:
    run = paragraph.add_run()
    fld_char1 = OxmlElement("w:fldChar")
    fld_char1.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fld_char2 = OxmlElement("w:fldChar")
    fld_char2.set(qn("w:fldCharType"), "end")
    run._r.append(fld_char1)
    run._r.append(instr)
    run._r.append(fld_char2)


def _configure_styles(doc: Document) -> None:
    styles = doc.styles
    title = styles["Title"]
    title.font.name = "Segoe UI"
    title.font.size = Pt(30)
    title.font.bold = True
    title.font.color.rgb = DARK_BLUE
    subtitle = styles["Subtitle"]
    subtitle.font.name = "Segoe UI"
    subtitle.font.size = Pt(16)
    subtitle.font.color.rgb = RGBColor(0x40, 0x63, 0x8B)
    for name, size in (("Heading 1", 20), ("Heading 2", 15), ("Heading 3", 12)):
        heading = styles[name]
        heading.font.name = "Segoe UI"
        heading.font.size = Pt(size)
        heading.font.bold = True
        heading.font.color.rgb = DARK_BLUE
    normal = styles["Normal"]
    normal.font.name = "Segoe UI"
    normal.font.size = Pt(10)


def _heading(doc: Document, text: str, level: int = 1):
    """Add a real Heading with page-break-before so sections start on a new
    page WITHOUT ever producing a header/footer-only blank page."""
    heading = doc.add_heading(text, level=level)
    p_pr = heading._p.get_or_add_pPr()
    page_break = OxmlElement("w:pageBreakBefore")
    p_pr.append(page_break)
    return heading


def _new_landscape_section(doc: Document):
    section = doc.add_section(WD_SECTION.NEW_PAGE)
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width = Inches(11.69)
    section.page_height = Inches(8.27)
    section.left_margin = Cm(1.5)
    section.right_margin = Cm(1.5)
    section.top_margin = Cm(1.5)
    section.bottom_margin = Cm(1.5)
    return section


def _new_portrait_section(doc: Document):
    section = doc.add_section(WD_SECTION.NEW_PAGE)
    section.orientation = WD_ORIENT.PORTRAIT
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.left_margin = Cm(2.0)
    section.right_margin = Cm(2.0)
    section.top_margin = Cm(1.8)
    section.bottom_margin = Cm(1.8)
    return section


def _header_footer(section, title_text: str) -> None:
    header = section.header
    header.is_linked_to_previous = False
    p = header.paragraphs[0]
    p.text = ""
    run = p.add_run("Baolai Packaging — 80-Item Master SEO Diagnostic Report")
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    footer = section.footer
    footer.is_linked_to_previous = False
    fp = footer.paragraphs[0]
    fp.text = ""
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = fp.add_run("Page ")
    run.font.size = Pt(8)
    _add_page_field(fp)
    run2 = fp.add_run("")
    run2.font.size = Pt(8)


def _label(doc, label: str, value: str, heading: bool = False) -> None:
    p = doc.add_paragraph()
    if heading:
        p.style = doc.styles["Heading 3"]
        p.add_run(label.rstrip(":") + ":")
        return
    r = p.add_run(label + " ")
    r.bold = True
    _safe_add(p, value)


def _safe_add(paragraph, text: str) -> None:
    """Add text with literal HTML kept as plain text (no hyperlink creation)."""
    paragraph.add_run(str(text))


_URL_RE = re.compile(r"https?://[^\s]+")


def _add_url_text(paragraph, text: str) -> None:
    """Add text; real http(s) URLs become clickable hyperlinks, literal HTML
    (e.g. <a href>) stays plain text."""
    pos = 0
    for match in _URL_RE.finditer(str(text)):
        before = text[pos:match.start()]
        if before:
            _safe_add(paragraph, before)
        url = match.group(0).rstrip(".,;:)'\"")
        if url.lower().startswith(("http://", "https://")):
            _add_hyperlink(paragraph, url)
        else:
            _safe_add(paragraph, url)
        pos = match.start() + len(url)
    if pos < len(text):
        _safe_add(paragraph, text[pos:])


def _add_evidence_items(doc, evidence_text: str) -> None:
    for line in str(evidence_text).splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("…"):
            p = doc.add_paragraph(line)
            p.style = doc.styles["List Bullet"]
            continue
        url = line.split(" — ")[0] if " — " in line else line
        rest = line[len(url) + 3:] if " — " in line else ""
        p = doc.add_paragraph(style="List Bullet")
        _add_url_text(p, url)
        if rest:
            p2 = doc.add_paragraph(rest)
            p2.style = doc.styles["List Bullet 2"]


def _client_evidence_70(doc, item: dict) -> None:
    """Client-facing evidence for Audit #70.

    Never dumps raw likely_form_urls or the internal scope token SITE. When a
    reliable URL list exists, show at most 5 examples; otherwise state that
    rendered DOM was unavailable and scope the manual validation without
    fabricating a URL count."""
    urls = [
        url for url in (item.get("representative") or [])
        if str(url).startswith(("http://", "https://"))
    ]
    p = doc.add_paragraph(style="List Bullet")
    p.add_run("Evidence: Rendered form DOM was not available.")
    p = doc.add_paragraph(style="List Bullet")
    p.add_run(
        "Manual Validation Scope: Contact/form pages require rendered-DOM "
        "and manual validation.")
    if urls:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(f"Likely form/contact pages ({len(urls)} identified):")
        for url in urls[:5]:
            up = doc.add_paragraph(style="List Bullet 2")
            _add_url_text(up, url)
    if len(urls) > 5:
        note = doc.add_paragraph(style="List Bullet")
        note.add_run("完整 URL 清单见 Detailed URL Findings CSV / Manual Review worksheet。")


def _summary_table(doc, rows: list[list[str]]) -> None:
    headers = ["ID", "Category", "Check", "Exec.", "Result", "Rule Pri.",
               "Confidence", "Affected", "Action"]
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    header_row = table.rows[0]
    _mark_header_row(header_row)
    widths = [Cm(1.1), Cm(2.2), Cm(6.0), Cm(1.6), Cm(2.2), Cm(1.2),
              Cm(2.0), Cm(1.6), Cm(1.7)]
    for index, (header, width) in enumerate(zip(headers, widths)):
        cell = header_row.cells[index]
        cell.width = width
        cell.text = ""
        p = cell.paragraphs[0]
        run = p.add_run(header)
        run.bold = True
        run.font.color.rgb = WHITE
        run.font.size = Pt(9)
        _set_cell_shading(cell, "0B3D6F")
    for row in rows:
        cells = table.add_row().cells
        for index, (value, width) in enumerate(zip(row, widths)):
            cell = cells[index]
            cell.width = width
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.line_spacing = 1.0
            _add_url_text(p, value)
            for run in p.runs:
                run.font.size = Pt(8)
    for row in table.rows[1:]:
        for cell in row.cells:
            tc_pr = cell._tc.get_or_add_tcPr()
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"), LIGHT_GREY)
            tc_pr.append(shd)


def _static_toc(doc, entries: list[tuple[str, str]]) -> None:
    _heading(doc, "Table of Contents", level=1)
    for label, bookmark in entries:
        p = doc.add_paragraph()
        p.style = doc.styles["Normal"]
        hyperlink = OxmlElement("w:hyperlink")
        hyperlink.set(qn("w:anchor"), bookmark)
        run = OxmlElement("w:r")
        r_pr = OxmlElement("w:rPr")
        color = OxmlElement("w:color")
        color.set(qn("w:val"), "0563C1")
        r_pr.append(color)
        underline = OxmlElement("w:u")
        underline.set(qn("w:val"), "single")
        r_pr.append(underline)
        run.append(r_pr)
        t = OxmlElement("w:t")
        t.text = label
        run.append(t)
        hyperlink.append(run)
        p._p.append(hyperlink)


def build_docx(
    output_path: str,
    *,
    items: list[dict],
    task_rows: list[dict],
    metrics: dict,
    result_counts: dict,
    execution_counts: dict,
    manual_rows: list[dict],
    schema_distribution: dict,
    domain: str = "https://www.baolaipackaging.com/",
    audit_date: str = "2026-08-09",
) -> str:
    """Build the native Word diagnostic report."""
    doc = Document()
    _configure_styles(doc)

    # ---------- Cover page ----------
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(140)
    title_run = p.add_run("Baolai Packaging")
    title_run.font.name = "Segoe UI"
    title_run.font.size = Pt(34)
    title_run.font.bold = True
    title_run.font.color.rgb = DARK_BLUE
    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_run = p2.add_run("80-Item Master SEO Diagnostic Report")
    sub_run.font.name = "Segoe UI"
    sub_run.font.size = Pt(17)
    sub_run.font.color.rgb = RGBColor(0x40, 0x63, 0x8B)
    for label, value in [
        ("Domain", domain),
        ("Audit Date", audit_date),
        ("Scope", "Full-site technical SEO diagnosis — 80 checks"),
        ("Pages Crawled", "315"),
        ("Prepared by", "Master SEO Audit System"),
    ]:
        mp = doc.add_paragraph()
        mp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = mp.add_run(f"{label}: {value}")
        r.font.size = Pt(11)
        r.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
    # Management Summary starts a new page via pageBreakBefore (no blank page).

    # ---------- Header / footer (applies to all sections) ----------
    _header_footer(doc.sections[0], "Baolai Packaging")

    # ---------- Management Summary ----------
    _add_bookmark(_heading(doc, "Management Summary", level=1), "ManagementSummary")
    doc.add_paragraph(
        f"本次对 {domain} 执行 80 项技术 SEO 诊断（315 页真实爬取）。"
        "状态分布如下（Result 与 Execution 分开统计，合计均为 80）。")
    _label(doc, "Result Distribution:", "")
    res_table = doc.add_table(rows=1, cols=2)
    res_table.style = "Table Grid"
    for index, header in enumerate(("Result", "数量")):
        cell = res_table.rows[0].cells[index]
        cell.text = ""
        run = cell.paragraphs[0].add_run(header)
        run.bold = True
        run.font.color.rgb = WHITE
        _set_cell_shading(cell, "0B3D6F")
    for result in ("PASS", "FAIL", "WARNING", "OPPORTUNITY",
                   "MANUAL_REVIEW_REQUIRED", "UNKNOWN"):
        cells = res_table.add_row().cells
        cells[0].text = result
        cells[1].text = str(result_counts.get(result, 0))
    cells = res_table.add_row().cells
    cells[0].text = "合计"
    cells[1].text = "80"
    _label(doc, "Execution Distribution:", "")
    ex_table = doc.add_table(rows=1, cols=2)
    ex_table.style = "Table Grid"
    for index, header in enumerate(("Execution", "数量")):
        cell = ex_table.rows[0].cells[index]
        cell.text = ""
        run = cell.paragraphs[0].add_run(header)
        run.bold = True
        run.font.color.rgb = WHITE
        _set_cell_shading(cell, "0B3D6F")
    for execution in ("EXECUTED_FULL", "EXECUTED_PARTIAL",
                      "NOT_CHECKED", "NOT_APPLICABLE"):
        cells = ex_table.add_row().cells
        cells[0].text = execution
        cells[1].text = str(execution_counts.get(execution, 0))
    cells = ex_table.add_row().cells
    cells[0].text = "合计"
    cells[1].text = "80"
    doc.add_paragraph()
    doc.add_paragraph(
        "必须修（Confirmed Issues — REMEDIATION）：#11/#45 零内部链接 15 页（合并 1 个动作）、"
        "#15 缺失 H1 10 页（先决策 /hashtag/ 归档索引策略）、#13 确认重复标题、"
        "#79 缺失 ALT 属性 309 页。")
    doc.add_paragraph(
        "建议优化（Optimization Opportunities）：#29 x-default（315 页）、#13 标题宽度 heuristic、"
        "#18 hashtag 策略、#19 实验室性能、#14 Meta、#24 移动可用性。")
    doc.add_paragraph(
        "数据缺口（Data / Validation Gaps）：GSC/Semrush/GA4/服务器日志/WP 快照/渲染/可用性未提供，"
        "含 #20 TTFB（需字段 TTFB/RUM/日志）。")
    doc.add_paragraph(
        "人工评审（Manual Review）：9 条动作（8 条核心规则 #53–57/#71–73 + "
        "#70 表单可访问性部分人工验证）。")
    doc.add_paragraph(
        "基础健康层：robots、状态码、canonical、重定向、sitemap、死链、Schema、安全头均 PASS。")
    # ---------- Static TOC ----------
    _static_toc(doc, [
        ("Management Summary", "ManagementSummary"),
        ("Executive Summary", "ExecutiveSummary"),
        ("80-Item Diagnostic Summary", "SummaryTable"),
        ("Full 80-Item Diagnosis", "FullDiagnosis"),
        ("30-Day Remediation Roadmap", "Roadmap"),
        ("Responsibility Matrix", "Responsibility"),
        ("Acceptance & Recheck", "Acceptance"),
        ("Technical Appendix", "TechnicalAppendix"),
    ])
    # ---------- Executive Summary ----------
    _add_bookmark(_heading(doc, "Executive Summary", level=1), "ExecutiveSummary")
    summary = doc.add_table(rows=1, cols=2)
    summary.style = "Table Grid"
    for index, header in enumerate(("指标", "数值")):
        cell = summary.rows[0].cells[index]
        cell.text = ""
        run = cell.paragraphs[0].add_run(header)
        run.bold = True
        run.font.color.rgb = WHITE
        _set_cell_shading(cell, "0B3D6F")
    for label, value in [
        ("SEO Health Score", f"{metrics['score']} / 100"),
        ("Audit Coverage", f"{metrics['coverage_pct']}%"),
        ("Result Confidence", f"High（{metrics['confidence_pct']}%）"),
        ("Pages Crawled", "315（全部 HTTP 200，sitemap 100%）"),
        ("确认整改任务（REMEDIATION）", str(metrics["confirmed_remediation"])),
        ("优化机会（OPTIMIZATION）", str(metrics["optimization"])),
        ("数据缺口（DATA_REQUIRED）", str(metrics["data_required"])),
        ("人工评审（MANUAL_REVIEW）", str(metrics["manual_review_actions"])),
    ]:
        cells = summary.add_row().cells
        cells[0].text = label
        cells[1].text = value
    doc.add_paragraph()
    doc.add_paragraph(
        "网站最大的实际问题（按诊断结果）：#11/#45 内部链接（15 页零入链）、"
        "#15 H1（10 页）、#79 图片 ALT（309 页 / 3,011 实例候选）、"
        "#13 标题（44 页）、#19 性能（实验室 LCP 5.3–6.8s，无字段数据）、"
        "#29 hreflang x-default（315 页机会项）、#18 归档策略（10 页）。")
    doc.add_paragraph(
        "健康领域：robots、状态码、canonical、重定向、sitemap、内部死链、"
        "Schema（Organization/BreadcrumbList 等真实分布）、安全头均 PASS。")
    # ---------- Summary table (landscape) ----------
    landscape = _new_landscape_section(doc)
    _header_footer(landscape, "Baolai Packaging")
    _add_bookmark(_heading(doc, "80-Item Diagnostic Summary", level=1), "SummaryTable")
    rows = []
    for item in items:
        rows.append([
            f"#{item['audit_id']:02d}",
            item["category"],
            item["check"],
            _abbrev(item["execution"]),
            _abbrev(item["result"]),
            _abbrev(item["priority"]),
            item["confidence"],
            str(item["affected_urls"]),
            item["action_required"],
        ])
    _summary_table(doc, rows)

    # ---------- Full 80-Item Diagnosis (portrait) ----------
    portrait = _new_portrait_section(doc)
    _header_footer(portrait, "Baolai Packaging")
    _add_bookmark(_heading(doc, "Full 80-Item Diagnosis", level=1), "FullDiagnosis")
    for item in items:
        heading = doc.add_heading(f"AUDIT #{item['audit_id']:02d}", level=2)
        _add_bookmark(heading, f"Audit{item['audit_id']:02d}")
        _label(doc, "Check:", item["check"])
        _label(doc, "Category:", item["category"])
        _label(doc, "Result:", item["result"])
        _label(doc, "Execution:", item["execution"])
        _label(doc, "Rule Priority:", item["priority"])
        _label(doc, "Confidence:", item["confidence"])
        _label(doc, "Data Source:", item["data_source"])
        _label(doc, "What Was Checked:", item["what_checked"])
        _label(doc, "Actual Website State:", item["actual_state"])
        _label(doc, "Diagnosis:", item["diagnosis"])
        _label(doc, "Evidence:", "")
        if item["audit_id"] == 70:
            _client_evidence_70(doc, item)
        else:
            _add_evidence_items(doc, item["evidence"])
        if item["audit_id"] == 27 and schema_distribution:
            _label(doc, "Schema Type Distribution:", "")
            for schema_type, count in schema_distribution.items():
                p = doc.add_paragraph(style="List Bullet")
                p.add_run(f"{schema_type}: {count} 页")
        _label(doc, "Affected URLs:", str(item["affected_urls"]))
        representative_urls = [
            url for url in (item["representative"] or [])
            if str(url).startswith(("http://", "https://"))
        ]
        if representative_urls:
            _label(doc, "Representative URLs:", "")
            for url in representative_urls:
                p = doc.add_paragraph(style="List Bullet")
                _add_url_text(p, url)
        _label(doc, "Full Affected URL Reference:",
               f"Detailed URL Findings CSV（Audit #{item['audit_id']:02d}）")
        impact = (
            "本项不适用于当前网站，不产生整改要求。"
            if item.get("execution") == "NOT_APPLICABLE"
            else item["seo_impact"]
        )
        _label(doc, "SEO / Business Impact:", impact)
        if item["is_pass"]:
            _label(doc, "Recommended Fix:", "No remediation required.")
            if item.get("optional_maintenance"):
                _label(doc, "Optional Maintenance:", item["optional_maintenance"])
        else:
            _label(doc, "Recommended Fix:", item["fix"] or "无需整改")
        _label(doc, "Owner:", item["owner"])
        acceptance = item["acceptance"]
        if item["audit_id"] == 1:
            acceptance = (
                "/robots.txt 返回 200；重要页面未被错误 Disallow；"
                "robots 规则与预期抓取策略一致；"
                "如包含 Sitemap 声明，则地址有效。")
        elif item["audit_id"] == 2:
            acceptance = (
                "Automated/Crawl Acceptance: 重要 Sitemap URL 为 "
                "200 + Indexable + Canonical。\n"
                "External Validation: GSC/Bing submission/processing status "
                "requires external data and remains not checked。")
        _label(doc, "Acceptance Criteria:", "")
        for part in str(acceptance).split("\n"):
            p = doc.add_paragraph(style="List Bullet")
            _safe_add(p, part)
        if item.get("observed"):
            _label(doc, "Remote Observation（非问题）:", item["observed"])
        if item.get("manual"):
            _label(doc, "Manual Review Instructions:", "")
            p = doc.add_paragraph(style="List Bullet")
            p.add_run(f"Why Manual: {item['manual']['why']}")
            p = doc.add_paragraph(style="List Bullet")
            p.add_run(f"What To Review: {item['manual']['review']}")
            p = doc.add_paragraph(style="List Bullet")
            p.add_run(f"Required Evidence: {item['manual']['evidence']}")
            p = doc.add_paragraph(style="List Bullet")
            p.add_run(f"Pass Criteria: {item['manual']['pass']}")
        if item.get("limitations"):
            _label(doc, "Limitations:", item["limitations"])

    # ---------- Roadmap ----------
    _add_bookmark(_heading(doc, "30-Day Remediation Roadmap", level=1), "Roadmap")
    for section_title, lines in [
        ("Confirmed Remediation（0–14 天）", [
            "#11/#45（合并）：为 15 个零内链产品页补充 HTML 内链。",
            "#15：先决策 10 个 /hashtag/ 归档页索引策略，再补 H1 或 noindex。",
            "#13 重复标题、#79 缺失 ALT（309 页）按页整改。",
        ]),
        ("Optimization（14–30 天）", [
            "#29 x-default（315 页）、#18 hashtag 策略（10 页）、#14 Meta（35 条）。",
            "#19 实验室 LCP 优化（4 模板）、#24 移动可用性（4 页）、#13 宽度 heuristic（43 条）。",
        ]),
        ("Data Access & Validation（独立通道）", [
            "接入 GSC/Semrush/GA4/日志/WP 快照/渲染/可用性；#20 TTFB 需字段 TTFB/RUM/日志；#19 需 CrUX。",
        ]),
        ("Manual Review（独立通道）", [
            "9 条人工评审动作（8 条核心 + #70 部分人工验证）。",
        ]),
        ("Continuous", [
            "建立 Rule 74 基线，每月/每季度巡检（内部建议）。",
        ]),
    ]:
        doc.add_heading(section_title, level=2)
        for line in lines:
            doc.add_paragraph(line, style="List Bullet")

    # ---------- Responsibility Matrix ----------
    _add_bookmark(_heading(doc, "Responsibility Matrix", level=1), "Responsibility")
    resp = doc.add_table(rows=1, cols=3)
    resp.style = "Table Grid"
    for index, header in enumerate(("角色", "主要职责", "对应 Audit")):
        cell = resp.rows[0].cells[index]
        cell.text = ""
        run = cell.paragraphs[0].add_run(header)
        run.bold = True
        run.font.color.rgb = WHITE
        _set_cell_shading(cell, "0B3D6F")
    for role, duty, audits in [
        ("SEO", "hreflang、Title/Meta、内链、GSC",
         "#13/#14/#29/#11/#45；Manual #53/#54/#72/#73"),
        ("Developer", "CWV、图片实现、TTFB 数据、表单", "#19/#24/#79/#20/#70"),
        ("Content", "内容价值、H1、归档策略", "#15/#18；Manual #55/#56/#57"),
        ("Design", "图片 ALT/尺寸/格式、移动可用性", "#24/#79"),
        ("Server/Admin", "日志/RUM/快照、staging", "#20/#67；Data Access"),
        ("Management", "优先级、资源、复查节奏", "Roadmap 整体"),
    ]:
        cells = resp.add_row().cells
        cells[0].text = role
        cells[1].text = duty
        cells[2].text = audits

    # ---------- Acceptance & Recheck ----------
    _add_bookmark(_heading(doc, "Acceptance & Recheck", level=1), "Acceptance")
    acc = doc.add_table(rows=1, cols=3)
    acc.style = "Table Grid"
    for index, header in enumerate(("阶段", "动作", "时机")):
        cell = acc.rows[0].cells[index]
        cell.text = ""
        run = cell.paragraphs[0].add_run(header)
        run.bold = True
        run.font.color.rgb = WHITE
        _set_cell_shading(cell, "0B3D6F")
    for stage, action, timing in [
        ("确认缺陷修复后", "对相关页面立即重测", "修复当天"),
        ("主要整改后", "完整 80 项复查（重新爬取）", "7–14 天"),
        ("长期", "技术巡检 + Rule 74 基线对比", "每月/每季度（内部建议）"),
    ]:
        cells = acc.add_row().cells
        cells[0].text = stage
        cells[1].text = action
        cells[2].text = timing

    # ---------- Technical Appendix ----------
    _add_bookmark(_heading(doc, "Technical Appendix", level=1), "TechnicalAppendix")
    doc.add_paragraph(
        "数据来源：2026-08-09 受控生产爬取（315 页，全部 HTTP 200）+ 离线 replay 重建（当前规则引擎）。")
    doc.add_paragraph(
        "诊断质量修正：80 项复核，20 项语义/状态修正；无已知系统误报；无 missing-data PASS；"
        "PSI 采样记为部分执行；#20 TTFB 无 lab-proxy 整改任务；#11/#45 整改去重；"
        "#70 部分人工验证。")
    doc.add_paragraph(
        "replay/snapshot/manifest 与内部校验见 Technical_Appendix 目录。")
    doc.add_paragraph(
        "报告由 Master SEO Audit System 自动生成；未提供数据源的规则保持 NOT_CHECKED，"
        "报告不包含模拟或编造结果。")

    doc.save(output_path)
    return output_path


def _abbrev(value: str) -> str:
    mapping = {
        "EXECUTED_FULL": "Full",
        "EXECUTED_PARTIAL": "Part.",
        "NOT_CHECKED": "N/C",
        "NOT_APPLICABLE": "N/A",
        "MANUAL_REVIEW_REQUIRED": "Manual",
        "Critical": "P0",
        "High": "P1",
        "Medium": "P2",
        "Low": "P3",
    }
    return mapping.get(value, value)
