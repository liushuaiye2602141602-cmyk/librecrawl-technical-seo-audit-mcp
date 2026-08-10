# Technology Intelligence — Implementation Plan

**Date:** 2026-08-10
**Status:** Plan (approved design: `docs/superpowers/specs/2026-08-09-technology-intelligence-design.md`, commit `0bbd097`)
**Product:** Website Technology Intelligence (client section: Website Technology Profile + Technology Risks & Recommendations)

---

## Goal

Implement the approved Website Technology Intelligence layer as a clean,
isolated capability of the Master SEO Audit System: crawl-time evidence
acquisition (safe header allowlist, script/css/meta-generator signals),
declarative signature detection, confidence semantics, CMS/applicability
bridge, risk correlation to existing Audit #01–#80, machine artifact, replay
support, DOCX sections, Skill/AGENTS boundaries, and cross-site regression —
without creating Audit #81, without changing the 80-rule contract, without
requiring external enrichment, and without any domain-specific logic.

## Architecture

```
LibreCrawl export (+ allowlisted headers/scripts/stylesheets/meta generator)
  -> PageContext normalization (audit_rules/context.py)
  -> Technology Intelligence Layer (audit_rules/technology/)
       LocalTechnologyDetector (signatures from registry)
       TechnologyProfile / TechnologyDetection / TechnologyEvidence / TechnologyRisk
       TechnologyRiskCorrelator
       OptionalTechnologyEnrichmentProvider (contract only, v1 no-op)
  -> CMS/applicability bridge (coverage.py _check_applicability, SiteContext.site_profile)
  -> Existing Audit #01–#80 findings (unchanged contract)
  -> 09_Technology_Profile.json (machine artifact)
  -> DOCX sections (Website Technology Profile / Technology Risks & Recommendations)
  -> Replay: source evidence persisted, offline reconstruction
```

## Tech Stack

- Python 3.12 (supported range), stdlib + existing deps (`httpx`, `pydantic` via
  settings, `python-docx` for DOCX, `pytest`).
- New module package: `audit_rules/technology/` (models, signatures, detector,
  risks, enrichment, artifact).
- Reuse: `audit_rules/context.py` (PageContext/SiteContext),
  `audit_rules/providers/base.py` (DataProvider contract),
  `audit_rules/replay.py` (sanitizer + replay schema + parity),
  `audit_rules/coverage.py` (applicability gate),
  `audit_rules/docx_report.py` (data-driven DOCX builder),
  `audit_rules/reporting.py`, `server.py EXPORT_FIELDS`, `tests/phase12/`.

## Global Constraints

- **Audit count remains exactly 80.** No Audit #81; no new rule in the registry.
- Technology Detection ≠ SEO Finding; Technology Detection ≠ vulnerability.
- Evidence-first: every detection carries structured evidence; `Unknown` is
  allowed; guessing is forbidden.
- Status semantics: `DETECTED` (sufficient evidence) / `NOT_DETECTED`
  (no supporting evidence observed; never "definitely absent") /
  `UNKNOWN` (insufficient/conflicting/uncollectable) / `CONFLICTING`
  (multiple credible mutually-exclusive judgments).
- Low-confidence detection must not drive Audit applicability; the
  applicability threshold is typed (see Task E).
- Local-first; external enrichment is interface-only in v1 and never blocks
  audit/DOCX.
- No domain-specific production logic (`baolaipackaging.com`,
  `gelgoogsort.com`, `yashengcrafts.com`, …).
- Missing data never becomes PASS; replay never calls live APIs; no raw
  sensitive header/cookie values in artifacts or reports.
- Technology Profile and Technology Risk do not directly affect SEO score;
  only Findings confirmed by existing Audit #01–#80 enter the existing score.
- Crawl cost control: no per-page extra requests; export-field reuse first;
  any site-level probe is bounded, cached, polite (≤3 URLs, one-shot).
- The current uncommitted second-site acceptance changes
  (`audit_rules/docx_report.py`, `tests/phase12/test_docx_report.py`,
  `docs/SECOND_SITE_GENERALIZATION_REVIEW.md`) are preserved untouched;
  implementation runs on an isolated feature branch/worktree.
- Each Task follows TDD: failing test → verify FAIL → minimal implementation →
  verify PASS → relevant regression → commit.

---

## Task A — Safe crawl evidence acquisition

**Goal:** Collect allowlisted response headers plus script/css/meta-generator
signals from already-downloaded HTML without extra crawl load, sanitize
sensitive values, and persist them through replay.

**Files:**
- Modify `server.py` — extend `EXPORT_FIELDS` with `response_headers`,
  `scripts`, `stylesheets`, `meta_generator`.
- Modify `audit_rules/context.py` — add PageContext fields
  `allowlisted_headers: Optional[dict]`, `scripts: list[str]`,
  `stylesheets: list[str]`, `meta_generator: Optional[str]`; normalize from raw
  export; apply the header allowlist at parse time.
- Modify `audit_rules/providers/librecrawl_provider.py` — map the new export
  fields into PageContext.
- Modify `audit_rules/replay.py` — add the four fields to `REPLAY_PAGE_FIELDS`
  and reuse the existing sensitive-value sanitizer for headers.
- Test: create `tests/phase12/test_technology_evidence_acquisition.py`.

**Interfaces:**
- Consumes: LibreCrawl export dict; existing `server.EXPORT_FIELDS` mechanism;
  `audit_rules.replay` sanitizer (`_contains_credentials` / sanitize paths).
- Produces: normalized `PageContext.allowlisted_headers/scripts/stylesheets/
  meta_generator`; replay-safe serialization.

**Header allowlist (final set = union of existing consumers + TI needs; only
these survive):** `server`, `via`, `x-powered-by`, `cf-ray`,
`cf-cache-status`, `x-cache`, `x-served-by`, `cache-control`,
`strict-transport-security`, `content-security-policy`, `x-generator`.
Everything else is dropped. **Forbidden always:** `authorization`,
`cookie`, `set-cookie` (values), session/auth/API tokens, credentials,
personal identifiers.

**Steps:**
1. Write failing tests: `safe_headers_only_are_persisted`,
   `sensitive_headers_are_never_persisted`,
   `set_cookie_values_are_not_persisted`,
   `source_html_scripts_are_detected_without_rendered_dom`,
   `source_html_stylesheets_are_detected_without_rendered_dom`,
   `meta_generator_is_detected`, `replay_preserves_allowlisted_technology_fields`.
2. Run and verify FAIL.
3. Minimal implementation: export-field extension, PageContext normalization,
   allowlist filter, replay allowlist registration.
4. Run and verify PASS.
5. Relevant regression: `tests/test_context.py`, `tests/phase12/
   test_replay_*.py` (page allowlist + sanitizer tests).
6. Commit: `feat: acquire safe technology evidence from crawl`.

**Crawl cost control:** no new requests per page. If LibreCrawl does not
return `response_headers`, the detector marks header-based signals
`NOT_DETECTED` (headers not collected), and an optional site-level probe
(homepage only, ≤3 URLs, cached for the audit) may fill the gap — gated by a
feature flag default off.

---

## Task B — Technology data contracts

**Goal:** Define typed models for evidence, detection, profile, and risk with
explicit detection-status and version semantics.

**Files:**
- Create `audit_rules/technology/__init__.py` (package exports).
- Create `audit_rules/technology/models.py`.
- Test: create `tests/phase12/test_technology_contracts.py`.

**Interfaces:**
- Consumes: existing `Finding`/`CoverageRow` naming conventions;
  `audit_rules.categories` enums for display labels.
- Produces: `TechnologyEvidence`, `TechnologyDetection`, `TechnologyProfile`,
  `TechnologyRisk`, statuses (`DETECTED/NOT_DETECTED/UNKNOWN/CONFLICTING`),
  and version fields (`schema_version`, `detector_version`,
  `signature_registry_version`).

**Steps:**
1. Write failing tests: `technology_profile_always_present`,
   `technology_detection_requires_evidence`,
   `not_detected_is_not_reported_as_definitely_absent`,
   `technology_artifact_contains_detector_version`,
   `technology_artifact_contains_registry_version`,
   `unknown_technology_not_guessed`, `conflicting_signals_reduce_or_flag_confidence`.
2. Run and verify FAIL.
3. Minimal implementation: dataclasses per the approved spec §4/§5 plus the
   four statuses and version fields.
4. Run and verify PASS.
5. Relevant regression: `tests/test_registry_integrity.py` (no new rule).
6. Commit: `feat: add technology data contracts`.

---

## Task C — TechnologySignatureRegistry

**Goal:** Declarative, testable signature registry; no scattered string checks;
no domain patterns.

**Files:**
- Create `audit_rules/technology/signatures.py` (registry load/validate/
  lookup, conflict detection).
- Create `audit_rules/technology/signature_data.py` (v1 signatures).
- Test: create `tests/phase12/test_technology_signatures.py`.

**Interfaces:**
- Consumes: signature definitions (technology, category, signal type,
  pattern, strength, version extractor, negative signals, confidence
  contribution, applicability requirement).
- Produces: validated signature table; `no_domain_patterns` guarantee.

**v1 signature breadth (correctness > quantity; breadth is not an acceptance
criterion):** WordPress, WooCommerce, Shopify, Webflow, Avada, Astra,
Elementor, Yoast, Rank Math, GA4, GTM, Meta Pixel, Cloudflare, nginx, Apache,
LiteSpeed, jQuery, and common forms/cache/CMP signatures only where evidence
is reliably obtainable from the v1 signal set.

**Steps:**
1. Write failing tests: `signature_registry_loads_declarative_signatures`,
   `signature_patterns_are_technology_scoped_not_domain_scoped`,
   `signature_strength_contributes_to_confidence`,
   `version_extractor_only_with_reliable_evidence`,
   `negative_signals_lower_or_flag_confidence`,
   `conflicting_signals_are_not_silently_overwritten`.
2. Run and verify FAIL.
3. Minimal implementation: registry loader/validator + v1 signature data.
4. Run and verify PASS.
5. Relevant regression: detector tests (Task D) reuse the registry; no change
   to `audit_rules/registry.py` (80-rule registry is separate).
6. Commit: `feat: add technology signature registry`.

---

## Task D — LocalTechnologyDetector

**Goal:** Deterministic local detection with evidence aggregation, confidence,
version, statuses, and graceful failure.

**Files:**
- Create `audit_rules/technology/detector.py`.
- Modify `audit_rules/integration.py` — run the detector after contexts are
  built and inject `existing_data["technology_profile"]`.
- Test: create `tests/phase12/test_technology_detector.py`.

**Interfaces:**
- Consumes: `list[PageContext]`, `SiteContext`, `TechnologySignatureRegistry`;
  optional replay document for offline mode.
- Produces: `TechnologyProfile` with detections/statuses/limitations; sets
  `site_profile` signal for Task E.

**Confidence rules (locked):** 2+ independent strong signals → High; 1 strong
signal → Medium/High per signature; weak single signal → Low; ordinary string
hit never → confirmed; conflicting signals lower confidence or surface
`conflicting_signals`; detector exception → profile `DETECTION_INCOMPLETE`
with reason, audit continues.

**Steps:**
1. Write failing tests: `technology_detection_requires_evidence`,
   `confidence_requires_signal_strength`,
   `version_unknown_when_not_provable`,
   `detector_failure_marks_profile_incomplete_not_audit_failure`,
   `detection_from_replay_does_not_call_network`.
2. Run and verify FAIL.
3. Minimal implementation: detector + profile assembly + integration wiring.
4. Run and verify PASS.
5. Relevant regression: `tests/phase12/test_replay_*.py`,
   `tests/test_integration.py` (existing_data shape).
6. Commit: `feat: add local technology detector`.

---

## Task E — CMS/applicability bridge

**Goal:** High/Medium/Low confidence drives Audit #36–39/#64–69 applicability
per the typed contract; never auto-PASS.

**Files:**
- Modify `audit_rules/context.py` — `SiteContext.site_profile` may be set to
  `"wordpress_remote"` from a High-confidence WordPress detection.
- Modify `audit_rules/coverage.py` — `_check_applicability` treats
  `site_profile in ("wordpress", "wordpress_remote")` as applicable for the
  WP rule set; a typed `applicability_requirement` on the WordPress signature
  defines the Medium-confidence combination (e.g., ≥2 strong signals);
  Low confidence is observation-only.
- Modify `audit_rules/integration.py` — wire the detector before coverage.
- Test: create `tests/phase12/test_technology_applicability.py`.

**Interfaces:**
- Consumes: `TechnologyProfile`, `site_profile`, `coverage.py` gate.
- Produces: correct `NOT_APPLICABLE` → Applicable transitions; rules without
  privileged data remain `NOT_CHECKED`/`EXECUTED_PARTIAL`/
  `MANUAL_REVIEW_REQUIRED`.

**Steps:**
1. Write failing tests: `cms_detection_controls_rule_applicability`,
   `wordpress_detection_does_not_auto_pass_privileged_rules`,
   `low_confidence_cms_does_not_drive_applicability`,
   `medium_confidence_requires_registry_defined_combo`,
   `generic_cms_profile_keeps_wp_rules_not_applicable`.
2. Run and verify FAIL.
3. Minimal implementation: profile→site_profile bridge + coverage gate +
   applicability requirement in the WordPress signature.
4. Run and verify PASS.
5. Relevant regression: `tests/test_coverage_manager.py`,
   `tests/test_execution_truth.py`.
6. Commit: `feat: bridge technology detection to CMS rule applicability`.

---

## Task F — TechnologyRiskCorrelator

**Goal:** Observation vs risk vs finding; map to existing audits; no #81; no
direct or double score penalty.

**Files:**
- Create `audit_rules/technology/risks.py`.
- Test: create `tests/phase12/test_technology_risks.py`.

**Interfaces:**
- Consumes: `TechnologyProfile`, existing `CoverageRow`s.
- Produces: `list[TechnologyRisk]` (classification
  `CONFIRMED_OBSERVATION|RISK_CANDIDATE|NO_RISK`, `mapped_audit_ids`).

**Mapping table (v1):** WordPress → #36–39/#64–69 (applicability, via Task E);
multiple SEO output sources/conflicting canonical-meta → #37/#8; duplicated
GA4/GTM loader → #34/#35; CDN/cache evidence → #23/#26/#66; schema-generator
provenance → #27/#28/#78; rendered-JS dependency → #46/#48 (optional);
form technology → #70/#71.

**Steps:**
1. Write failing tests: `technology_detected_is_not_automatic_risk`,
   `technology_risk_maps_to_existing_rule`,
   `technology_risk_does_not_double_penalize`,
   `no_new_rule_created_by_risk_correlator`,
   `no_risk_when_no_mapping_applies`.
2. Run and verify FAIL.
3. Minimal implementation: correlator + mapping table; risks are metadata
   only (no Finding creation, no score mutation).
4. Run and verify PASS.
5. Relevant regression: `tests/test_scoring_and_artifacts.py` (score stable
   when only observations exist).
6. Commit: `feat: correlate technology observations to existing audits`.

---

## Task G — Optional enrichment interface (contract only)

**Goal:** `OptionalTechnologyEnrichmentProvider` contract + v1 no-op; fail-open.

**Files:**
- Create `audit_rules/technology/enrichment.py`.
- Test: create `tests/phase12/test_technology_enrichment.py`.

**Interfaces:**
- Consumes: `TechnologyProfile`, optional credentials/config (empty in v1).
- Produces: enrichment facts with `source_provenance="external_api"` or
  `{"status": "unavailable"}`.

**Steps:**
1. Write failing tests: `external_enrichment_optional`,
   `external_failure_does_not_block_audit`,
   `external_results_never_silently_override_local`,
   `enrichment_unavailable_recorded_in_profile`.
2. Run and verify FAIL.
3. Minimal implementation: contract + no-op provider (returns unavailable);
   no real BuiltWith/Wappalyzer API.
4. Run and verify PASS.
5. Relevant regression: integration tests for provider isolation.
6. Commit: `feat: add optional technology enrichment interface`.

---

## Task H — Replay integration

**Goal:** Technology source evidence persists in replay; offline
reconstruction; no live calls.

**Files:**
- Modify `audit_rules/replay.py` — persist allowlisted page fields and, when
  present, the serialized profile in `provider_evidence`-style section;
  version the technology section.
- Modify `audit_rules/technology/detector.py` — accept replay evidence in
  offline mode.
- Test: create `tests/phase12/test_technology_replay.py`.

**Interfaces:**
- Consumes: replay document; existing `build_replay_document` /
  `load_replay_artifact`.
- Produces: replay→profile reconstruction with parity/version checks.

**Steps:**
1. Write failing tests: `technology_profile_available_from_replay`,
   `replay_reconstruction_uses_snapshot_not_live_api`,
   `technology_replay_parity_after_signature_update_is_versioned`,
   `sensitive_header_values_absent_from_replay`.
2. Run and verify FAIL.
3. Minimal implementation: replay persistence + offline detector path.
4. Run and verify PASS.
5. Relevant regression: `tests/phase12/test_replay_315_page_parity.py`,
   `tests/phase12/test_replay_sensitive_fields.py`.
6. Commit: `feat: persist technology evidence in replay`.

---

## Task I — Machine artifact

**Goal:** `09_Technology_Profile.json` with provenance, versions, evidence,
risk mapping, client-safe serialization.

**Files:**
- Create `audit_rules/technology/artifact.py` (serializer/validator).
- Modify `runner.py` (root) finalize path — write/register the artifact; or
  the reports generator when artifacts are assembled offline.
- Test: create `tests/phase12/test_technology_artifact.py`.

**Interfaces:**
- Consumes: `TechnologyProfile`, `list[TechnologyRisk]`.
- Produces: `09_Technology_Profile.json` (schema_version, detector_version,
  signature_registry_version, source_url, git_head, detections, evidence,
  versions, risk_correlations, mapped_audit_ids, limitations,
  provider_provenance, detection_status).

**Steps:**
1. Write failing tests: `technology_artifact_contains_detector_version`,
   `technology_artifact_contains_registry_version`,
   `technology_profile_contains_no_raw_internal_objects`,
   `technology_artifact_serializes_from_replay_offline`.
2. Run and verify FAIL.
3. Minimal implementation: serializer + finalize wiring + registry.
4. Run and verify PASS.
5. Relevant regression: artifact/ZIP tests
   (`tests/phase12/test_final_zip_current_run_only.py`).
6. Commit: `feat: emit 09_Technology_Profile.json artifact`.

---

## Task J — DOCX integration

**Goal:** Insert editable Word sections `Website Technology Profile` and
`Technology Risks & Recommendations` between Executive Summary and
80-Item Diagnostic Summary; human-readable evidence; no raw dicts; no unsafe
values.

**Files:**
- Modify `audit_rules/docx_report.py` — add `website_technology_profile(
   doc, profile, risks)` builder (real Word tables, repeated headers) and call
   it after Executive Summary.
- Modify `reports/final-acceptance/generate_80item_docx.py` — pass profile
   and risks from the bundle/replay.
- Test: create `tests/phase12/test_technology_docx.py`.

**Interfaces:**
- Consumes: `TechnologyProfile`, `list[TechnologyRisk]`.
- Produces: DOCX tables; fixed no-risk sentence when none confirmed.

**Steps:**
1. Write failing tests: `technology_profile_present_in_docx`,
   `technology_risks_present_in_docx`,
   `technology_profile_contains_no_raw_internal_objects`,
   `technology_docx_evidence_is_human_readable`,
   `technology_docx_contains_no_sensitive_header_values`,
   `no_risk_sentence_when_no_confirmed_risk`,
   `docx_still_contains_80_audits_after_technology_sections`.
2. Run and verify FAIL.
3. Minimal implementation: DOCX sections + wiring.
4. Run and verify PASS.
5. Relevant regression: `tests/phase12/test_docx_report.py` (all existing
   DOCX tests remain green).
6. Commit: `feat: add technology sections to DOCX report`.

---

## Task K — Skill + AGENTS

**Goal:** `skills/technology-intelligence/SKILL.md` (behavior) and root
`AGENTS.md` (long-term product invariants only); explicit boundary with
engine implementation.

**Files:**
- Create `skills/technology-intelligence/SKILL.md`.
- Create root `AGENTS.md`.
- Test: create `tests/phase12/test_technology_docs.py` (asserts AGENTS.md
  contains the required invariants and SKILL.md exists and is non-empty;
  asserts neither contains domain names).

**Interfaces:**
- Consumes: approved spec invariants (§1, §20, §22 of the design).
- Produces: behavioral documentation; no runtime import.

**Steps:**
1. Write failing tests: `agents_invariants_present`,
   `skill_doc_exists_and_states_no_rule81`,
   `docs_contain_no_customer_domains`.
2. Run and verify FAIL.
3. Minimal implementation: AGENTS.md invariants (audit = 80 rules;
   Detection ≠ Finding; Detection ≠ vulnerability; evidence-first; no
   domain-specific production logic; local-first; external optional; missing
   data never PASS; client report has no unsafe/raw internal data; no Audit
   #81) + SKILL.md behavioral guidance.
4. Run and verify PASS.
5. Relevant regression: docs-only; no engine impact.
6. Commit: `docs: add technology intelligence skill and agent invariants`.

---

## Task L — Cross-site regression fixtures

**Goal:** Generic fixtures proving no dependency on
`baolaipackaging.com`/`gelgoogsort.com`.

**Files:**
- Create `tests/phase12/test_technology_cross_site.py` and fixture data
  builders (WordPress-like generic, non-WordPress generic, conflicting
  signals, unknown/insufficient evidence).
- Reuse `tests/phase12/test_diagnostic_quality.py` and
  `tests/phase12/test_report_quality.py` conventions.

**Interfaces:**
- Consumes: detector, registry, correlator, DOCX builder with synthetic data.
- Produces: deterministic cross-site assertions.

**Steps:**
1. Write failing tests: `generic_wordpress_like_fixture_detected`,
   `generic_non_wordpress_fixture_not_reported_as_wordpress`,
   `conflicting_signals_fixture_flags_conflict`,
   `unknown_insufficient_evidence_fixture_returns_unknown`,
   `baolai_specific_stack_not_reused`,
   `second_site_stack_not_reused`.
2. Run and verify FAIL.
3. Minimal implementation: fixture builders only (no production code change
   unless a real generic bug surfaces — then fix that generic bug).
4. Run and verify PASS.
5. Relevant regression: full suite.
6. Commit: `test: add cross-site technology fixtures`.

---

## Task M — Full regression / final acceptance

**Goal:** Everything green, contracts intact, CI-ready; then the separate
real-world acceptance.

**Files:**
- Verify: `python -m pytest tests/ -q`, `compileall`,
  `tests/test_registry_integrity.py`, `tests/test_master_id_adapter_binding.py`,
  tracked-JSON validation, `docker compose config -q`, privacy scan, and the
  existing `CROSS_SITE_HARDCODE_SCAN` extended to
  `audit_rules/technology/`.
- Modify (only if needed): `.github/workflows/ci.yml` gate list to include
  the new test paths.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: CI-ready state with exactly 80 rules; score unchanged unless an
  existing rule gains new confirmed evidence.

**Steps:**
1. Write failing test (if any gate gap exists, e.g., hardcode scan misses the
   new package): `technology_hardcode_scan_covers_new_package`.
2. Run and verify FAIL (only if a gap exists; otherwise skip).
3. Minimal implementation.
4. Run and verify PASS.
5. Relevant regression: full suite + privacy scan + DOCX/replay regression.
6. Commit: `test: finalize technology intelligence regression gates`.

**Separate acceptance step (not a fixture):** after Task M, run the approved
`SECOND REAL-WORLD TECHNOLOGY INTELLIGENCE ACCEPTANCE` on
`https://gelgoogsort.com/` using the current crawl data + replay — as a
validation run, never as a hardcoded test input.

---

## Test Coverage Mapping (31 tests)

| Test | Task |
|---|---|
| technology_profile_always_present | B |
| technology_profile_does_not_create_rule_81 | M / K |
| technology_detection_requires_evidence | B / D |
| technology_detected_is_not_automatic_risk | F |
| unknown_technology_not_guessed | B / D |
| cms_detection_controls_rule_applicability | E |
| wordpress_detection_does_not_auto_pass_privileged_rules | E |
| technology_risk_maps_to_existing_rule | F |
| technology_risk_does_not_double_penalize | F |
| external_enrichment_optional | G |
| external_failure_does_not_block_audit | G |
| confidence_requires_signal_strength | C / D |
| conflicting_signals_reduce_or_flag_confidence | B / C |
| version_unknown_when_not_provable | C / D |
| cookie_values_not_persisted | A |
| baolai_specific_stack_not_reused | L |
| second_site_stack_not_reused | L |
| technology_profile_present_in_docx | J |
| technology_risks_present_in_docx | J |
| technology_profile_contains_no_raw_internal_objects | I / J |
| technology_profile_available_from_replay | H |
| safe_headers_only_are_persisted | A |
| sensitive_headers_are_never_persisted | A |
| set_cookie_values_are_not_persisted | A |
| source_html_scripts_are_detected_without_rendered_dom | A / D |
| source_html_stylesheets_are_detected_without_rendered_dom | A / D |
| meta_generator_is_detected | A / D |
| low_confidence_cms_does_not_drive_applicability | E |
| technology_artifact_contains_detector_version | B / I |
| technology_artifact_contains_registry_version | B / I |
| not_detected_is_not_reported_as_definitely_absent | B / J |

---

## Plan Self-Review

**Spec coverage:** every approved design section maps to a Task
(acquisition A, contracts B, registry C, detector D, applicability E,
correlator F, enrichment G, replay H, artifact I, DOCX J, Skill/AGENTS K,
cross-site L, regression M; security/privacy in A/H/I/J; crawl-cost and
no-request rules in A/D; failure behavior in D/G/M).

**Placeholder scan:** the plan contains no unfinished markers and no
non-executable phrasing of the kinds forbidden by the writing-plans format
(every task has concrete files, interfaces, and a six-step TDD flow).

**Invariant scan:** no Audit #81; no double scoring (F/M); no raw sensitive
headers or cookie values (A/H/I/J); external API not required (G); replay no
live calls (H); Low confidence cannot mutate applicability (E); detector and
registry versions in artifact (B/I); no domain hardcode (C/L/M).

**Type/signature consistency:** models use the same snake_case dataclass
conventions as `Finding`/`CoverageRow`/`AuditScore`; signature fields match
the registry contract in §7 of the design.

**File-path validity:** all modified files exist in the current repo
(`server.py`, `audit_rules/context.py`,
`audit_rules/providers/librecrawl_provider.py`, `audit_rules/replay.py`,
`audit_rules/integration.py`, `audit_rules/coverage.py`, `runner.py`,
`audit_rules/docx_report.py`,
`reports/final-acceptance/generate_80item_docx.py`, `tests/phase12/`); new
files live under `audit_rules/technology/` and `skills/technology-intelligence/`.

**Dependency order:** A → B → (C, G) → D → E → F → H → I → J → K → (L, M);
no task depends on an unimplemented predecessor.
