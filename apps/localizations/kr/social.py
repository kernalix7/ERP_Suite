"""대한민국 4대보험 어댑터 — 2026년 기준 요율."""
from __future__ import annotations

from decimal import Decimal

from apps.localizations.base import SocialInsuranceAdapter

# 2026년 기준 요율 (%)
_HEALTH = Decimal('3.545')
_LONG_TERM_CARE_OF_HEALTH = Decimal('12.95')  # 건강보험료의 %
_PENSION = Decimal('4.5')
_EMPLOYMENT_EE = Decimal('0.9')     # 직원 실업급여
_EMPLOYMENT_ER = Decimal('1.05')    # 사업주 실업급여+고용안정·직업능력개발
_INDUSTRIAL_ER = Decimal('0.7')     # 산재: 직원 0%, 사업주 0.7% (제조업 평균)


class KRSocialInsuranceAdapter(SocialInsuranceAdapter):
    """대한민국 4대보험 (2026년 기준).

    장기요양보험은 건강보험료 × 12.95%로 파생되어 별도 항목으로 노출한다.
    산재보험 사업주 요율은 업종별로 다르며, 여기서는 제조업 평균값을 기본으로 한다.
    """

    def insurance_types(self) -> list[str]:
        return ['국민연금', '건강보험', '장기요양보험', '고용보험', '산재보험']

    def employee_rates(self) -> dict[str, Decimal]:
        return {
            '국민연금': _PENSION,
            '건강보험': _HEALTH,
            '장기요양보험': Decimal('0'),   # 건강보험료의 12.95% — calculate_long_term_care() 사용
            '고용보험': _EMPLOYMENT_EE,
            '산재보험': Decimal('0'),
        }

    def employer_rates(self) -> dict[str, Decimal]:
        return {
            '국민연금': _PENSION,
            '건강보험': _HEALTH,
            '장기요양보험': Decimal('0'),   # 건강보험료의 12.95% — calculate_long_term_care() 사용
            '고용보험': _EMPLOYMENT_ER,
            '산재보험': _INDUSTRIAL_ER,
        }

    def long_term_care_rate_of_health(self) -> Decimal:
        """장기요양보험료율 = 건강보험료 × 이 비율."""
        return _LONG_TERM_CARE_OF_HEALTH

    def calculate_employee_deductions(self, gross_pay: Decimal) -> dict[str, int]:
        """직원 공제액 계산 (원 단위 절사).

        Returns:
            {'국민연금': int, '건강보험': int, '장기요양보험': int, '고용보험': int, '산재보험': int}
        """
        health = int(gross_pay * _HEALTH / 100)
        return {
            '국민연금': int(gross_pay * _PENSION / 100),
            '건강보험': health,
            '장기요양보험': int(health * _LONG_TERM_CARE_OF_HEALTH / 100),
            '고용보험': int(gross_pay * _EMPLOYMENT_EE / 100),
            '산재보험': 0,
        }

    def calculate_employer_contributions(self, gross_pay: Decimal) -> dict[str, int]:
        """회사 부담액 계산 (원 단위 절사).

        Returns:
            {'국민연금': int, '건강보험': int, '장기요양보험': int, '고용보험': int, '산재보험': int}
        """
        health = int(gross_pay * _HEALTH / 100)
        return {
            '국민연금': int(gross_pay * _PENSION / 100),
            '건강보험': health,
            '장기요양보험': int(health * _LONG_TERM_CARE_OF_HEALTH / 100),
            '고용보험': int(gross_pay * _EMPLOYMENT_ER / 100),
            '산재보험': int(gross_pay * _INDUSTRIAL_ER / 100),
        }
