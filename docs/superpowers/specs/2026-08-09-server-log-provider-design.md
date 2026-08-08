# Server log provider design

## Outcome

Add a local, streaming server-access-log provider that turns Apache/Nginx combined logs and structured JSON logs into bounded crawler evidence without loading whole files into memory.

## Input and safety

`MASTER_AUDIT_SERVER_LOGS_ENABLED`, `SERVER_LOG_PATH`, and `SERVER_LOG_MAX_LINES` configure an explicitly named file. The provider performs read-only streaming, caps processed lines, counts malformed lines, and stores aggregates only. Raw user agents, client IPs, query values, and log lines are not copied into audit artifacts.

## Normalization

Each accepted line yields method, normalized request target, status, user-agent class, and optional response time. Supported bots: Googlebot, Bingbot, YandexBot, Baiduspider, and a generic bot class. Aggregates include status, bot, URL, bot×URL, response-time distribution, crawl-waste patterns, processed/malformed counts, and truncation.

## Rules

- Rule 33 reports crawl volume/bot composition and flags high bot error or waste ratios.
- Rule 5 consumes actual bot-hit frequencies to prioritize locally detected session/search/calendar/faceted URL waste. It remains partial because GSC Crawl Stats is not exposed by the current GSC provider.
- Rule 20 may consume response-time aggregates as supporting evidence, but access-log duration is not automatically labeled TTFB unless the structured field explicitly says so.
- Rule 64 stays manual/privileged; access frequency alone cannot enumerate WordPress scheduled tasks.

Missing files, unreadable input, zero valid lines, and parser-wide failure make the provider unavailable. Truncated/malformed evidence is explicitly partial.
