"""US tax adapter (stub) — Sales Tax / Federal withholding.

미국은 연방 부가세가 없고 주별 Sales Tax 가 다름. 본 스텁은 0 반환.
"""
from __future__ import annotations

from decimal import Decimal

from apps.localizations.base import TaxAdapter


class USTaxAdapter(TaxAdapter):
    """US tax adapter (stub)."""

    def vat_rate(self) -> Decimal:
        # 연방 부가세 없음 — 주별 Sales Tax 는 별도 로직 필요
        return Decimal('0')

    def withholding_rates(self) -> dict[str, Decimal]:
        return {}

    def local_income_tax_rate(self) -> Decimal:
        return Decimal('0')
