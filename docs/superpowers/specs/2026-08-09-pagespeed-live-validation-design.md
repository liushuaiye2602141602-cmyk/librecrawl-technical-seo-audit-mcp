# PageSpeed live validation design

## Goal

Make the already implemented PageSpeed client and performance checks reachable
from the production V3 runner, preserve honest provider-failure semantics, and
record a real API smoke validation without persisting the supplied credential.

## Verified starting facts

- `audit_rules.providers.psi_client.fetch_pagespeed()` successfully returned a
  live mobile Lighthouse result for `https://example.com/` on 2026-08-09.
- The response contained all four score categories, six normalized lab metrics,
  URL-scope field data, and Lighthouse 13.4.1.
- `audit_rules.integration._get_runner()` currently creates a runner without a
  `PageSpeedDataProvider`, so production V3 audits cannot fetch PSI data.
- The provider identifies itself as `PageSpeedInsights`, while registry rules
  require the canonical source `PageSpeed API`; this prevents honest coverage
  availability even if snapshots are supplied.
- An all-error PSI batch currently leaves the provider marked available, which
  can turn provider errors into apparent PASS results.

## Architecture

`_get_runner()` owns one session-cached `PageSpeedDataProvider` under the
canonical key `PageSpeed API`. The provider remains unavailable when the API
key or feature flags are absent. The RuleRunner samples eligible URLs once,
populates a shared `(normalized_url, strategy)` cache, and exposes the canonical
provider only when at least one snapshot succeeds. If every request fails, PSI
rules are `NOT_CHECKED + UNKNOWN`; error snapshots remain diagnostic evidence
but never become an SEO PASS or FAIL.

Configuration is validated at provider construction. Sample limits are bounded
positive integers and strategies are restricted to `mobile` and `desktop`,
deduplicated in caller order. Invalid environment configuration falls back to
safe defaults instead of making module import fail.

## Security and compatibility

- The API key is read from environment/process memory only and is never logged,
  serialized, documented, or committed.
- The shared PSI HTTP client and existing MCP tool signatures remain unchanged.
- Mocked tests cover success, missing key, 400/429/5xx, timeout, malformed
  responses, caching, sampling limits, and provider-to-rule data flow.
- Live validation emits only a sanitized structural summary.
