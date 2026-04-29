"""US chart of accounts adapter (stub) — US-GAAP."""
from __future__ import annotations

from apps.localizations.base import ChartOfAccountsAdapter


class USChartOfAccountsAdapter(ChartOfAccountsAdapter):
    """US-GAAP chart of accounts adapter (stub)."""

    def standard_name(self) -> str:
        return 'US-GAAP'

    def income_statement_format(self) -> str:
        return 'multi-step'
