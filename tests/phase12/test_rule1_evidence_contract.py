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


def test_cloudflare_managed_allow_root_is_not_a_global_rule1_block():
    """Cloudflare-managed 'User-agent: *' + 'Allow: /' must not be merged
    into the AI-bot root blocks, and must not produce a Rule 1 finding."""
    from audit_rules.adapters import _adapter_robots_txt
    from audit_rules.context import SiteContext
    from server import _parse_robots_txt

    parsed = _parse_robots_txt(
        "User-agent: *\n"
        "Content-Signal: search=yes,ai-train=no,use=reference\n"
        "Allow: /\n\n"
        "User-agent: Amazonbot\nDisallow: /\n\n"
        "User-agent: Applebot-Extended\nDisallow: /\n\n"
        "User-agent: *\n"
        "Disallow: /inquire\nDisallow: /admin\n"
        "Sitemap: https://example.com/sitemap.xml\n"
    )
    # Wildcard allow group stays separate from the AI-bot group.
    assert parsed["groups"][0]["user_agents"] == ["*"]
    assert parsed["groups"][0]["disallow"] == []
    assert parsed["groups"][0].get("allow") == ["/"]
    assert parsed["groups"][1]["user_agents"] == ["amazonbot"]
    assert parsed["groups"][1]["disallow"] == ["/"]
    assert parsed["groups"][1].get("allow", []) == []
    assert parsed["important_blocked"] == []
    assert parsed["important_blocked_evidence"] == []

    site = SiteContext.from_site_check({"robots_txt": parsed}, "https://example.com/")
    findings = _adapter_robots_txt(_rule_one(), site, [], {})
    assert findings == []


def test_adapter_recomputes_effective_blocks_from_merged_group_shape():
    """Even when the stored robots dict already carries a stale merged
    'User-agent: *' root block (as preserved in a production replay), the
    adapter must apply last-matching-group semantics and not flag it."""
    from audit_rules.adapters import _adapter_robots_txt
    from audit_rules.context import SiteContext

    robots_data = {
        "found": True,
        "status": 200,
        "disallow_count": 29,
        "groups": [
            {"user_agents": ["*", "amazonbot"], "disallow": ["/"]},
            {"user_agents": ["applebot-extended"], "disallow": ["/"]},
            {"user_agents": ["bytespider"], "disallow": ["/"]},
            {"user_agents": ["*"], "disallow": ["/inquire", "/admin", "/login"]},
        ],
        "important_blocked": ["/"],
        "important_blocked_evidence": [
            {"applicable_agents": ["*"], "blocked_paths": ["/"]},
        ],
        "sitemap_declared": ["https://example.com/sitemap.xml"],
    }
    site = SiteContext.from_site_check({"robots_txt": robots_data}, "https://example.com/")
    findings = _adapter_robots_txt(_rule_one(), site, [], {})
    assert findings == []


def test_last_matching_wildcard_group_shadows_earlier_root_block():
    from server import _parse_robots_txt

    parsed = _parse_robots_txt(
        "User-agent: *\nDisallow: /\n\n"
        "User-agent: *\nDisallow: /private/\n"
    )
    assert parsed["important_blocked"] == []
    assert parsed["important_blocked_evidence"] == []


def test_specific_googlebot_root_block_remains_traceable():
    from server import _parse_robots_txt

    parsed = _parse_robots_txt(
        "User-agent: *\nAllow: /\n\n"
        "User-agent: Googlebot\nDisallow: /\n"
    )
    assert parsed["important_blocked"] == ["/"]
    assert parsed["important_blocked_evidence"] == [
        {"applicable_agents": ["googlebot"], "blocked_paths": ["/"]},
    ]
