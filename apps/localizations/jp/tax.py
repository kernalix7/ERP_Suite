"""JP 세제 어댑터 (스텁) — 일본 소비세(消費税).

근거(향후 실 구현 시 참조):
- 消費税法 — 일반세율 10%, 경감세율 8% (식품 등)
- 所得税法 — 원천징수
"""
from __future__ import annotations

from decimal import Decimal

from apps.localizations.base import TaxAdapter


class JPTaxAdapter(TaxAdapter):
    """일본 소비세 어댑터 (스텁)."""

    def vat_rate(self) -> Decimal:
        return Decimal('0.10')

    def withholding_rates(self) -> dict[str, Decimal]:
        return {}

    def local_income_tax_rate(self) -> Decimal:
        return Decimal('0')
