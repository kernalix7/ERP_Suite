"""JP 계정과목 어댑터 (스텁) — JGAAP / IFRS."""
from __future__ import annotations

from apps.localizations.base import ChartOfAccountsAdapter


class JPChartOfAccountsAdapter(ChartOfAccountsAdapter):
    """일본 계정과목 어댑터 (스텁)."""

    def standard_name(self) -> str:
        return 'JGAAP'

    def income_statement_format(self) -> str:
        return 'multi-step'
