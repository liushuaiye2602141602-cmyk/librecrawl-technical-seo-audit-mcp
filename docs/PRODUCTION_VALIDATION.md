# Production validation

Use this checklist after installation or credential rotation. Start with a controlled site or a small safe sample.

## Offline release gate

1. Run the full test suite.
2. Verify the 80-rule registry, 72 adapters, and registered providers.
3. Run `docker compose config -q` and build the image.
4. Run the benchmark and compare with `docs/audit/PERFORMANCE_BENCHMARK.md`.
5. Scan tracked files for secrets and confirm check modules contain no direct HTTP clients.

## Safe live smoke

1. Start a bounded audit with a low page ceiling on a site you are authorized to audit.
2. Keep sitemap concurrency/delay conservative; do not run aggressive security probes.
3. For PSI, sample one or a few URLs—never the full site for a smoke test.
4. Call `librecrawl_master_audit_status` and verify missing providers are `NO_EVIDENCE_ARTIFACT` and dependent rules are `NOT_CHECKED/UNKNOWN`.
5. Download the ZIP and verify its SHA-256, coverage row count, score/coverage/confidence separation, enhanced reports, and portable snapshot.
6. Export the snapshot, run a second controlled audit after a known change, and validate the diff.

## Credential-specific validation

- GSC: use read-only OAuth and a property matching the audited host; test one analytics window and one URL Inspection sample.
- Semrush: use a v4 paid key and a root-domain target that contains the audited host.
- GA4: use `analytics.readonly` for the intended property.
- Server Logs: provide an exact `SERVER_LOG_SITE_HOST` manifest and a small copied log fixture first.
- WordPress/render/availability: generate privacy-safe, host-bound read-only snapshots and validate them before production use.

Do not fabricate evidence when an account, entitlement, or input is missing. Record the item as live-validation pending while keeping the implemented offline contract green.
