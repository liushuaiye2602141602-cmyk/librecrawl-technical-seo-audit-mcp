# Manual Review Workflow

When Master Audit V3 is enabled, every finalized audit emits
`<domain>-<timestamp>.manual-review.md`. The sections are generated from the
current `NEW_MANUAL` registry rows, so the artifact cannot silently drift from
the source-of-truth CSV.

For each rule, the reviewer moves the item from `PENDING`/`IN_REVIEW` to exactly one final status:

- `PASS`: reviewed and acceptance criteria are met;
- `WARNING`: a non-blocking issue exists; evidence is required;
- `FAIL`: acceptance criteria are not met; evidence is required;
- `NOT_APPLICABLE`: the reviewer confirmed the rule does not apply.

The HTML markers and field labels are machine-readable and must not be edited.
Every final decision also requires a reviewer and ISO-8601 review time. Completed templates can be validated as structured outcomes and converted to unified findings with:

```python
from audit_rules.manual_review import parse_manual_review, parse_manual_review_outcomes
from audit_rules.registry import load_registry

markdown = open("example.com-20260809-1200.manual-review.md", encoding="utf-8").read()
outcomes = parse_manual_review_outcomes(
    markdown, load_registry(), expected_site="https://example.com")
findings = parse_manual_review(
    markdown, load_registry(), expected_site="https://example.com")
```

The parser rejects incomplete sections, multiple selected statuses, duplicate
or unknown rule markers, cross-site files, missing reviewer/time, and
WARNING/FAIL results without evidence. PASS and NOT_APPLICABLE produce no issue
finding but remain structured coverage outcomes.

For production ingestion, mount the completed file read-only, set
`MANUAL_REVIEW_INPUT_PATH`, and rerun the same site with V3 enabled. The
`ManualReviewDataProvider` validates the host and merges PASS, WARNING, FAIL,
and NOT_APPLICABLE into coverage; WARNING/FAIL also enter findings, tasks, and
reports. Until that completed artifact is supplied, manual rules truthfully
remain `NOT_CHECKED`.
