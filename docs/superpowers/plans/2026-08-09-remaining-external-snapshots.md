# Remaining External Snapshot Providers Plan

1. Add failing provider tests for flags, schemas, host/age validation, privacy,
   normalization, bounds, and integration registration.
2. Implement rendered-DOM and availability snapshot providers.
3. Add failing rule tests for Rules 46, 48, and 80, including partial-evidence
   and unavailable-evidence behavior.
4. Implement and register checks; migrate the three mapping rows from
   `NEW_EXTERNAL_DATA` to `EXISTING_PARTIAL`.
5. Add configuration and collector-contract documentation, synchronize the
   handoff matrix and counts, run full regressions, and scan for secrets.
