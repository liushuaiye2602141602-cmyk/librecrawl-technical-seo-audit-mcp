# Server log provider implementation plan

1. TDD Apache/Nginx combined and JSON line parsing, bot classification, privacy-safe normalization, and malformed handling.
2. TDD streaming aggregation, max-line truncation, configuration gates, and runner registration.
3. TDD Rule 33 findings and Rule 5 bot-frequency enrichment, including unavailable/partial evidence.
4. Bind Rule 33 and migrate only its source-of-truth classification.
5. Update configuration and handoff artifacts, run full regressions, and verify no raw log secrets enter outputs.
