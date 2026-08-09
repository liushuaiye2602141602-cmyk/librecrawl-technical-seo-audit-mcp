# Audit scoring and remediation

## Score contract

`audit-score.json` uses `audit-score-v1` / scoring version `1.0`. The quality score includes only executed rules. `NOT_CHECKED` is never treated as PASS and is listed in `not_checked_rules`; `NOT_APPLICABLE` is excluded and listed in `excluded_rules`.

Priority weights are Critical 4, High 3, Medium 2, and Low 1. The maximum penalty for a rule is its priority weight multiplied by the worst finding's severity factor (Error 1.0, Warning 0.55, Opportunity 0.25, Info 0) and evidence confidence. `rule_contributions` exposes each executed rule's weight, penalty, and rule score. Category and overall scores use the same deterministic calculation.

Coverage is the percentage of applicable rules actually executed and is reported separately from quality. Finding confidence is a priority-weighted percentage with High (80–100), Medium (50–79.99), Low (below 50), or Unknown (no findings) labels. Missing external evidence therefore lowers coverage rather than fabricating a high or low quality result.

## Remediation task contract

`master-audit-tasks.csv` retains the original action-management columns and includes severity, finding type, detected/expected values, confidence, and affected-URL counts/samples. Equivalent findings are grouped only when their rule, result shape, action, owner, acceptance criteria, and confidence match. Up to 20 unique URLs and evidence values are retained in the task row, while `affected_url_count` preserves the full group size. All text cells are protected against spreadsheet formula injection.
