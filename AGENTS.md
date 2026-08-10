# Agent Invariants — Master SEO Audit System

These are long-term product invariants. They apply to every agent, skill, and
tool that builds, extends, or runs the Master SEO Audit System. Detailed
behavioral guidance for the technology intelligence layer lives in
`skills/technology-intelligence/SKILL.md`.

## Core invariants

1. **Audit remains exactly 80 rules.** The diagnostic registry is exactly 80
   items. Never add Audit #81 or any new rule to satisfy a new capability.
2. **Technology Detection != Finding.** Detecting a technology is an
   observation, not an SEO finding. It must never be emitted as a
   client-facing FAIL/WARNING by itself.
3. **Technology Detection != Vulnerability.** A detected technology is never
   automatically a security or SEO vulnerability. Correlation only points at
   existing audits that can consume the evidence.
4. **Evidence-first.** Every result, detection, or correlation must cite
   structured evidence (signal, value, source URL, scope, strength,
   provenance). No evidence, no claim.
5. **No domain-specific production logic.** Production code must never
   special-case a customer domain. No hardcoded site names in detectors,
   rules, scoring, or report generation.
6. **Local-first.** Detection runs locally from crawl evidence (HTML,
   allowlisted response headers, resources). External providers are optional.
7. **External optional.** Missing, failing, or quota-limited external
   enrichment never blocks the audit, DOCX, replay, or report. It is recorded
   as `unavailable`.
8. **Missing data never becomes PASS.** A rule that cannot be evaluated
   without missing data is NOT_CHECKED / EXECUTED_PARTIAL /
   MANUAL_REVIEW_REQUIRED per its contract — never a fabricated PASS or FAIL.
9. **Client-safe reporting.** Client reports never contain raw dicts, raw
   JSON, internal enums, signature internals, sensitive headers, cookie
   values, debug reprs, or internal scope tokens.
10. **No Audit #81.** A new capability never expands the audit count. It is
    expressed as evidence, applicability, risk correlation, or an artifact.
11. **One universal report contract.** Every site produces the same report
    architecture (Universal Master SEO Diagnostic Report). Site technology,
    scale, language, CMS, and issue counts change content/data only, never
    the report structure.
12. **Current-run-only.** Any audit run may use only the current run, current
    replay, current provider evidence, and current site metadata. Never fall
    back to previous client state, module-global client caches, static
    previous-site counts, or historical default domains.
13. **Client-safe and shareable.** Client reports hide raw internals, local
    paths, tokens, secrets, and other clients' data; they never hide real
    issues. `REPORT_AUDIENCE=client` (default) and `internal` share the same
    diagnosis results.
14. **Actionable remediation.** Every confirmed FAIL/WARNING answers: what is
    wrong, where, why it matters, how to fix, who fixes it, and how to verify
    it is fixed. PASS items still show what was checked and why they pass.
15. **Presentation never changes diagnosis.** Report wording, labels, or
    audience mode never change Rule Result, Coverage, Score, or Findings.
