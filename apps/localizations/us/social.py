"""US social insurance adapter (stub) — Social Security / Medicare / FUTA."""
from __future__ import annotations

from decimal import Decimal

from apps.localizations.base import SocialInsuranceAdapter


class USSocialInsuranceAdapter(SocialInsuranceAdapter):
    """US social insurance adapter (stub)."""

    def insurance_types(self) -> list[str]:
        return ['Social Security', 'Medicare', 'FUTA', 'SUTA']

    def employee_rates(self) -> dict[str, Decimal]:
        return {}

    def employer_rates(self) -> dict[str, Decimal]:
        return {}
