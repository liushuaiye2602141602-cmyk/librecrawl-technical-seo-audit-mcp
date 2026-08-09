# Website Technology Intelligence Skill

Use this skill whenever work touches the Website Technology Profile,
Technology Risks & Recommendations, technology detection, CMS applicability,
or the `09_Technology_Profile.json` artifact in the Master SEO Audit System.

## Purpose

Technology Intelligence observes what a site is built with — CMS,
framework/platform, theme/builder, SEO tools, analytics, tag managers,
pixels, CDN/WAF, server, JS libraries, and other reliable technologies —
from evidence already collected during a crawl. It never invents
technologies and never creates new audit rules.

## Boundary

- The audit count is **exactly 80**. Technology Intelligence adds evidence,
  applicability context, and risk correlation only.
- A technology **detection is an observation**, not a Finding and not a
  vulnerability. Only an existing Audit #01鈥?0 with a confirmed finding can
  produce a client-facing FAIL/WARNING or remediation.
- Technology Profile and Technology Risks **never deduct SEO Score**
  directly. Score changes come only from the existing 80-rule score
  contract.

## Evidence rules

- Every detection requires structured evidence: signal type, signal value,
  source URL, source scope, strength, and provenance.
- Multiple independent strong signals raise confidence to High; a single
  strong signal is Medium/High per the registry contract; a weak single
  signal is Low; conflicts reduce confidence or flag CONFLICTING.
- Common strings never imply 100% confidence, and versions are only reported
  when provable from evidence, otherwise `Unknown`.
- `NOT_DETECTED` means the current detector coverage found no supporting
  evidence — never a claim that the technology is definitely absent.

## Privacy and safety

- Persist only allowlisted response headers. Never persist Authorization,
  Cookie values, Set-Cookie values, tokens, credentials, session data, or
  personal identifiers.
- Cookie detection stores names only.
- Replay and offline reconstruction never call live APIs or external
  providers.

## Detection status contract

| Status | Meaning |
| --- | --- |
| DETECTED | Sufficient evidence supports the technology. |
| NOT_DETECTED | No supporting evidence observed; absence is not proven. |
| UNKNOWN | Insufficient data or collection capability. |
| CONFLICTING | Credible signals conflict; confidence reduced and reported. |

## CMS applicability safety

- High-confidence CMS detection may drive applicability for the relevant
  existing audits only (WordPress 鈫?existing WordPress/plugin audits).
- Medium confidence may drive applicability only when the registry-defined
  explicit strong-evidence requirement is met.
- Low-confidence or conflicting CMS detection is observation only and never
  changes applicability.
- Detecting WordPress never auto-PASSes or auto-FAILs the WordPress rules;
  those rules still evaluate their own evidence per their contracts.

## Risk correlation

- Risk correlation maps a confirmed observation to existing audits only:
  WordPress 鈫?existing WordPress/plugin audits; CDN/cache 鈫?existing
  cache/CDN audits; SEO output 鈫?existing provenance audits; analytics 鈫?
  existing analytics audits; schema generator 鈫?existing schema audits; JS
  rendering 鈫?existing rendering audits; forms 鈫?existing form audits.
- A correlation is a `CONFIRMED_OBSERVATION` by default. It becomes a
  confirmed risk only when a mapped existing audit has an actual FAIL/WARNING
  finding. Never double-penalize.

## Client reporting

- DOCX shows the Website Technology Profile table (Category, Technology,
  Version, Confidence, Evidence) and Technology Risks & Recommendations
  (Technology, Observation/Confirmed Risk, Mapped Audit, Impact, Recommended
  Action).
- When no risk is confirmed, show: "No confirmed technology-specific risks
  were detected from the available observable evidence."
- Evidence in client reports is human-readable. Never output raw dicts,
  raw JSON, internal enum dumps, signature internals, sensitive headers,
  cookie values, or internal scope tokens.

## Replay and artifacts

- Technology evidence persists in the replay document with schema, detector,
  and signature registry versions.
- Replay reconstruction prefers the versioned snapshot; version mismatches
  are recorded in limitations, never silently re-detected.
- Every audit run emits `09_Technology_Profile.json` with versions,
  detections, evidence, limitations, provenance, and risk correlations.

## Domain independence

- Never write production logic that special-cases a customer domain.
- Core detection tests use generic fixtures, never customer sites.
