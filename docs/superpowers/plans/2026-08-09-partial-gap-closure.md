# Existing-partial crawl gap closure implementation plan

## Task 1: Execution truth

- Add failing coverage tests for missing adapters, adapter exceptions, and
  explicit data-unavailable checks.
- Record completed rule IDs and per-rule not-checked reasons in the harness.
- Require execution evidence in production RuleRunner coverage computation.

## Task 2: Rules 2, 5, and 13

- Add false-positive and issue tests for sitemap status/indexability,
  parameter/session/calendar/faceted URL patterns, and title
  missing/duplicate/estimated truncation.
- Implement the checks in `audit_rules/checks/foundation_gaps.py` and register
  them lazily.

## Task 3: Rules 23, 25, and 66

- Test case-insensitive Cache-Control/Age/CDN headers, missing header data,
  HTTPS coverage, mixed-content raw exports, optional TLS evidence, and
  WordPress dynamic-page cache leaks.
- Implement without additional HTTP requests and preserve unavailable states.

## Task 4: Rule 40 task contract

- Add tests for real Finding field names and exact actionable task columns.
- Repair and extend task CSV generation while preserving existing columns.
- Register the output-stage adapter and production availability marker.

## Task 5: Registry and verification

- Update seven mapping rows with actual functions/modules and honest remaining
  gaps; keep classifications partial where acceptance criteria remain external.
- Update adapter-count integrity tests from 48 to 55.
- Run focused tests, full regression, placeholder/security scans, and update
  current handoff facts before committing subsystem checkpoints.
