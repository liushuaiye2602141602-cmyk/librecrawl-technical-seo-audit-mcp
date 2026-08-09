# PageSpeed live validation implementation plan

**Goal:** Connect PSI to the production V3 runner, make configuration and API
failure semantics explicit, validate the supplied key live, and update handoff
facts without persisting secrets.

## Task 1: Canonical provider registration and runtime configuration

- Add failing tests proving `_get_runner()` registers one `PageSpeedDataProvider`
  under `PageSpeed API` and missing credentials keep it unavailable.
- Add safe parsers for `PSI_SAMPLE_LIMIT` and `PSI_STRATEGIES`; reject invalid
  strategies and fall back safely for invalid environment values.
- Register the provider in the cached integration runner.

## Task 2: Honest all-error and partial-success coverage

- Add runner tests for one successful snapshot, all requests failing, and a
  mixed batch.
- Expose `PageSpeed API` only when at least one sampled snapshot succeeds.
- Preserve cached error snapshots for diagnostics; all-error coverage must be
  `NOT_CHECKED + UNKNOWN`, never PASS/FAIL.

## Task 3: PSI client failure contract

- Add mocked client tests for missing keys, valid normalization, HTTP 400, 429,
  5xx, timeouts, and malformed/non-object JSON.
- Sanitize provider errors and prevent accidental credential reflection.
- Keep the existing dict interface and the single canonical HTTP call.

## Task 4: Live validation and handoff

- Run the client and provider against `https://example.com/` using the supplied
  credential only in a process-scoped environment variable.
- Verify mobile parsing and provider snapshot conversion; do not print raw
  responses or credentials.
- Run focused and full test suites, update the Phase 3 report/current state,
  and commit the verified PSI checkpoint.
