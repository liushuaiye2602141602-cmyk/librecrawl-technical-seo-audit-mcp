# Semrush provider implementation plan

1. Write failing tests for v4 authorization, request parameters, caching, payload validation, and sanitized failures.
2. Implement the Semrush v4 backlinks client.
3. Write failing provider tests for configuration, target resolution, partial success, and runner registration.
4. Implement and register the provider under `Semrush API`.
5. Write failing Rule 31 and Rule 77 checks, including partial and unavailable evidence.
6. Bind checks, migrate source-of-truth rows, update configuration and handoff state.
7. Run focused and complete regression suites plus a secret-pattern scan.
