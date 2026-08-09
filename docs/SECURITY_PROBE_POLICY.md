# Security probe policy

The audit is read-only. Security findings are based on crawl-visible headers, TLS/snapshot evidence, public WordPress output, and administrator-supplied read-only summaries.

## Allowed

- bounded GET/HEAD requests already required for crawling and link validation;
- passive inspection of response headers, mixed content, staging signals, and public version markers;
- validation of host-bound local evidence files;
- bounded provider API reads with documented scopes and quotas.

## Prohibited

- credential guessing, password testing, brute force, or account enumeration;
- exploit payloads, XML-RPC pingback abuse, destructive requests, or write methods;
- mass DNS/subdomain enumeration;
- database, WordPress, or production content writes;
- treating a reachable REST/XML-RPC endpoint as proof of vulnerability.

There is intentionally no environment flag that enables aggressive probes. Provider absence or probe unavailability produces `NOT_CHECKED/UNKNOWN`, not a fabricated security PASS or website FAIL.

Server logs discard client IPs, raw user agents, query values, and source lines. Snapshot providers reject sensitive keys and cross-site evidence. CSV writers neutralize spreadsheet formulas. Secrets belong in process/container environment injection and must never be committed.
