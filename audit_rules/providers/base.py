"""DataProvider ABC — pluggable external data source adapter."""

from abc import ABC, abstractmethod
from typing import Optional

from audit_rules.context import PageContext, SiteContext


class DataProvider(ABC):
    """Abstract base for data providers.

    Each provider enriches PageContext/SiteContext with data from one
    external source (LibreCrawl, PageSpeed, GSC, Semrush, etc.).

    Providers self-test availability. When unavailable, rules that depend
    on them produce NOT_CHECKED, never fabricated PASS/FAIL.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name (e.g. 'PageSpeed API')."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Can this provider enrich contexts right now?

        Returns False if credentials are missing, API is unreachable, etc.
        Phase 1: LibreCrawlProvider always returns True because crawl data
        is the foundational data source.
        """
        ...

    @abstractmethod
    def enrich_site(self, ctx: SiteContext) -> None:
        """Enrich a SiteContext with provider-specific data."""
        ...

    @abstractmethod
    def enrich_page(self, ctx: PageContext) -> None:
        """Enrich a PageContext with provider-specific data.

        Phase 1: Uses existing crawl export data ONLY. No HTTP refetch.
        Heavy fields are lazy-loaded on first access.
        """
        ...

    def missing_rule_ids(self) -> list[int]:
        """Which rule IDs require this provider?

        Override in subclasses to declare rule dependencies.
        """
        return []
