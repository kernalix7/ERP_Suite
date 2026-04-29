"""JP 사회보험 어댑터 (스텁) — 健康保険 / 厚生年金 / 雇用保険 / 労災保険."""
from __future__ import annotations

from decimal import Decimal

from apps.localizations.base import SocialInsuranceAdapter


class JPSocialInsuranceAdapter(SocialInsuranceAdapter):
    """일본 사회보험 어댑터 (스텁)."""

    def insurance_types(self) -> list[str]:
        return ['健康保険', '厚生年金', '雇用保険', '労災保険']

    def employee_rates(self) -> dict[str, Decimal]:
        return {}

    def employer_rates(self) -> dict[str, Decimal]:
        return {}
