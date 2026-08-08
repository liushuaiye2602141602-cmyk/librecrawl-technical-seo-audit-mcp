# Existing-partial crawl gap closure design

## Goal

Eliminate the seven `EXISTING_PARTIAL` registry entries that currently have no
adapter, close the crawl-evidence portions of their acceptance criteria, and
prevent unregistered or crashed rules from becoming false PASS results.

## Scope

Rules 2, 5, 13, 23, 25, 40, and 66 receive executable bindings. They remain
`EXISTING_PARTIAL` wherever external evidence or human judgment is still
required. No provider failure or missing response header may be interpreted as
an SEO pass.

## Architecture

A new `foundation_gaps` check module consumes only normalized SiteContext,
PageContext, raw export references, and already-produced extended data. It
implements sitemap health, crawl-space patterns, title uniqueness/truncation,
cache/CDN headers, HTTPS coverage/mixed content, and WordPress cache-layer
signals. Header-dependent checks explicitly report data unavailability to the
execution tracker instead of returning an empty finding list.

`CompatibilityHarness` records which rules actually completed and why an
adapter did not execute. `CoverageManager` receives these facts. A rule with no
adapter, a crashed adapter, or an explicit data-unavailable result is
`NOT_CHECKED + UNKNOWN`; only a completed adapter can PASS. External source
gating remains independent and conservative.

Rule 40 stays an output-stage rule. The task generator is repaired to use the
real Finding fields and expanded with actionable assignee, due date, status,
and verification columns. A small pure adapter verifies that the deliverable
pipeline marker is present; production integration sets that marker before
rule execution and later writes the CSV.

## Evidence boundaries

- Sitemap crawl evidence does not claim GSC/Bing submission success.
- URL-pattern detection does not claim server-log crawl share.
- Title pixel width is an estimator; intent/CTR remains external/manual.
- Cache checks use exported response headers only and make no HTTP calls.
- Certificate validity remains unavailable unless explicit TLS evidence is
  supplied; HTTPS redirect and mixed-content checks still execute.
- WordPress cache synergy applies only to WordPress profiles.
