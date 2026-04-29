"""US tax calendar adapter (stub)."""
from __future__ import annotations

from datetime import date

from apps.localizations.base import TaxCalendarAdapter


class USTaxCalendarAdapter(TaxCalendarAdapter):
    """US tax calendar adapter (stub)."""

    def vat_filing_due(self, year: int, quarter: int) -> date:
        raise NotImplementedError('US tax calendar not yet implemented')

    def withholding_filing_due(self, year: int, month: int) -> date:
        raise NotImplementedError('US tax calendar not yet implemented')

    def corporate_tax_filing_due(self, year: int) -> date:
        raise NotImplementedError('US tax calendar not yet implemented')
