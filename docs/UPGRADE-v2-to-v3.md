# Upgrade from legacy audits to Master Audit V3

V3 is additive and defaults off. Existing MCP tools, legacy CSV columns, audit session behavior, and ZIP delivery remain available.

## Upgrade procedure

1. Back up the current deployment configuration and any portable snapshot baselines.
2. Pull the release and rebuild/install `requirements.txt`.
3. Copy new variables from `.env.example`; do not copy credentials into source-controlled files.
4. Keep `MASTER_AUDIT_V3_ENABLED=false` for the first restart and run a legacy smoke audit.
5. Set `MASTER_AUDIT_V3_ENABLED=true` and enable only providers for which authoritative credentials or read-only inputs are available.
6. Run a small audit, call `librecrawl_master_audit_status`, and confirm exactly 80 coverage rows. Missing providers must be `NOT_CHECKED/UNKNOWN`.
7. Download `audit-snapshot-v1.json.gz` or keep it on the persistent `/snapshots` volume for future comparison.
8. Compare legacy and enhanced reports, then roll out to larger sites.

## Compatibility notes

- `impl_status`, adapter existence, execution status, and result status are separate concepts.
- The 8 genuinely manual rules intentionally remain `NEW_MANUAL`.
- V3 task columns are additive; consumers should read CSVs by column name.
- The ZIP contains every registered artifact, so V3 increases its file count.
- Provider clients are created fresh for each audit. Credentials and fixed date windows are not retained between sites.
- A completed manual-review file is ingested on a rerun through `MANUAL_REVIEW_INPUT_PATH`.

## Rollback

Set `MASTER_AUDIT_V3_ENABLED=false` and restart the MCP service. This disables the V3 pipeline without deleting legacy artifacts or portable snapshots. No database migration is required.
