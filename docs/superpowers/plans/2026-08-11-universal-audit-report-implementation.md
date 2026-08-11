# Universal Master SEO Diagnostic Report — Implementation Plan

**Goal:** productize the audit report into one universal, client-safe,
actionable DOCX contract driven by a report view model; keep all 80 rules and
approved SEO/Technology semantics unchanged.

**Architecture:**

```text
diagnostic data (coverage/findings/tasks/tech profile/replay)
  → ReportViewModel (labels, scopes, grouping, client-safe evidence)
  → Universal DOCX renderer (fixed 15-section structure)
  → export package (01_Master_SEO_Diagnostic_Report.docx + artifacts)
```

**Tech stack:** existing Python `audit_rules` + `python-docx`; no new
dependencies. `REPORT_FORMAT=docx` default; `REPORT_AUDIENCE=client|internal`.

**Global constraints:**
- exactly 80 rules; no Audit #81; no SEO/score/technology-semantic changes
- no third live site; no gelgoogsort re-crawl; no client overfitting
- current-run data only; no cross-client leakage; no domain hardcode
- client-safe output (no raw internals/paths/tokens/other clients)
- strict TDD per task: failing test → implementation → pass → regression →
  commit
- worktree: `D:\ai\deepseek_project\librecrawl-universal-report` on
  `feat/universal-audit-report-v1`; no merge

---

## Task A — Report view model

**Goal:** `audit_rules/report_view.py` owns presentation decisions.

Interfaces:
- `build_report_view(...)` → `ReportViewModel` with: management summary
  buckets, key findings (FAIL/WARNING/high-value OPPORTUNITY, Top 10–15),
  remediation priority plan rows, actionable audit items (6 self-check
  questions), checklist rows, scope summaries, score explanation,
  report metadata (schema/template versions, run identity).
- current-run provenance: every count from current coverage/tasks/replay.

Tests: `universal_report_always_has_80_audits`,
`management_summary_has_all_buckets`, `key_findings_only_fail_warning_opportunity`,
`remediation_plan_answers_6_questions`, `score_explanation_present`,
`report_template_version_present`, `report_identity_uses_current_run`.

## Task B — Universal DOCX renderer

**Goal:** fixed 15-section DOCX with the new sections.

Interfaces: extend `audit_rules/docx_report.py` with
`build_universal_docx(...)` (or a `universal` mode) rendering Cover,
Management Summary, Executive Summary, Technology Profile, Technology Risks,
Key Findings, Remediation Priority Plan, 80-Item Summary, Full #01–80,
Remediation Checklist, Manual Review, Roadmap, Responsibility Matrix,
Acceptance & Recheck, Technical Appendix.

Tests: `universal_report_contains_management_summary`,
`universal_report_contains_key_findings`,
`universal_report_contains_remediation_plan`,
`universal_report_contains_remediation_checklist`,
`universal_report_contains_manual_review`,
`universal_report_contains_recheck_workflow`,
`pass_rule_contains_evidence`, `fail_rule_contains_action`,
`fail_rule_contains_acceptance`, `not_checked_contains_required_data`,
`not_applicable_contains_reason`, `representative_urls_are_bounded`,
`large_findings_are_compacted`, `docx_long_urls_wrap`,
`docx_no_blank_page_regression`, `docx_80_heading_regression`.

## Task C — REPORT_AUDIENCE modes

`client` (default) and `internal`; identical diagnosis results.

Tests: `client_and_internal_views_share_same_results`,
`client_report_hides_internal_paths`, `client_report_hides_raw_dicts`,
`client_report_hides_tokens`, `client_report_hides_other_clients`.

## Task D — Language/label layer

Central label map (zh-CN phase 1) with future en-US hooks; no Chinese strings
inside diagnosis logic.

Tests: `report_labels_are_unified` (no half-Chinese/half-English mixed labels),
`label_layer_supports_language_keys`.

## Task E — Client safety + current-run isolation

- shareable-safety scan helper over the generated DOCX text: local paths,
  tokens, secrets, raw dicts, internal placeholders, other fixture domains,
  debug markers, TODO/TBD, NoneType, example placeholders.
- isolation contract: view model only consumes current-run inputs.

Tests: `shareable_safety_scan_passes_client_docx`,
`sequential_reports_do_not_leak_client_state`,
`current_run_metrics_only`.

## Task F — Generic fixtures + cross-site tests

Offline fixtures: `generic_wordpress_site`, `generic_nonwordpress_site`,
`multilingual_site`, `single_language_site`, `site_with_failures`,
`healthy_site`, `site_with_missing_external_data`, `technology_unknown_site`,
`large_issue_count_site`. Same template renders all.

Tests: `generic_fixtures_all_render`, `sequential_reports_do_not_leak_client_state`
(Site A → Report A, Site B → Report B; no A data in B).

## Task G — Skill + AGENTS

`skills/universal-seo-report/SKILL.md` + `AGENTS.md` invariants; docs-only.

Tests: `skill_doc_exists`, `agents_invariants_present` (updated).

## Task H — Universal demo report

Generate `01_Master_SEO_Diagnostic_Report.docx` from an offline fixture into a
demo package; no live calls.

Tests: `demo_package_contains_universal_docx`,
`demo_package_contains_09_technology_profile`.

## Task I — Full regression + final acceptance

`python -m pytest tests/ -q` (0 failed), rule count == 80, hardcode scan,
push `feat/universal-audit-report-v1`, CI green. Final 58-item response.
No merge.

---

## Test coverage mapping (spec item 50)

All named tests from the spec are assigned to Tasks A–I above.
