# Universal Master SEO Diagnostic Report — Product Design Spec

**Status:** Approved (user final approval) · **Date:** 2026-08-11
**Scope:** report contract / UX / remediation usability / cross-site
genericity / client-safe output / regression protection.

---

## 1. Goal

Turn the current audit reporting system into a **universal product**:
any website URL → crawl → Technology Intelligence → 80 Rules → Findings →
Remediation → DOCX, all producing the **same** universal, executable,
verifiable, shareable, client-safe diagnostic report.

The default client deliverable is:

`01_Master_SEO_Diagnostic_Report.docx`

## 2. One Universal Report Contract

There is exactly **one** report structure. Site technology, page scale,
language, CMS, and issue counts affect **content/data only** — never the
report architecture.

Fixed DOCX structure:

1. Cover
2. Management Summary
3. Executive Summary
4. Website Technology Profile
5. Technology Risks & Recommendations
6. Key Findings / What Needs Attention
7. Remediation Priority Plan
8. 80-Item Diagnostic Summary
9. Full Audit #01–80
10. Remediation Checklist
11. Manual Review Required
12. 30-Day Remediation Roadmap
13. Responsibility Matrix
14. Acceptance & Recheck
15. Technical Appendix

Exactly 80 audits are always present. No Audit #81.

## 3. Default Client Deliverable

- Client primary deliverable: `01_Master_SEO_Diagnostic_Report.docx`
  (`REPORT_FORMAT=docx` remains the default).
- Internal artifact directory keeps the numbered artifacts:
  `02_80_Item_Diagnostic_Matrix.xlsx`, `03_Detailed_URL_Findings.csv`,
  `04_Remediation_Tasks.csv`, `05_Manual_Review.csv`,
  `06_Performance_Data.csv`, `07_Audit_Score.json`,
  `08_80_Rule_Coverage.csv`, `09_Technology_Profile.json`,
  `Technical_Appendix/`, `README.txt`, Final ZIP.
- Export package directory convention:
  `reports/<site>-seo-audit-<date>/` with the generic filenames above
  (no client-specific product name in report filenames).

## 4. Management Summary (2–3 minute read)

Non-technical audience. Answers:

- How is the site overall?
- How many issues are there?
- What are the most important ones?
- What is already healthy?
- What cannot be judged yet and why?
- What to do first?

Shows: SEO Health Score, Coverage, Confidence, Pages Crawled, Confirmed
Issues, Warnings, Optimization Opportunities, Manual Review, Data Required.
Execution/Result may remain but with human explanation.

## 5. Key Findings / What Needs Attention (new)

Auto-derived from the 80 rules — never free-form AI. Shows only FAIL,
WARNING, and confirmed high-value OPPORTUNITY (never all PASS). Up to
Top 10–15, ranked by real Rule Priority + Result + Affected Scope + Impact.
Columns: Priority · Audit · Issue · Why It Matters · Affected Scope ·
Recommended Action.

## 6. Remediation Priority Plan (new)

The user-facing "what do I fix first" section. Table:

Order · Priority · Audit # · Problem · Affected URLs/Scope · What To Do ·
Owner · How To Verify · Status

Organized by P0/P1/P2/P3 and REMEDIATION / OPTIMIZATION / DATA_REQUIRED /
MANUAL_REVIEW.

## 7. Actionable Audits (#01–80)

Every audit includes:

- Audit ID, Check, Category, Result, Execution, Rule Priority, Action
  Priority, Confidence, Data Source
- What Was Checked
- Actual Website State (real current state: pages checked, problems found,
  main problem types)
- Diagnosis
- Evidence (representative; full evidence in artifacts)
- Affected Scope (e.g. "2 pages", "199 pages", "site-wide", "sampled 5/228",
  "not checked")
- Representative URLs (bounded, never hundreds)
- Why This Matters (SEO + business, human language)
- What To Do (executable)
- Implementation Guidance (only when appropriate; never assume unknown
  client backend)
- Owner
- How To Verify / Acceptance Criteria
- Limitations / Missing Data (when applicable)

## 8. PASS / UNKNOWN / N/A Semantics

- **PASS** is never just "No remediation required": it states what was
  checked, why it passes, the evidence, what to maintain, and how to recheck.
- **UNKNOWN / NOT_CHECKED** is not written like a failure: it states Not
  verified, the reason, the required data (GSC/GA4/Server Logs/WordPress
  Admin/Rendered DOM/Manual Review), and how to complete the check.
- **NOT_APPLICABLE** keeps the 80-row slot but states why (e.g. "Site is not
  WordPress", "No multilingual structure detected").

## 9. Technology Profile & Risks

- Keep the approved Website Technology Profile fields: Category, Technology,
  Status, Version, Confidence, Evidence.
- Semantics: DETECTED / UNKNOWN / NOT_DETECTED / CONFLICTING; Technology ≠
  Issue; Low confidence ≠ confirmed; UNKNOWN observations may display but
  must be labeled Not Confirmed; full evidence in `09_Technology_Profile.json`.
- Technology Risks & Recommendations shows only confirmed observations and
  confirmed risk correlations. UNKNOWN candidates are never presented as a
  confirmed stack. Neither section independently deducts score.

## 10. Client-Safe Output

The DOCX must never contain:

- raw Python dicts, raw JSON, internal enum dumps, internal scope tokens,
  "SITE", "likely_form_urls", debug text, stack traces
- local Windows paths (`D:\...`, `C:\...`), API keys, tokens,
  Authorization, Cookie/Set-Cookie values
- internal filenames (except intentional artifact references)
- other clients' domain/brand/page-count/technology/metrics

## 11. Cross-Client Isolation (product blocker)

Any audit run may only use: current run, current replay, current provider
evidence, current site metadata. Never: fallback to previous client state,
module-global caches of client data, static previous-site counts, historical
default domains. Every number in the report (pages crawled, sitemap count,
affected URLs, schema count, internal links, image count, performance
sample, technology signals) comes from the current-run artifact.

## 12. Report Audience Modes

`REPORT_AUDIENCE` supports at least `client` (default) and `internal`.

- client: safe, no raw internals/debug/local paths; never hides real issues.
- internal: may show more technical provenance and artifact references; still
  forbids secrets/tokens.
- Same diagnosis results in both modes — presentation differs, SEO Result
  never differs.

## 13. Report Language / Label Layer

Phase 1: unify heading/label/explanation language style of the Chinese
report; technical terms (Canonical, hreflang, CWV, GA4, WordPress) may stay
English. Architecture must allow future `zh-CN` / `en-US` without scattering
Chinese strings into diagnosis logic.

## 14. Self-Check Design (6 questions)

Every confirmed FAIL/WARNING must answer:

- WHAT IS WRONG?
- WHERE IS IT?
- WHY DOES IT MATTER?
- HOW DO I FIX IT?
- WHO SHOULD FIX IT?
- HOW DO I KNOW IT IS FIXED?

If a confirmed issue cannot answer a key question, the report is not
client-ready.

## 15. Remediation Checklist

A Word-editable checkbox table auto-generated from tasks:

☐ · Audit · Priority · Problem · Scope · Action · Owner · Verification · Status

Status starts Open; users can edit to In Progress / Fixed / Verified. The
generator needs no database state management.

## 16. Task Aggregation

Do not duplicate one root cause across multiple audits (e.g. #11/#45 orphan
internal linking share one remediation action). Keep existing task
aggregation.

## 17. Priority Semantics

Keep Rule Priority distinct from Action Priority. Critical Rule + PASS =
healthy; Critical Rule + NOT_CHECKED = high-priority data gap; Critical Rule
+ FAIL = high-priority remediation. The report explains this.

## 18. Score Explanation

Add "How To Read The Score": Score = health of executed rules; Coverage =
how much was actually checked; Confidence = reliability of conclusions.
Explicitly: Score is not a Google official score and not a ranking
prediction.

## 19. Performance Reporting

Field Data ≠ Lab Data; Sample ≠ Full Site; PSI Error ≠ SEO defect; TBT ≠
INP; no CrUX → no Field CWV Pass claim. Client-facing interpretation keeps
these distinctions.

## 20. Roadmap / Responsibility / Recheck

- 30-Day Roadmap is generated from current tasks (Immediate 0–7, Short Term
  8–14, Medium Term 15–30) — no hardcoded client content.
- Responsibility Matrix aggregates by Owner (SEO, Developer, Content,
  Analytics, Infrastructure, Security, Product, Management); no empty role
  spam when a role has no tasks.
- Acceptance & Recheck is a real recheck workflow: fix → spot-check affected
  URLs → re-run audit → compare Result/Affected Count/Evidence/Score/Coverage
  → Verified only when Acceptance Criteria are truly met.

## 21. Report Identity & Provenance

- Site Name / Domain / Audit Date / Pages Crawled are all current-run driven;
  when site name cannot be reliably determined, use the hostname. No other
  client fallback.
- Machine metadata adds `report_schema_version` and `report_template_version`
  (values per existing conventions; no git tag created).
- Technical Appendix metadata: audit run ID, source URL, audit date, rule
  definition version, technology detector version, technology registry
  version, report template version, replay SHA (when available).

## 22. View Model / Template Separation

Diagnostic data → report view model → DOCX renderer. The rule engine never
carries Word layout logic. A `ReportViewModel` (or equivalent) owns human
labels, scope summaries, task grouping, client-safe evidence, action
summaries, and score explanation.

## 23. Backward Compatibility

80 Rules, Technology Intelligence, Replay, and existing artifacts must keep
working; old calling conventions stay compatible where practical. The
default client report switches to the Universal Master SEO Diagnostic
Report.

## 24. Skill & AGENTS

- `skills/universal-seo-report/SKILL.md` constrains agent behavior: client-safe,
  current-run-only, exactly 80 rules, evidence-first, actionable remediation,
  no cross-client leakage, no hidden missing data, no domain hardcode,
  shareable output.
- `AGENTS.md` gains the long-term invariants.
- The skill is behavior guidance only — real capability lives in Engine /
  ViewModel / DOCX generator / Artifacts / Tests.

## 25. Non-Negotiables

- Do not redesign the 80 rules, add Audit #81, redesign Technology
  Intelligence, re-crawl gelgoogsort, start a third live site, or change
  approved SEO semantics.
- Report presentation never changes Rule Result / Coverage / Score / Finding.
- Do not overfit existing clients (no `if baolai`, `if gelgoog`, `if
  page_count == 228`, etc.).
