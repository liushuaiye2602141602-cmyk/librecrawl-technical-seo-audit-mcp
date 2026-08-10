# Website Technology Intelligence — Design Spec

**Date:** 2026-08-09
**Status:** Design (no implementation)
**Product name:** Website Technology Intelligence
**Client report section:** Website Technology Profile + Technology Risks & Recommendations
**Hard constraint:** Audit count remains exactly **80**. This is not Audit #81.

---

## 1. Product Definition

The Master SEO Audit System gains a **technology awareness layer** for every
future site audit:

```
URL → Crawl → Local Technology Detection → Technology Profile
    → Technology Risk Correlation → Existing Audit #01–#80 → DOCX Report
```

*Website Technology Intelligence* identifies the observable technology stack
of an audited site (like a BuiltWith-style profile, without using the
BuiltWith name or depending on it), maps technology facts to the existing
80 rules, and reports human-readable evidence. It is **not** a new SEO rule,
**not** a vulnerability scanner, and **not** a score input by itself.

Product invariants (must hold everywhere):

1. `Technology detected ≠ SEO issue`.
2. `Technology detected ≠ security vulnerability`.
3. Local detection is the primary source; external enrichment is optional.
4. Every detection is evidence-driven; `Unknown` is allowed and guessing is
   forbidden.
5. Risk only exists when mapped to, and confirmed by, an existing
   Audit #01–#80 rule.
6. No domain-specific logic (`baolaipackaging.com`, `gelgoogsort.com`,
   `yashengcrafts.com`, …) anywhere in signatures or correlation.

---

## 2. Current Codebase Context (what exists, what to reuse)

### 2.1 Architecture to integrate with

- **Crawl/acquisition:** LibreCrawl export → `server._parse_export()` →
  `libreclient.export_pages()`. Export fields are listed in
  `server.EXPORT_FIELDS` (url, title, meta, h1, word_count, canonical, depth,
  response_time_ms, links_detailed, images, robots, lang, charset, viewport,
  og_tags, twitter_tags, json_ld, hreflang, **analytics**, …).
- **PageContext** (`audit_rules/context.py`): lightweight page fields +
  lazy `response_headers` (from raw `response_headers`/`headers` keys,
  currently **absent** from the production export) + `_raw_export` reference.
- **SiteContext**: robots/sitemap/redirect facts, crawl completeness, and
  **`site_profile`** (`"generic"` default; only the WordPress privileged
  provider sets `"wordpress"`). `coverage.py:_check_applicability` gates
  rules #36–39/#64–69 on `site_profile == "wordpress"`.
- **Rule Registry**: 80 rules, exact IDs 1..80 (`audit_rules/registry.py`).
- **Rule adapters**: one adapter per rule (`adapters.py`); several already
  consume technology-adjacent evidence (e.g., #23 Cache/CDN via
  `response_headers`, #26 security headers, #39 WP probes gated by
  `WP_SECURITY_PROBES_ENABLED`, #18 archive classifier, #67 staging).
- **Providers**: LibreCrawl, PageSpeed, GSC, Semrush, GA4, Server Logs,
  WordPress Privileged, Rendered DOM, Availability, Manual Review
  (`audit_rules/providers/`), each via `DataProvider`.
- **Coverage/Findings/Tasks/Score contracts**: `CoverageManager` (80 rows),
  `Finding` (severity/priority/confidence/evidence/…), task taxonomy
  (REMEDIATION / OPTIMIZATION / DATA_REQUIRED / MANUAL_REVIEW / MONITORING),
  scoring (UNKNOWN excluded from quality denominator).
- **Report**: `audit_rules/reporting.py` (Markdown) and
  `audit_rules/docx_report.py` (native Word DOCX, data-driven site name,
  pages, evidence, management/executive/roadmap sections).
- **Replay**: `audit_rules/replay.py` — pages/links/site_data/
  provider_evidence + parity validation; enables offline regeneration.

### 2.2 Existing detection signals (reuse, don’t duplicate)

| Signal | Where it lives today | Reuse for |
|---|---|---|
| Per-page **analytics fingerprint** (`ga4_id`, `gtm_id`, `fb_pixel`, `hotjar`, `mixpanel`, …) | LibreCrawl export `analytics` field; consumed in `server.py` report | Analytics, Tag Manager, Advertising Pixel categories |
| **Asset paths** in `links_detailed` / `images` (e.g., `wp-content`, `wp-includes`, CDN hosts) | PageContext `links_detailed`, `image_summary` | CMS / CDN / asset fingerprints |
| **meta `robots`** content (Yoast-style pattern) | PageContext `robots` | CMS/SEO-plugin heuristics (low strength alone) |
| **JSON-LD types** (`@type`, `@graph`) | `json_ld_types` via `_extract_json_ld_types` | Schema-generator provenance |
| **URL structure** (`/wp-json/`, `/wp-admin/`, `/tag/`, `/hashtag/`, locale prefixes) | page URLs + `_classify_archive_page` | CMS/architecture hints (low strength) |
| **response headers** (when present) | PageContext `response_headers` (lazy) | CDN/WAF/server/security-header signals |

### 2.3 Gaps to close at acquisition time (crawl-layer, not per-rule)

The current export does **not** collect: `response_headers`, a structured
script/stylesheets inventory, `meta generator`, or cookie names. The spec
defines a minimal crawl-layer extension (add `response_headers` to
`EXPORT_FIELDS` and normalize a small `assets`/`scripts` list from existing
link/image data when available). Until then those categories report
`Unknown / Not Detected` — never guesses. Rendered DOM remains an optional
provider, never a default dependency.

---

## 3. Architecture

```
Technology Intelligence Layer
│
├── LocalTechnologyDetector
├── TechnologySignatureRegistry
├── TechnologyProfile
├── TechnologyDetection
├── TechnologyEvidence
├── TechnologyRisk
├── TechnologyRiskCorrelator
├── OptionalExternalEnrichmentProvider
└── ReportTechnologySection
```

### 3.1 Component contracts

| Component | Responsibility | Inputs | Outputs | Dependencies | Failure behavior |
|---|---|---|---|---|---|
| **TechnologySignatureRegistry** | Declarative signatures (no scattered `if "wp-content" in html` in code) | signature definitions (technology, category, signal type, pattern, strength, version extractor, negative signals) | validated signature table | none | Registry load failure → detector returns empty profile with `detection_incomplete` reason |
| **LocalTechnologyDetector** | Runs signatures over crawl-time evidence | PageContexts, SiteContext, replay document | `list[TechnologyDetection]` | Registry, replay/crawl data | Detector exception → profile `Detection incomplete` + reason; **never** fails the 80-rule audit |
| **TechnologyProfile** | Aggregated per-category stack | detections + confidence aggregation | `TechnologyProfile` | Detector | N/A (pure model) |
| **TechnologyRiskCorrelator** | Maps confirmed observations to existing rules | profile + audit coverage/findings | `list[TechnologyRisk]` | Profile, coverage | No matching rule → no risk (never invents) |
| **OptionalExternalEnrichmentProvider** | Optional Wappalyzer-like/BuiltWith-like API source | profile + credentials/config | enrichment facts with provenance | external API | timeout/quota/error/missing credentials → enrichment `unavailable`, never blocks audit/report |
| **ReportTechnologySection** | DOCX/Markdown sections | profile + risks + evidence | client-safe report sections | Profile, RiskCorrelator | Empty profile → “Detection incomplete / Unknown”, still renders |

### 3.2 Placement in the pipeline

The layer runs **after crawl normalization and before rule evaluation** (so
`site_profile` / rule applicability can consume it) and is **fully
replayable** (runs from the preserved replay document when no live crawl is
available). It is a sibling of the existing providers — not a new rule, not a
new provider family required for the 80 rules to run.

---

## 4. Data Model

### 4.1 `TechnologyEvidence` (structured, not a human string)

```text
signal_type      e.g. "meta_generator", "asset_path", "response_header",
                 "script_src", "analytics_fingerprint", "json_ld_type",
                 "url_pattern", "cookie_name"
signal_value     exact observed value (no raw page HTML dumps)
source_url       one representative URL
source_scope     "single_page" | "multi_page" | "site_level"
strength         strong | medium | weak   (signature-defined)
source_provenance "local_crawl" | "external_api"
```

### 4.2 `TechnologyDetection`

```text
category            one of the categories in §6
technology_name     e.g. "WordPress", "Cloudflare", "GA4"
technology_type     e.g. "CMS", "CDN", "Analytics"
version             only when reliably provable (§10), else "Unknown"
confidence          High | Medium | Low (client display); internal 0.00–1.00
confidence_score    0.00–1.00
detection_sources   [TechnologyEvidence]
first_seen_urls     [url]
affected_urls       [url]
is_observation      True always at detection time
is_risk             False by default; set only by RiskCorrelator
risk_level          None | Low | Medium | High   (only when is_risk)
risk_reason         ""
mapped_audit_ids    []  (set by RiskCorrelator)
limitations         e.g. "Rendered DOM not available", "headers not exported"
external_enrichment {}  (provenance kept separate; never overrides local)
```

### 4.3 `TechnologyProfile`

```text
schema_version        "technology-profile-v1"
source_url            audited site
generated_at
git_head
detections            [TechnologyDetection]
category_summary      {category: [technology names]}
detection_status      "COMPLETE" | "PARTIAL" | "DETECTION_INCOMPLETE"
detection_reason      "" | failure reason
limitations           [string]
external_enrichment   {"provider": name|"", "status": "unavailable"|"ok"}
```

### 4.4 `TechnologyRisk`

```text
technology          e.g. "WordPress"
observation         the confirmed TechnologyDetection
classification      "CONFIRMED_OBSERVATION" | "RISK_CANDIDATE" | "NO_RISK"
mapped_audit_ids    [existing rule ids]
impact              human-readable, tied to the existing rule
recommended_action  only when the mapped rule confirms a Finding
```

Model naming and fields follow the existing `Finding`/`CoverageRow`/`AuditScore`
conventions (snake_case dataclasses, `schema_version`, `confidence` as
`0.00–1.00` with client `High/Medium/Low` labels).

---

## 5. Technology Categories

Detector registry supports all of the following categories; a site simply has
`Unknown / Not Detected` where there is no evidence:

CMS · Ecommerce · Framework · Backend/Platform · Theme · Page Builder ·
SEO Technology · Analytics · Tag Manager · Advertising Pixel · CDN ·
WAF/Security · Web Server · JavaScript Library · Consent/CMP · Chat/CRM ·
Forms · Performance/Cache · Schema Generator · Fonts/Assets · Video/Embed ·
Payment · Hosting Signal · DNS/Edge

No evidence → `Unknown / Not Detected`. No guesses, no “looks like” defaults.

---

## 6. Local-First Detection Sources

Detection runs over evidence the crawl already produced (or minimal,
non-default crawl-layer fields):

- HTML-derived: meta `generator` (when exported), meta `robots`, title/lang,
  `og_tags`/`twitter_tags`.
- Response headers (when exported): `server`, `x-powered-by`, `cf-ray`,
  `x-cache`, `x-cache-hits`, security headers, `set-cookie` name patterns
  (names only — **never values**).
- Scripts/stylesheets: `script_src`, `stylesheet_href` from a normalized
  asset list (built from existing `links_detailed`/`images` asset paths; a
  full DOM/script inventory is an optional rendered-DOM provider).
- Asset paths: `wp-content/`, `wp-includes/`, `cdn.` hosts, `assets/`,
  fingerprint hashes in URLs.
- `analytics` fingerprint (existing): ga4_id, gtm_id, fb_pixel, hotjar,
  mixpanel, …
- JSON-LD: types and `@graph` provenance.
- URL structure: `/wp-json/`, `/wp-admin/`, `/tag/`, `/hashtag/`, locale
  prefixes, `.php`, `?s=` search patterns.
- Observable cookies: only when a cookie-source provider exists; records
  names/categories, never values.
- HTTP behavior / DNS/CDN: only from observable crawl data (e.g., redirect
  behavior, response header CDN signatures); no DNS scanning, no
  subdomain brute force, no active probing beyond the existing audit bounds.

**Rendered DOM is optional** (existing `RenderSnapshotProvider`), not a
default dependency.

---

## 7. TechnologySignatureRegistry

Signatures are declarative and data-driven:

```text
{
  "technology": "WordPress",
  "category": "CMS",
  "signals": [
    {"type": "asset_path",   "pattern": r"/wp-content/",  "strength": "strong"},
    {"type": "asset_path",   "pattern": r"/wp-includes/", "strength": "strong"},
    {"type": "meta_generator","pattern": r"WordPress",    "strength": "strong"},
    {"type": "url_pattern",  "pattern": r"/wp-json/",     "strength": "medium"},
    {"type": "url_pattern",  "pattern": r"/wp-admin/",    "strength": "medium"},
    {"type": "robots_meta",  "pattern": r"max-image-preview", "strength": "weak"}
  ],
  "negative_signals": [{"type": "meta_generator", "pattern": r"Webflow"}],
  "version_extractor": {"type": "generator_version", "pattern": r"WordPress ([\d.]+)"},
  "min_strength_for_detection": "medium",
  "notes": "weak signals alone must stay Low confidence"
}
```

Requirements: extensible, testable, no single-site dependence; patterns
target **technology characteristics only**, never customer domains.

---

## 8. Confidence Model

- Client display: `High | Medium | Low`. Internal: `0.00–1.00`.
- Aggregation rule:
  - 2+ independent **strong** signals → High.
  - 1 strong signal → Medium/High (signature-defined; never automatic High).
  - Weak single signal → Low (never “confirmed”).
- A single ordinary string hit is never 100% confirmation.
- **Conflicting signals** are never silently overwritten: they lower
  confidence and/or surface `conflicting_signals: [...]` in the detection.
- `confidence_score` uses the aggregated strength, not the number of URLs.

---

## 9. Version Detection

Version is emitted **only** with reliable evidence:

- explicit script/library version (`?ver=…`, package version), generator
  version, or a resource signature whose version is provable.
- Otherwise `Version = Unknown`.

Forbidden: guessing from release dates, hashing files to infer versions,
inferring from CMS “appearance”, or mapping a stack to a version.

---

## 10. Technology ≠ Issue (formal invariant)

These are always `Observation`, never automatic FAIL:

- WordPress detected → Observation
- Cloudflare detected → Observation
- REST API available → Observation
- XML-RPC available → Observation
- server header visible → Observation
- CMS detected → Observation
- version detected → Observation
- jQuery / GA4 / GTM / cookie-consent detected → Observation

Only the `TechnologyRiskCorrelator` may classify a confirmed observation as a
risk, and only by mapping to an existing rule that independently confirms a
Finding.

---

## 11. Technology Risk Correlation

`TechnologyRiskCorrelator` maps **confirmed** observations to existing rules:

| Observed technology fact | Mapped existing audits | Behavior |
|---|---|---|
| WordPress (High confidence) | #36–#39, #64–#69 | **Applicability** change: NOT_APPLICABLE → Applicable evaluation (see §12); never auto-PASS |
| Multiple SEO output sources / conflicting canonical/meta | #37 (and #8 canonical) | supplies evidence to existing checks |
| Duplicated GA4 loader / containers | #34/#35 | evidence only; rules decide |
| CDN/cache evidence (headers, asset hosts) | #23/#26/#66 | evidence for existing checks |
| Schema generator provenance | #27/#28/#78 | evidence for schema checks |
| Rendered-JS dependency | #46/#48 | optional helper evidence (Rendered DOM provider) |
| Form technology | #70/#71 | evidence for accessibility/manual checks |

Three explicit concepts, kept separate:

1. **Technology observation** — fact, no judgment.
2. **Technology risk** — a correlator-level flag only when the mapped rule
   could be affected; still not a finding.
3. **SEO finding** — produced only by the existing rule adapter.

No new rule is created. No double penalty: the profile does not score, risks
do not score; only Findings from Audit #01–#80 affect the existing score.

---

## 12. WordPress Applicability (the key change)

- If WordPress is **High-confidence detected** (local evidence): rules
  #36–#39/#64–#69 move from `NOT_APPLICABLE` to **applicable evaluation**.
- Applicable ≠ EXECUTED_FULL. Without privileged data the rules stay
  `NOT_CHECKED` / `EXECUTED_PARTIAL` / `MANUAL_REVIEW_REQUIRED` per actual
  capability (existing adapters already raise `DataUnavailableError` or
  require a privileged snapshot).
- `WordPress detected → WordPress rules PASS` is forbidden.
- `site_profile` becomes a **profile-derived** field (e.g.,
  `"wordpress_remote"` from local evidence) in addition to the
  privileged-provider `"wordpress"`; the coverage applicability gate is
  adjusted to treat both as applicable while keeping the evidence bar.

---

## 13. External Enrichment (optional, fail-open)

`OptionalExternalEnrichmentProvider` interface:

- Wappalyzer-like / BuiltWith-like API, or any future provider.
- Local detector works independently; external is additive.
- Timeout, quota, API error, missing credentials → enrichment
  `unavailable`, never blocking the 80-rule audit, DOCX generation, or the
  Technology Profile.
- On conflict, **source provenance is preserved**; external results never
  silently override local evidence (both shown; confidence adjusted).

---

## 14. Report Contract (DOCX)

Default DOCX structure becomes:

```text
Cover
Management Summary
Executive Summary
Website Technology Profile
Technology Risks & Recommendations
80-Item Diagnostic Summary
Full Audit #01–#80
30-Day Remediation Roadmap
Responsibility Matrix
Acceptance & Recheck
Technical Appendix
```

**Website Technology Profile table:** Category | Technology | Version |
Confidence | Evidence (human-readable bullets, ≤5 per detection).

**Technology Risks & Recommendations table:** Technology | Confirmed
Observation / Risk | Mapped Audit | Impact | Recommended Action.

When no confirmed risk exists, the section shows exactly:

> No confirmed technology-specific risks were detected from the available
> observable evidence.

Evidence is human-readable (`/wp-content/ asset references`, `response
header cf-ray`), never raw Python dicts/JSON/enums/registry internals.
Structured evidence goes to the Technical Appendix / machine artifact.

---

## 15. Machine Artifact

`09_Technology_Profile.json` (numbered to fit the existing client package):

```json
{
  "schema_version": "technology-profile-v1",
  "source_url": "...",
  "git_head": "...",
  "detections": [...],
  "confidence": "...",
  "evidence": [...],
  "versions": {...},
  "risk_correlations": [...],
  "mapped_audit_ids": [...],
  "limitations": [...],
  "provider_provenance": {...},
  "detection_status": "COMPLETE|PARTIAL|DETECTION_INCOMPLETE"
}
```

Replay must be able to rebuild the profile offline (crawl evidence →
replay snapshot → offline detection) without revisiting the site. Any
live-external dependency is snapshotted or reported as
`external enrichment unavailable`.

---

## 16. Replay Support

- Detection inputs are stored in the replay (pages/links/site_data +
  provider evidence). The profile is **regenerated offline** from the replay.
- If a detection depends on live external enrichment, the enrichment result
  is snapshotted into replay evidence or explicitly marked unavailable.
- Replay never silently calls live APIs.

---

## 17. Cross-Site Generalization

- No domain-specific production logic: signatures match technology
  characteristics only.
- No `baolaipackaging.com` / `gelgoogsort.com` / `yashengcrafts.com` special
  cases in engine, detector, correlator, or report.
- The existing `CROSS_SITE_HARDCODE_SCAN` is extended to scan the new layer.
- After implementation, `gelgoogsort.com` serves as the **second real-world
  Technology Intelligence acceptance** — to validate generality, not to
  tailor the design.

---

## 18. Security Semantics

Invariants:

- REST API available ≠ vulnerability
- XML-RPC available ≠ vulnerability
- server header visible ≠ vulnerability
- CMS detected ≠ insecure
- version detected ≠ automatically vulnerable

Remediation is allowed only with reliable vulnerability evidence or a
confirmed risk already defined by an existing Audit rule. Technology
Intelligence must not become a low-quality vulnerability scanner.

---

## 19. Privacy / Security

- Cookie detection records **names/category evidence only**; never values.
- Session/auth/personal tokens/credentials never enter artifact/report.
- Headers are filtered to avoid leaking sensitive tokens (reuse the replay
  sanitizer allowlist/denylist approach).

---

## 20. Skill / Agent Instructions

- Add `skills/technology-intelligence/SKILL.md` to constrain behavior:
  evidence-first interpretation, technology ≠ issue, confidence semantics,
  risk mapping to existing rules, no #81, no domain-specific assumptions,
  local-first, external optional, client-safe reporting.
- `AGENTS.md` (currently **absent** at repo root — add one if the team
  wants long-term invariants) may record the product invariants from §1.
- Explicit boundary: **Skill/AGENTS are behavioral constraints, not product
  implementation**. Engine / Report / Tests are the formal implementation.

---

## 21. Test Strategy

Future tests (mirroring the 80-rule TDD pattern):

- `technology_profile_always_present`
- `technology_profile_does_not_create_rule_81`
- `technology_detection_requires_evidence`
- `technology_detected_is_not_automatic_risk`
- `unknown_technology_not_guessed`
- `cms_detection_controls_rule_applicability`
- `wordpress_detection_does_not_auto_pass_privileged_rules`
- `technology_risk_maps_to_existing_rule`
- `technology_risk_does_not_double_penalize`
- `external_enrichment_optional`
- `external_failure_does_not_block_audit`
- `confidence_requires_signal_strength`
- `conflicting_signals_reduce_or_flag_confidence`
- `version_unknown_when_not_provable`
- `cookie_values_not_persisted`
- `baolai_specific_stack_not_reused`
- `second_site_stack_not_reused`
- `technology_profile_present_in_docx`
- `technology_risks_present_in_docx`
- `technology_profile_contains_no_raw_internal_objects`
- `technology_profile_available_from_replay`

---

## 22. Backward Compatibility & Failure Behavior

- Exactly 80 rules; existing Finding/Coverage/Score/Tasks/DOCX/Replay
  contracts remain compatible. Technology Intelligence is a cleanly
  isolated layer.
- Detector failure → profile `Detection incomplete` + reason + available
  evidence + limitations; the 80-item audit continues normally.
- No external API becomes a hard dependency.

---

## 23. Future Validation Site

`https://gelgoogsort.com/` is the designated second real-world acceptance
site for this capability — the design is deliberately **not** shaped around
it.

---

## 24. Open Questions (recorded, not blocking)

1. Whether `response_headers` should be added to `EXPORT_FIELDS` (crawl-layer
   cost vs richer CDN/WAF/server detection) — requires an acquisition-layer
   change; header categories stay `Unknown` until decided.
2. Whether a structured `assets/scripts` inventory should be normalized from
   existing link/image data or deferred to the rendered-DOM provider.
3. Whether `AGENTS.md` should be introduced at repo root with the product
   invariants, or whether `skills/technology-intelligence/SKILL.md` alone
   suffices.
4. External enrichment provider choice (none required for v1; interface only).

---

## Self-Review

- No TBD/TODO placeholders left unresolved (open questions are explicit).
- No conflict with the existing 80-item contract; audit count stays 80.
- No new Audit #81.
- External API is optional; local detection is primary.
- No technology-equals-issue logic; risk requires an existing rule.
- No domain-specific logic.
- Failure behavior, replay, privacy, DOCX, tests, and Skill-vs-Engine
  boundaries are specified.
