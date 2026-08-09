# Server log provider validation

Status: `IMPLEMENTED / INPUT_VALIDATION_PENDING`

The V3 runner now registers a streaming local access-log provider. It supports Apache/Nginx Combined lines and common structured JSON fields, classifies major search bots, redacts IP/user-agent/query values, and aggregates status, bot, URL-pattern, crawl-waste, and optional response-time evidence. Processing is line-bounded and malformed/truncated input is explicit.

Rule 33 is executable; Rule 5 now adds observed bot-hit frequency to URL-pattern findings and stays partial because GSC Crawl Stats is not available through the implemented API set. Rule 64 remains privileged/manual.

Validation covers both formats, redaction, bot classification, aggregation, truncation, missing/invalid files, provider registration, Rule 33 thresholds, Rule 5 enrichment, and full regression: 617 passed. Production validation remains dependent on a user-supplied real access-log file.
