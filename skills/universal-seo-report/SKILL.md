# Universal Master SEO Diagnostic Report Skill

Use this skill whenever work touches the client report contract, report
view model, DOCX renderer, remediation plan/checklist, report audience modes,
or shareable client output of the Master SEO Audit System.

## Purpose

Every website audit produces the **same** Universal Master SEO Diagnostic
Report structure. The system is a product: one report architecture, driven by
data, safe to share with any client.

## Default client deliverable

- Primary: `01_Master_SEO_Diagnostic_Report.docx` (`REPORT_FORMAT=docx`).
- Internal artifact directory: numbered `02`–`09` files +
  `Technical_Appendix/` + `README.txt` + Final ZIP.
- Export directory convention: `reports/<site>-seo-audit-<date>/` with
  generic filenames — never a client-specific product name in filenames.

## Report contract

The fixed DOCX structure is:

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

Exactly 80 audits. Never add Audit #81.

## Evidence and semantics

- Evidence-first: every result cites representative evidence; full evidence
  lives in artifacts (`03_Detailed_URL_Findings.csv`,
  `09_Technology_Profile.json`).
- PASS items still explain what was checked, why they pass, what to maintain,
  and how to recheck — never just "No remediation required."
- UNKNOWN/NOT_CHECKED states Not Verified, the reason, the required data, and
  how to complete the check. Missing data never becomes PASS.
- NOT_APPLICABLE keeps its 80-row slot but states why.
- Technology Profile semantics: DETECTED / UNKNOWN / NOT_DETECTED /
  CONFLICTING; Low confidence never confirms; UNKNOWN observations must be
  labeled Not Confirmed.

## Actionable remediation

Every confirmed FAIL/WARNING must answer the six questions:

- WHAT IS WRONG?
- WHERE IS IT?
- WHY DOES IT MATTER?
- HOW DO I FIX IT?
- WHO SHOULD FIX IT?
- HOW DO I KNOW IT IS FIXED?

Recommendations are rule-driven (remediation library), never LLM guesses
about unknown client backends.

## Client safety

Client DOCX must never contain: raw dicts, raw JSON, internal enums, internal
scope tokens, local Windows paths, API keys/tokens, Authorization, Cookie /
Set-Cookie values, debug text, stack traces, or other clients' domain/brand/
page-count/technology/metrics.

## Cross-client isolation

Use only current-run data: current replay, current provider evidence, current
site metadata. Never fall back to a previous client's state or a static
previous-site count. Report identity (Site Name, Domain, Audit Date, Pages
Crawled) is current-run driven; when site name cannot be reliably determined,
use the hostname — never another client.

## Audience modes

`REPORT_AUDIENCE=client` (default) or `internal`. Both present the same
diagnosis results; presentation may differ (internal may show more
provenance). No secrets/tokens in either mode.

## Score explanation

Always explain: Score = health of executed rules; Coverage = how much was
actually checked; Confidence = reliability of conclusions. Score is not a
Google official score and not a ranking prediction.

## Performance claims

Field Data != Lab Data; Sample != Full Site; PSI Error != SEO defect; no
CrUX -> no Field CWV Pass claim.

## Domain independence

Never write `if client_x:` / `if page_count == N:` report logic. The renderer
is driven by the data contract, not by a known client.
