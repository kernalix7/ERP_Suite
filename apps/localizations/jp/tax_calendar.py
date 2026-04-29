"""JP 세무 신고기한 어댑터 (스텁)."""
from __future__ import annotations

from datetime import date

from apps.localizations.base import TaxCalendarAdapter


class JPTaxCalendarAdapter(TaxCalendarAdapter):
    """일본 세무 신고기한 어댑터 (스텁)."""

    def vat_filing_due(self, year: int, quarter: int) -> date:
        raise NotImplementedError('JP tax calendar not yet implemented')

    def withholding_filing_due(self, year: int, month: int) -> date:
        raise NotImplementedError('JP tax calendar not yet implemented')

    def corporate_tax_filing_due(self, year: int) -> date:
        raise NotImplementedError('JP tax calendar not yet implemented')
