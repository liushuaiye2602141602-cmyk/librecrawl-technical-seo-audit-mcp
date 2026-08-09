"""Rule 1 must retain applicable User-agent evidence."""

import json


def _rule_one():
    from audit_rules.registry import load_registry

    return next(rule for rule in load_registry() if rule.audit_id == 1)


def test_bot_specific_root_blocks_do_not_become_global_rule1_failure():
    from audit_rules.adapters import _adapter_robots_txt
    from audit_rules.context import SiteContext
    from server import _parse_robots_txt

    parsed = _parse_robots_txt("""
User-agent: AhrefsBot
Disallow: /
User-agent: GPTBot
Disallow: /
User-agent: *
Disallow: /private/
Sitemap: https://example.com/sitemap.xml
""")
    site = SiteContext.from_site_check({"robots_txt": parsed}, "https://example.com/")

    findings = _adapter_robots_txt(_rule_one(), site, [], {})

    assert findings == []
    assert parsed["important_blocked"] == []
    assert parsed["groups"][0] == {"user_agents": ["ahrefsbot"], "disallow": ["/"]}


def test_applicable_root_block_has_traceable_rule1_evidence_contract():
    from audit_rules.adapters import _adapter_robots_txt
    from audit_rules.context import SiteContext
    from server import _parse_robots_txt

    parsed = _parse_robots_txt("""
User-agent: Googlebot
Disallow: /
Sitemap: https://example.com/sitemap.xml
""")
    site = SiteContext.from_site_check({"robots_txt": parsed}, "https://example.com/")

    findings = _adapter_robots_txt(_rule_one(), site, [], {})

    assert len(findings) == 1
    finding = findings[0]
    evidence = json.loads(finding.evidence)
    assert evidence == {
        "applicable_agents": ["googlebot"],
        "blocked_paths": ["/"],
        "robots_status": 200,
    }
    for field in (
        "audit_id", "rule_id", "scope", "finding_type", "evidence",
        "detected_value", "expected_value", "data_source", "confidence",
        "remediation", "acceptance_criteria",
    ):
        assert getattr(finding, field) not in (None, "")


def test_rule1_acceptance_contract_flags_missing_sitemap_declaration():
    from audit_rules.adapters import _adapter_robots_txt
    from audit_rules.context import SiteContext
    from server import _parse_robots_txt

    parsed = _parse_robots_txt("User-agent: *\nDisallow: /private/\n")
    site = SiteContext.from_site_check({"robots_txt": parsed}, "https://example.com/")

    findings = _adapter_robots_txt(_rule_one(), site, [], {})

    assert len(findings) == 1
    assert findings[0].detected_value == "No Sitemap declaration in robots.txt"
    assert findings[0].expected_value == "At least one valid Sitemap: URL"
