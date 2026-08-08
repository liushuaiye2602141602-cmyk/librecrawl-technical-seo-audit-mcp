# GA4 provider design

## Outcome

Add an OAuth-backed Google Analytics 4 provider that distinguishes property configuration, configured key events, observed event counts, and daily data continuity. Missing credentials or API families never become tracking passes.

## API boundary

- Admin API `properties.get` for property identity/state.
- Admin API `properties.keyEvents.list` with token pagination for configured key events.
- Data API `properties:runReport` for daily sessions and event-name counts over a finalized 28-day window.
- OAuth bearer token with `analytics.readonly`; secrets remain process-only.

## Runtime contract

`MASTER_AUDIT_GA4_ENABLED`, `GA4_ACCESS_TOKEN`, and `GA4_PROPERTY_ID` configure the provider. Property IDs are normalized to `properties/{id}`. Requests are cached and all errors are credential-safe. Each API family is isolated; no successful families means the source is unavailable.

## Rules

- Rule 34 cross-checks an accessible, non-trashed GA4 property, observed daily activity, and available GSC property evidence. It remains partial because Bing verification and duplicate client-side tag detection are outside these APIs.
- Rule 35 compares configured GA4 key events with observed event counts, flagging missing key events and key events with zero observations. It remains partial because end-to-end GTM/browser dispatch requires a real submission workflow.

Live validation remains pending until a property-authorized OAuth token and GA4 property ID are supplied.
