"""Completed manual-review artifact provider."""

import os
from pathlib import Path

from audit_rules.context import PageContext, SiteContext
from audit_rules.manual_review import parse_manual_review_outcomes
from audit_rules.providers.base import DataProvider
from audit_rules.registry import load_registry


class ManualReviewDataProvider(DataProvider):
    def __init__(self, path: str = "") -> None:
        self._path = Path(path or os.getenv("MANUAL_REVIEW_INPUT_PATH", ""))
        self.runtime_available = False

    @property
    def name(self) -> str:
        return "Manual Review"

    def is_available(self) -> bool:
        return bool(os.getenv("MASTER_AUDIT_V3_ENABLED", "false").lower() == "true"
                    and os.getenv("MASTER_AUDIT_MANUAL_REVIEW_ENABLED", "true").lower() == "true"
                    and self._path.is_file())

    def missing_rule_ids(self) -> list[int]:
        return [53, 54, 55, 56, 57, 71, 72, 73]

    def enrich_site(self, ctx: SiteContext) -> None:
        pass

    def enrich_page(self, ctx: PageContext) -> None:
        pass

    def collect(self, site_ctx: SiteContext, page_contexts: list[PageContext],
                shared_data: dict) -> bool:
        try:
            outcomes = parse_manual_review_outcomes(
                self._path.read_text(encoding="utf-8"), load_registry(),
                expected_site=site_ctx.base_url)
        except (OSError, ValueError):
            shared_data["manual_review_errors"] = ["input:ValidationError"]
            self.runtime_available = False
            return False
        shared_data["manual_review_outcomes"] = outcomes
        self.runtime_available = True
        return True
