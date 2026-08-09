# Final Client Report Consistency

**Date:** 2026-08-09
**Run:** single post-correction offline run over the accepted replay.

| Metric | Value | Check |
|---|---|---|
| Audit rows | 80 | PASS |
| Matrix rows | 80 | PASS |
| Coverage rows | 80 | PASS |
| Detailed finding rows | 909 | PASS |
| Task rows | 905 | PASS |
| Manual rows | 9 | PASS |
| Performance rows | 5 | PASS |
| Confirmed remediation | 321 | PASS |
| Optimization | 460 | PASS |
| Data-required | 17 | PASS |
| Manual-review actions | 9 | PASS |
| P0/P1/P2/P3 confirmed remediation | 0/2/319/0 | PASS |
| Score | 90.35 | PASS |
| Coverage | 64.29% | PASS |
| Confidence | High (87.32%) | PASS |
| PDF pages | 72 | PASS |

## Artifact hashes

- `01_80_Item_Master_SEO_Diagnostic_Report.html`: `71b92059fe46804171841b5feaeb47e2e81f10b01baa202ed20fcf275ad8f580`
- `01_80_Item_Master_SEO_Diagnostic_Report.pdf`: `598711fe293b31848acac78f0e65e671606eea28fc8714db9e6ae23990ae9ba6`
- `02_80_Item_Master_SEO_Diagnostic_Report.md`: `2a3513ede20fbc2b50b920a33e1b6f173d887e8fac0cca93aa0972aed46dc7bb`
- `03_80_Item_Diagnostic_Matrix.csv`: `21fb604c2453f79a6e0359d54b472c88651461e9d4246c9ab52eef99400033a3`
- `04_Detailed_URL_Findings.csv`: `f4da632c4310d2b065224a4474fba19f5705c80613ac5027d1e20dc2d4eb5da4`
- `05_Remediation_Tasks.csv`: `accf853a1957cc99510dcf77d18529bb146ac2b7ad1b916cfad1c2de751e88ad`
- `06_Manual_Review.csv`: `462b837022f57b7378d934c80a4c3f061470fe020363477fb74d31d2bfa616c4`
- `07_Performance_Data.csv`: `acaaaf266a6cf1ed34cf24da6c4630126d1bf1a964c25658e65b258335702e26`
- `08_Audit_Score.json`: `6b25648b85e6c8fa9ffe1aaa26a95d26bc0fc679f3a9298e16254b0d05228e73`
- `09_80_Rule_Coverage.csv`: `aeca3fdde4d947b6e413b94555bc9309b3c819c12b47a91c0f42821aec8c8d7d`
- `80_Item_Diagnostic_Data.xlsx`: `4556fac1da84ffb61eb9eb1e57659b4f230f658947b5e9e70078311c0cb7316f`
- `metrics.json`: `c51247da5f30d618b33dc2f1abc14ee3357097cc41a6b7389768fc4e022689ba`
- `README.txt`: `5c8e3587d6a26a1b8b9c3eeb28b95b34a2991361eb0ea82777fa10a02accd1a7`
- `Technical_Appendix\01_audit-replay-v1.json.gz`: `f38e2a45047107d80b644014770123a9855eb5a45762ae044d80e085ae39424f`
- `Technical_Appendix\02_audit-snapshot-v1.json.gz`: `746d0290bfad8d41eb097854e88d6351432de904917171f25078990cdab0e03a`
- `Technical_Appendix\03_artifact-manifest.json`: `50c6d32d6de57995422f998d98c4e1a2812038e973526e3e6bd41f16e896cc85`
- `Technical_Appendix\04_INTERNAL_VALIDATION.md`: `2623ee44b5a72b88c6756fdda720cef578bc3cf1904df697750403c4a6451cf5`

All checks PASS ? CSV/XLSX/ZIP report the same post-correction run.

## FINAL WORD DELIVERY (DOCX)

| Check | Value | Result |
|---|---|---|
| Primary format | DOCX (`01_80_Item_Master_SEO_Diagnostic_Report.docx`) | PASS |
| PDF in client ZIP | None (PDF is optional `REPORT_FORMAT=pdf` internal export only) | PASS |
| DOCX render (LibreOffice 25.2 headless) | 70 pages, 3 landscape summary pages, 0 blank pages | PASS |
| DOCX link annotations | 140, all real http(s) URLs; literal `<a href>` stays plain text | PASS |
| Audit #01?#80 | 80 real Heading 2 paragraphs | PASS |
| Summary table | 81 rows x 9 cols, real Word table, repeated header, landscape, portrait restored | PASS |
| Word styles | Title/Subtitle/Heading 1-3/Normal/List Bullet real styles | PASS |
| Manual review | 9 actions (8 core #53-57/#71-73 + #70 PARTIAL_MANUAL_VALIDATION) | PASS |
| No engine metadata in client body | PASS |
| DOCX regression tests | 10 passing (`tests/phase12/test_docx_report.py`) | PASS |
| Full test suite | 832 passed / 0 failed | PASS |