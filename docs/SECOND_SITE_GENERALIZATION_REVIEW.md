# Second Real-World Site Generalization Review

**Site:** https://gelgoogsort.com/ · **Audit date:** 2026-08-10
**Run:** `feat/technology-intelligence-v1` @ `f1ab038` (Technology Intelligence V1)
**Crawl session:** `44d7ff51af874b00` · **Replay SHA-256:**
`2a43b7075d716a60ae5faa90b64ec95184efc14d9ed6c1c0b9fa229ba5319728`

---

## 1. Detected site profile (gelgoogsort)

GELGOOG — fruit & vegetable sorting equipment manufacturer. Bilingual
WordPress-style site (en-US / es-ES), product/ + es/ + news/ + category/
architecture. 228 pages crawled; URL architecture `/product/`, `/es/`,
`/news/`, `/category/`, product-line landing pages, `/about/`.

## 2. Technology evidence

- `asset_path`: `/wp-content/uploads/...` (favicon, images) across news pages.
- `robots_meta`: `index, follow, max-image-preview:large, max-snippet:-1,
  max-video-preview:-1` on every page (Yoast-style output).
- `analytics_fingerprint`: `ga4_id`, `gtm_id` present in crawl export.
- Source HTML `scripts`/`stylesheets`/`response_headers` were **not populated
  by the upstream LibreCrawl engine** this round (engine export gap, recorded,
  not fabricated); detection still worked from persisted images/robots/
  analytics/URL evidence.

## 3. Confidence

| Technology | Category | Status | Confidence |
|---|---|---|---|
| WordPress | CMS | CONFLICTING | Low |
| WooCommerce | Ecommerce | CONFLICTING | Low |
| Yoast SEO | SEO Technology | DETECTED | Low |
| GA4 | Analytics | DETECTED | High |
| GTM | Tag Manager | DETECTED | High |

Two independent strong analytics fingerprints → High. Single weak
`robots_meta` signal → Low. Conflicting CMS signals (WordPress + WooCommerce
cross-category conflict) → CONFLICTING / Low.

## 4. 80 rules operational

**PASS.** All 80 rules executed through the standard pipeline (80 coverage
rows); no rule added, removed, or domain-special-cased. Technology
Intelligence contributed profile/evidence/applicability/risk correlation
only.

## 5. CMS applicability correct?

**YES.** WordPress detection is CONFLICTING/Low → observation only per the
confidence gate → #36–39/#64–69 stay NOT_APPLICABLE (site profile remains
generic). WordPress detection never auto-PASSed or auto-FAILed any rule.

## 6. Rules still requiring privileged data

GSC (#2/#5/#16/#25/#34/#44/#52/#75/#76), Semrush (#31/#77), GA4 (#34/#35),
Server Logs (#5/#20/#33), Rendered DOM (#46/#48/#80), PSI field/CrUX
(#19/#61/#62/#63). These remain NOT_CHECKED / EXECUTED_PARTIAL / 
MANUAL_REVIEW_REQUIRED per contract — no mock, no fabricated PASS.

## 7. Baolai assumptions found

- The offline bundle validation gate treated any Rule 1/6 task as a pipeline
  failure; gelgoogsort has a **real** Rule 6 finding (www/non-www redirect
  missing). Gate fixed generically: findings stay visible, bundle integrity
  is judged on structural gates only.
- `generate_80item_report.py` hardcoded a Baolai `SITE_URL` default; the
  generator is env-parameterized and was driven with `SITE_URL` for this run.
- Coverage bookkeeping assumed NOT_APPLICABLE rules carry no client findings;
  #39 had a phantom `finding_count=1`. Normalization now zeroes
  NOT_APPLICABLE finding counts for every rule (generic invariant).

## 8. Gelgoogsort-specific temptation / hardcode

**NONE.** Production hardcode scan (baolaipackaging / gelgoogsort /
yashengcrafts) over `audit_rules/technology/` + runtime files is clean. No
`if domain == ...` anywhere. The real crawl is a validation input, not a
hardcoded test fixture.

## 9. Generic false positives found

- Webflow signature `script_src /assets/.*\.js` (weak) can fire on any site
  with an `/assets/` JS bundle — low-confidence only, flagged as a known weak
  signature, not a confirmed claim.
- Upstream crawler start race aborted the first crawl attempt after 9–40
  pages; fixed generically (see #10).
- #39 XML-RPC/REST API observation counted as a client finding on a
  NOT_APPLICABLE rule; fixed generically (see #10).

## 10. Generic engine fixes made

1. **Server header signature matching** — `^server$.*nginx` can never match
   `server=nginx`; corrected to `^server[:=].*nginx` (nginx/Apache/LiteSpeed/
   Cloudflare).
2. **Crawl completion gate** — the runner declared the crawl complete on a
   single `is_running=false` snapshot right after `start_crawl`; now requires
   consecutive terminal snapshots (regression: `test_runner_crawl_completion_gate.py`).
3. **Replay technology persistence** — the crawl-time Technology Profile is
   now embedded in `audit-replay-v1` (regression:
   `test_runner_replay_persists_technology_profile`).
4. **NOT_APPLICABLE finding counts** — coverage `finding_count` must equal
   Detailed Findings rows; all NOT_APPLICABLE rows are zeroed.
5. **Optional performance artifact** — PSI provider unavailable/timeout no
   longer breaks report generation; gap is recorded in metrics.

## 11. Technology Profile replay-rebuildable?

**YES.** Offline reconstruction from the 228-page replay
(`reconstruct_technology_profile`) reproduces the identical five detections
(WordPress/WooCommerce CONFLICTING, Yoast Low, GA4/GTM High) — crawl evidence
parity, replay technology parity, and artifact parity verified. The replay
also embeds the crawl-time profile snapshot (schema/detector/registry
versions).

## 12. DOCX cross-site?

**YES.** Rendered DOCX (76 pages, LibreOffice): Gelgoog cover + headers, no
Baolai text, Website Technology Profile + Technology Risks sections present,
80 audits, summary table landscape (pages 11–13) with portrait recovery, zero
blank pages, zero overflow, no raw dicts, no sensitive values, no malformed
hyperlinks.

## 13. Does the second site prove the system generalizes?

**YES.** The pipeline ran a completely different site with a different
technology stack, CMS confidence conflict, missing PSI/privileged data, and
real Rule 1/6/8 findings — without any domain-specific logic. All fixes
surfaced by the second site were generic.

## 14. Is external enrichment needed next?

**Not for v1.** The local detector produced a defensible profile; the
optional enrichment interface + no-op provider is in place. A
BuiltWith/Wappalyzer-style provider would raise CMS confidence (resolving the
WordPress CONFLICTING case) but is not required for acceptance.

## 15. SECOND_SITE_ACCEPTANCE

**PASS.** Score 85.94 / 100 · Coverage 54.29% · Confidence High (85.19%).
228/228 pages, NOT_TRUNCATED, replay 228 pages / 14,410 links, technology
profile + risks in DOCX and `09_Technology_Profile.json`, final ZIP SHA-256
`f319bdd1606816a8acc8bc93c7596ab85d6561e4d32b4d65275e625d7368d4bd`.
