"""audit_rules — Unified Audit Rule Registry for Enterprise SEO Audit v3.

Sub-packages:
    categories   — Enums (Priority, Severity, Scope, ExecutionStatus, ResultStatus, etc.)
    models       — Dataclasses (RuleDefinition, Finding, CoverageRow)
    registry     — CSV loader, merger, validator → list[RuleDefinition]
    context      — PageContext, SiteContext (lightweight + lazy-heavy fields)
    runner       — RuleRunner: single-pass evaluation engine
    coverage     — CoverageManager: 80-row coverage matrix
    providers/   — Pluggable data provider adapters
"""
