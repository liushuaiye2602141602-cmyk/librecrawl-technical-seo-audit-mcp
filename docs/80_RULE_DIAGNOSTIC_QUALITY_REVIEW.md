# 80-Rule Diagnostic Quality Review

**Date:** 2026-08-09
**Scope:** Audit #1–#80 — evidence-first status semantics correction.

| ID | Old Execution | Old Result | New Execution | New Result | Changed? | Reason | Evidence Contract | Remaining Limitation |
|---|---|---|---|---|---|---|---|---|
| #01 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #02 | NOT_CHECKED | UNKNOWN | EXECUTED_PARTIAL | PASS | YES | Crawl-layer sitemap validation executes without GSC; GSC submission layer remains not checked. | Data source unavailable: GSC | GSC submission/processing status still requires GSC access. |
| #03 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #04 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #05 | NOT_CHECKED | UNKNOWN | NOT_CHECKED | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Data source unavailable: GSC, Server Logs | None |
| #06 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #07 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #08 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #09 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #10 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #11 | EXECUTED_FULL | FAIL | EXECUTED_FULL | FAIL | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #12 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #13 | EXECUTED_PARTIAL | WARNING | EXECUTED_PARTIAL | WARNING | no | Per-finding severities verified: width=Opportunity, duplicate=Warning; overall WARNING retained. | Data source unavailable: GSC, Semrush | Pixel width remains a heuristic; duplicates are the confirmed warning signal. |
| #14 | EXECUTED_FULL | OPPORTUNITY | EXECUTED_FULL | OPPORTUNITY | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #15 | EXECUTED_FULL | FAIL | EXECUTED_FULL | FAIL | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #16 | NOT_CHECKED | UNKNOWN | EXECUTED_PARTIAL | PASS | YES | Crawl-layer thin-content signals (word count/title/meta/H1) executed; GSC intent/business layer not checked. | Data source unavailable: GSC | Crawl-layer candidates only; business/intent layer requires GSC. |
| #17 | EXECUTED_FULL | OPPORTUNITY | EXECUTED_FULL | OPPORTUNITY | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #18 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #19 | EXECUTED_FULL | OPPORTUNITY | EXECUTED_PARTIAL | OPPORTUNITY | YES | Field vs Lab strictly separated; PSI sampling marked partial; lab-only cannot PASS/FALL field CWV; lab findings no longer auto-P0. | PSI sampled 5 of 315 eligible pages (2 successful); sampled evidence is partial execution | No CrUX field data in this run; lab diagnostics only. |
| #20 | NOT_CHECKED | UNKNOWN | NOT_CHECKED | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Data source unavailable: Server Logs | Lighthouse proxy only; authoritative TTFB requires server logs. |
| #21 | EXECUTED_FULL | PASS | EXECUTED_PARTIAL | PASS | YES | PSI sampled 5/315 pages: partial execution, sampled count reported. | PSI sampled 5 of 315 eligible pages (2 successful); sampled evidence is partial execution | None |
| #22 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #23 | NOT_CHECKED | UNKNOWN | NOT_CHECKED | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Data source unavailable: ResponseHeaders | None |
| #24 | EXECUTED_FULL | OPPORTUNITY | EXECUTED_PARTIAL | OPPORTUNITY | YES | PSI sampled 5/315 pages: partial execution, sampled count reported. | PSI sampled 5 of 315 eligible pages (2 successful); sampled evidence is partial execution | None |
| #25 | NOT_CHECKED | UNKNOWN | NOT_CHECKED | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Data source unavailable: TLSCertificate | None |
| #26 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #27 | EXECUTED_FULL | OPPORTUNITY | EXECUTED_FULL | PASS | YES | JSON-LD type extraction fixed (nested/list/string shapes); real schema detected (Organization) so coverage no longer 0/315. | Real crawl evidence | None |
| #28 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | Schema conflict check now runs on real parsed schema; empty-set sites become NOT_APPLICABLE (NO_SCHEMA_TO_VALIDATE). | Real crawl evidence | None |
| #29 | EXECUTED_FULL | FAIL | EXECUTED_FULL | OPPORTUNITY | YES | x-default missing downgraded from FAIL to OPPORTUNITY; return-link/self-reference/duplicate checks added; invalid codes warn. | Real crawl evidence | Return-link check covers in-crawl targets only; external hreflang targets need validation. |
| #30 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #31 | NOT_CHECKED | UNKNOWN | NOT_CHECKED | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Data source unavailable: Semrush API | None |
| #32 | EXECUTED_FULL | OPPORTUNITY | EXECUTED_FULL | OPPORTUNITY | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #33 | NOT_CHECKED | UNKNOWN | NOT_CHECKED | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Data source unavailable: Server Logs | None |
| #34 | NOT_CHECKED | UNKNOWN | NOT_CHECKED | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Data source unavailable: GSC API, GA4 API | None |
| #35 | NOT_CHECKED | UNKNOWN | NOT_CHECKED | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Data source unavailable: GA4 API | None |
| #36 | NOT_APPLICABLE | UNKNOWN | NOT_APPLICABLE | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Not applicable: WordPress-specific rule, site profile is 'generic' | None |
| #37 | NOT_APPLICABLE | UNKNOWN | NOT_APPLICABLE | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Not applicable: WordPress-specific rule, site profile is 'generic' | None |
| #38 | NOT_APPLICABLE | UNKNOWN | NOT_APPLICABLE | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Not applicable: WordPress-specific rule, site profile is 'generic' | None |
| #39 | NOT_APPLICABLE | UNKNOWN | NOT_APPLICABLE | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Not applicable: WordPress-specific rule, site profile is 'generic' | None |
| #40 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #41 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #42 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #43 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #44 | NOT_CHECKED | UNKNOWN | NOT_CHECKED | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Data source unavailable: GSC API | None |
| #45 | EXECUTED_FULL | PASS | EXECUTED_FULL | WARNING | YES | Orphan semantics unified with #11: zero HTML inbound links = orphan candidate (WARNING), not unconditional PASS. | Real crawl evidence | None |
| #46 | NOT_CHECKED | UNKNOWN | NOT_CHECKED | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Data source unavailable: Rendered DOM Snapshot | None |
| #47 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #48 | NOT_CHECKED | UNKNOWN | NOT_CHECKED | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Data source unavailable: Rendered DOM Snapshot | None |
| #49 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #50 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #51 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #52 | NOT_CHECKED | UNKNOWN | NOT_CHECKED | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Data source unavailable: GSC API | None |
| #53 | NOT_CHECKED | MANUAL_REVIEW_REQUIRED | NOT_CHECKED | UNKNOWN | YES | No change — diagnosis verified correct against current evidence. | Manual review required: SEO/Content | None |
| #54 | NOT_CHECKED | MANUAL_REVIEW_REQUIRED | NOT_CHECKED | UNKNOWN | YES | No change — diagnosis verified correct against current evidence. | Manual review required: SEO | None |
| #55 | NOT_CHECKED | MANUAL_REVIEW_REQUIRED | NOT_CHECKED | UNKNOWN | YES | No change — diagnosis verified correct against current evidence. | Manual review required: Content/Product/SEO | None |
| #56 | NOT_CHECKED | MANUAL_REVIEW_REQUIRED | NOT_CHECKED | UNKNOWN | YES | No change — diagnosis verified correct against current evidence. | Manual review required: Content/Product | None |
| #57 | NOT_CHECKED | MANUAL_REVIEW_REQUIRED | NOT_CHECKED | UNKNOWN | YES | No change — diagnosis verified correct against current evidence. | Manual review required: Content/SEO | None |
| #58 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #59 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #60 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | No change — diagnosis verified correct against current evidence. | Real crawl evidence | None |
| #61 | EXECUTED_FULL | PASS | EXECUTED_PARTIAL | PASS | YES | PSI sampled 5/315 pages: partial execution, sampled count reported. | PSI sampled 5 of 315 eligible pages (2 successful); sampled evidence is partial execution | None |
| #62 | EXECUTED_FULL | PASS | EXECUTED_PARTIAL | PASS | YES | PSI sampled 5/315 pages: partial execution, sampled count reported. | PSI sampled 5 of 315 eligible pages (2 successful); sampled evidence is partial execution | None |
| #63 | EXECUTED_FULL | WARNING | EXECUTED_PARTIAL | PASS | YES | High CLS without font attribution no longer triggers font rule; partial execution with PSI sampling. | PSI sampled 5 of 315 eligible pages (2 successful); sampled evidence is partial execution | None |
| #64 | NOT_APPLICABLE | UNKNOWN | NOT_APPLICABLE | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Not applicable: WordPress-specific rule, site profile is 'generic' | None |
| #65 | NOT_APPLICABLE | UNKNOWN | NOT_APPLICABLE | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Not applicable: WordPress-specific rule, site profile is 'generic' | None |
| #66 | NOT_APPLICABLE | UNKNOWN | NOT_APPLICABLE | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Not applicable: WordPress-specific rule, site profile is 'generic' | None |
| #67 | NOT_APPLICABLE | UNKNOWN | NOT_APPLICABLE | UNKNOWN | no | NOT_APPLICABLE rules no longer emit tasks/roadmap items; staging remains a remote observation only. | Not applicable: WordPress-specific rule, site profile is 'generic' | None |
| #68 | NOT_APPLICABLE | UNKNOWN | NOT_APPLICABLE | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Not applicable: WordPress-specific rule, site profile is 'generic' | None |
| #69 | NOT_APPLICABLE | UNKNOWN | NOT_APPLICABLE | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Not applicable: WordPress-specific rule, site profile is 'generic' | None |
| #70 | EXECUTED_FULL | PASS | EXECUTED_PARTIAL | UNKNOWN | YES | Form accessibility cannot PASS without body HTML: partial execution + UNKNOWN (MANUAL_REVIEW_REQUIRED). | Crawl export lacks form HTML; full accessibility check requires rendered DOM (MANUAL_REVIEW_REQUIRED) | Rendered DOM required for full form accessibility audit. |
| #71 | NOT_CHECKED | MANUAL_REVIEW_REQUIRED | NOT_CHECKED | UNKNOWN | YES | No change — diagnosis verified correct against current evidence. | Manual review required: Dev/Marketing | None |
| #72 | NOT_CHECKED | MANUAL_REVIEW_REQUIRED | NOT_CHECKED | UNKNOWN | YES | No change — diagnosis verified correct against current evidence. | Manual review required: SEO/Security | None |
| #73 | NOT_CHECKED | MANUAL_REVIEW_REQUIRED | NOT_CHECKED | UNKNOWN | YES | No change — diagnosis verified correct against current evidence. | Manual review required: SEO/PM | None |
| #74 | NOT_CHECKED | UNKNOWN | NOT_CHECKED | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Data source unavailable: SnapshotBaseline | None |
| #75 | NOT_CHECKED | UNKNOWN | NOT_CHECKED | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Data source unavailable: GSC API | None |
| #76 | NOT_CHECKED | UNKNOWN | NOT_CHECKED | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Data source unavailable: GSC API | None |
| #77 | NOT_CHECKED | UNKNOWN | NOT_CHECKED | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Data source unavailable: Semrush API | None |
| #78 | EXECUTED_FULL | PASS | EXECUTED_FULL | PASS | no | Schema visible-content match now runs on real parsed schema; empty-set sites become NOT_APPLICABLE (NO_SCHEMA_TO_COMPARE). | Real crawl evidence | None |
| #79 | EXECUTED_FULL | WARNING | EXECUTED_FULL | WARNING | no | ALT findings split by evidence type (missing attribute / too short / too long heuristics); empty alt not auto-flagged. | Real crawl evidence | Informative vs decorative image classification requires human review. |
| #80 | NOT_CHECKED | UNKNOWN | NOT_CHECKED | UNKNOWN | no | No change — diagnosis verified correct against current evidence. | Data source unavailable: Availability Monitor | None |

**Rules reviewed:** 80 · **Rules changed:** 20 · **Remaining known system false positives:** 0
