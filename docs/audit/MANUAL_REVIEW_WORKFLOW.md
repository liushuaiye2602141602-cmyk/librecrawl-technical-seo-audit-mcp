# Manual Review Workflow

When Master Audit V3 is enabled, every finalized audit emits
`<domain>-<timestamp>.manual-review.md`. The sections are generated from the
current `NEW_MANUAL` registry rows, so the artifact cannot silently drift from
the source-of-truth CSV.

For each rule, the reviewer selects exactly one status:

- `PASS`: reviewed and acceptance criteria are met;
- `WARNING`: a non-blocking issue exists; evidence is required;
- `FAIL`: acceptance criteria are not met; evidence is required;
- `NOT_APPLICABLE`: the reviewer confirmed the rule does not apply.

The HTML markers and field labels are machine-readable and must not be edited.
Completed templates can be converted to unified findings with:

```python
from audit_rules.manual_review import parse_manual_review
from audit_rules.registry import load_registry

markdown = open("example.com-20260809-1200.manual-review.md", encoding="utf-8").read()
findings = parse_manual_review(markdown, load_registry())
```

The parser rejects incomplete sections, multiple selected statuses, duplicate
or unknown rule markers, and WARNING/FAIL results without evidence. PASS and
NOT_APPLICABLE produce no issue finding. Manual rules remain `NOT_CHECKED` in
the original audit until a reviewer completes the separate artifact; the blank
template itself is never treated as evidence.
