# WordPress Privileged Snapshot Provider

## Status

The provider, privacy validation, five rules, and integration contracts are
implemented and fixture-validated. Validation with a real administrator-
generated snapshot is pending because no WordPress privileged export was
provided.

## Safety model

The audit service reads one local JSON file and has no WordPress credentials,
remote endpoint client, WP-CLI runner, SQL client, or mutation method. The file
is capped at 5 MiB, must match the audited hostname, and is rejected when older
than `WP_AUDIT_MAX_AGE_HOURS`.

The contract forbids fields named `password`, `secret`, `token`, `api_key`,
`api_token`, `authorization`, `cookie`, `username`, `user_login`, `email`, `ip`,
or `value` anywhere in the JSON tree. Administrator records contain only a 2FA
boolean. Autoload records contain option names and byte counts, never values.

## Contract

```json
{
  "schema_version": "wordpress-audit-v1",
  "collected_at": "2026-08-09T06:30:00+00:00",
  "site_url": "https://example.com",
  "core": {"version": "6.6.1", "update_available": false, "vulnerable": false},
  "php": {"version": "8.2.20"},
  "plugins": [
    {
      "slug": "example-plugin",
      "version": "1.2.3",
      "status": "active",
      "update_available": false,
      "last_updated_days": 30,
      "abandoned": false,
      "vulnerable": false
    }
  ],
  "themes": [],
  "cron_events": [
    {"hook": "daily_cleanup", "interval_seconds": 86400, "overdue_seconds": 0}
  ],
  "autoload": {
    "total_bytes": 400000,
    "largest_options": [{"name": "example_cache", "bytes": 80000}]
  },
  "administrators": [{"two_factor_enabled": true}]
}
```

The administrator-side collector is trusted to determine update availability,
vulnerability and abandonment booleans from approved sources. The audit report
keeps those judgments explicitly partial and requires provenance review.

## Rules

- 36: updates and explicitly reported vulnerable core/components;
- 64: tasks overdue by at least five minutes and recurring under one minute;
- 65: autoload total above 800 KiB and individual options above 100 KiB;
- 68: aggregate administrator 2FA coverage;
- 69: inactive, explicitly abandoned, or at least 730-day stale components.

All five fail closed when evidence is unavailable. Even with a valid snapshot,
they are `EXECUTED_PARTIAL` because staging regression, exploitability, job
necessity, DBA cleanup safety, WAF controls, and maintenance-source provenance
remain human decisions.
