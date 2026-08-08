# WordPress Privileged Snapshot Provider Design

## Goal

Close the privileged-data gaps in Rules 36, 64, 65, 68, and 69 without
placing WordPress, database, or SSH credentials inside the audit service.

## Security boundary

The provider reads a local, administrator-generated JSON snapshot. It does not
log in to WordPress, execute WP-CLI, query a database, or expose mutation
methods. The snapshot contract must not contain passwords, tokens, option
values, email addresses, usernames, IP addresses, or raw database rows.

Configuration is opt-in:

- `MASTER_AUDIT_WORDPRESS_ENABLED=true`
- `WP_AUDIT_EXPORT_PATH=/read-only/path/wordpress-audit.json`

The file must declare `schema_version: wordpress-audit-v1`. Invalid schemas,
unknown top-level secrets, malformed component records, or a site URL that does
not match the audited host make the provider unavailable. A valid snapshot sets
the site profile to `wordpress` before applicability is evaluated.

## Normalized evidence

The provider emits `shared_data["wordpress_privileged"]` containing only:

- core/PHP versions and update booleans;
- plugin/theme slugs, status, update status, maintenance age, and explicit
  abandoned/vulnerable booleans;
- cron hook names, schedule intervals, and overdue seconds;
- aggregate autoload bytes plus option names and byte sizes (never values);
- administrator totals and count without 2FA (never identities);
- collection time and non-sensitive validation warnings.

## Rule behavior

- Rule 36 flags available core/plugin/theme updates and explicitly reported
  vulnerable components. It remains partial because exploitability and
  staging regression require security/human review.
- Rule 64 flags overdue cron events and sub-minute recurring jobs. It remains
  partial because request duration and business necessity need logs/human
  interpretation.
- Rule 65 warns above 800 KiB total autoload or 100 KiB per option. It remains
  partial because slow-query and safe-removal analysis need a DBA.
- Rule 68 flags any administrator without 2FA. It remains partial because WAF,
  recovery, and login-rate-limit controls are outside the snapshot.
- Rule 69 flags inactive retained components and components explicitly marked
  abandoned or not updated for at least 730 days. It remains partial because
  maintenance status is supplied by the trusted collector.

All five checks fail closed with `NOT_CHECKED`, never PASS, when the snapshot is
missing, stale, invalid, or host-mismatched.

## Validation

Tests cover schema rejection, secret-field rejection, host matching, privacy
normalization, provider integration, findings, partial-execution boundaries,
and missing-evidence behavior. Live validation requires a real administrator-
generated snapshot and is documented as pending when none is supplied.
