"""Registry-driven manual review artifact and parser contracts."""

import pytest

from audit_rules.registry import load_registry


def _complete(template: str, statuses: dict[int, str]) -> str:
    chunks = template.split("<!-- manual-review-rule:")
    output = [chunks[0]]
    for chunk in chunks[1:]:
        audit_id = int(chunk.split(" -->", 1)[0])
        status = statuses.get(audit_id, "PASS")
        line = "Status: [ ] PASS | [ ] WARNING | [ ] FAIL | [ ] NOT_APPLICABLE"
        selected = line.replace(f"[ ] {status}", f"[x] {status}")
        chunk = chunk.replace(line, selected, 1)
        chunk = chunk.replace(
            "Evidence: <!-- enter evidence -->",
            f"Evidence: reviewed evidence for rule {audit_id}", 1)
        output.append("<!-- manual-review-rule:" + chunk)
    return "".join(output)


def test_template_is_generated_from_current_manual_registry_rules():
    from audit_rules.manual_review import generate_manual_review_template

    registry = load_registry()
    manual_ids = [r.audit_id for r in registry if r.impl_status.value == "NEW_MANUAL"]
    output = generate_manual_review_template(registry, "https://example.com/shop")

    assert output.startswith("<!-- manual-review-v1 -->")
    assert "Site: example.com" in output
    assert output.count("<!-- manual-review-rule:") == len(manual_ids) == 8
    assert [int(part.split(" -->", 1)[0]) for part in
            output.split("<!-- manual-review-rule:")[1:]] == manual_ids
    assert "Rule 36" not in output


def test_completed_template_parses_warning_and_failure_to_findings():
    from audit_rules.manual_review import (
        generate_manual_review_template, parse_manual_review,
    )

    registry = load_registry()
    completed = _complete(generate_manual_review_template(registry, "example.com"), {
        53: "FAIL", 54: "WARNING", 71: "NOT_APPLICABLE",
    })
    findings = parse_manual_review(completed, registry)

    assert [(f.audit_id, f.severity) for f in findings] == [
        (53, "Error"), (54, "Warning")]
    assert all(f.data_source == "Manual Review" for f in findings)
    assert all(f.confidence == 1.0 for f in findings)
    assert "reviewed evidence" in findings[0].evidence


@pytest.mark.parametrize("mutator,match", [
    (lambda text: text, "incomplete"),
    (lambda text: _complete(text, {}).replace(
        "[x] PASS | [ ] WARNING", "[x] PASS | [x] WARNING", 1), "exactly one"),
    (lambda text: _complete(text, {}).replace(
        "<!-- manual-review-rule:53 -->", "<!-- manual-review-rule:999 -->", 1),
     "unknown or non-manual"),
])
def test_parser_fails_closed_for_incomplete_ambiguous_or_tampered_input(mutator, match):
    from audit_rules.manual_review import (
        ManualReviewValidationError, generate_manual_review_template,
        parse_manual_review,
    )

    template = generate_manual_review_template(load_registry(), "example.com")
    with pytest.raises(ManualReviewValidationError, match=match):
        parse_manual_review(mutator(template), load_registry())


def test_fail_or_warning_requires_evidence():
    from audit_rules.manual_review import (
        ManualReviewValidationError, generate_manual_review_template,
        parse_manual_review,
    )

    registry = load_registry()
    completed = _complete(generate_manual_review_template(registry, "example.com"), {53: "FAIL"})
    completed = completed.replace(
        "Evidence: reviewed evidence for rule 53",
        "Evidence: <!-- enter evidence -->", 1)
    with pytest.raises(ManualReviewValidationError, match="evidence"):
        parse_manual_review(completed, registry)


def test_runner_helper_writes_and_registers_manual_review_artifact(tmp_path, monkeypatch):
    import runner

    registered = []
    monkeypatch.setattr(
        runner.state, "add_artifact",
        lambda sid, kind, path: registered.append((sid, kind, path)))
    path = runner._write_manual_review_artifact(
        "session-1", "https://example.com", "example.com", "20260809-1200", tmp_path)

    assert path.name == "example.com-20260809-1200.manual-review.md"
    assert path.read_text(encoding="utf-8").startswith("<!-- manual-review-v1 -->")
    assert [(sid, kind) for sid, kind, _ in registered] == [
        ("session-1", "manual_review_md")]
