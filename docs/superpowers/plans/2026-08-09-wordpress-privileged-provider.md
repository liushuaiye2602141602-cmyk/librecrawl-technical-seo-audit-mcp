# WordPress Privileged Provider Implementation Plan

1. Add failing provider contract tests for opt-in availability, schema and host
   validation, secret rejection, privacy-safe normalization, and registration.
2. Implement the read-only JSON snapshot provider and pass focused tests.
3. Add failing rule tests for Rules 36, 64, 65, 68, and 69, including their
   required partial/manual boundaries.
4. Implement and register the five checks, then update the source mapping CSV.
5. Add configuration, collector-contract, validation, matrix, and handoff docs.
6. Run focused and full regression tests, validate JSON/CSV artifacts, scan for
   secrets, and commit each completed subsystem.
