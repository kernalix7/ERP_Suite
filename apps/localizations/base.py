"""국가 어댑터 추상 베이스 — 모든 국가가 구현해야 할 인터페이스.

각 국가별로 이 클래스를 상속받아 구현:
- KRAdapter (apps/localizations/kr/) — 한국, 현재 운영 기준
- USAdapter (apps/localizations/us/) — 미래
- JPAdapter (apps/localizations/jp/) — 미래

각 도메인별 sub-adapter:
- TaxAdapter — VAT/Sales Tax/GST 등 세제
- TaxCalendarAdapter — 신고기한
- IdentifierAdapter — 사업자번호 형식·검증
- CalendarAdapter — 공휴일·영업일 계산
- ChartOfAccountsAdapter — 계정과목 표준
- ElectronicInvoiceAdapter — e-Invoice 연동 (홈택스, SDI 등)
- SocialInsuranceAdapter — 사회보험 요율
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import Optional


class TaxAdapter(ABC):
    """세제 — VAT / Sales Tax / GST 등."""

    @abstractmethod
    def vat_rate(self) -> Decimal:
        """기본 부가세율 (KR 0.10, US 주별 다름, 인도 0.18 등)."""

    @abstractmethod
    def withholding_rates(self) -> dict[str, Decimal]:
        """원천세율 — 세목별 (KR: 사업소득 0.033, 기타소득 0.088 등)."""


class TaxCalendarAdapter(ABC):
    """세무 신고 기한 캘린더."""

    @abstractmethod
    def vat_filing_due(self, year: int, quarter: int) -> date:
        """부가세 신고기한 (KR: 분기 종료 익월 25일)."""

    @abstractmethod
    def withholding_filing_due(self, year: int, month: int) -> date:
        """원천세 신고기한 (KR: 지급월 익월 10일)."""

    @abstractmethod
    def corporate_tax_filing_due(self, year: int) -> date:
        """법인세 신고기한 (KR: 사업연도 종료 후 3개월)."""


class IdentifierAdapter(ABC):
    """국가별 식별자 형식·검증 — 사업자번호, EIN, CNPJ 등."""

    @abstractmethod
    def business_number_format(self) -> str:
        """사업자번호 표준 포맷 (KR: '###-##-#####')."""

    @abstractmethod
    def validate_business_number(self, value: str) -> bool:
        """사업자번호 유효성 검증 (체크섬 등)."""


class CalendarAdapter(ABC):
    """공휴일·영업일 계산."""

    @abstractmethod
    def is_holiday(self, target: date) -> bool:
        """공휴일 여부."""

    @abstractmethod
    def is_business_day(self, target: date) -> bool:
        """영업일 여부 (주말 + 공휴일 제외)."""

    @abstractmethod
    def add_business_days(self, start: date, days: int) -> date:
        """N영업일 후 일자 반환."""


class ChartOfAccountsAdapter(ABC):
    """계정과목 표준 — K-GAAP / US-GAAP / IFRS / 인도 Schedule III 등."""

    @abstractmethod
    def standard_name(self) -> str:
        """기준 회계기준 명칭 ('K-GAAP', 'US-GAAP', 'IFRS')."""

    @abstractmethod
    def income_statement_format(self) -> str:
        """손익계산서 양식 ('9-step', 'multi-step', 'single-step')."""


class ElectronicInvoiceAdapter(ABC):
    """e-Invoice 국세청 연동 — 홈택스 / SDI / SAT 등."""

    @abstractmethod
    def is_supported(self) -> bool:
        """국가에서 e-Invoice 의무 발행 여부."""

    @abstractmethod
    def submit_tax_invoice(self, invoice) -> dict:
        """세금계산서 제출 (KR 홈택스 등)."""


class SocialInsuranceAdapter(ABC):
    """사회보험 — KR 4대보험 / US Social Security 등."""

    @abstractmethod
    def insurance_types(self) -> list[str]:
        """국가별 의무가입 사회보험 종류."""

    @abstractmethod
    def employee_rates(self) -> dict[str, Decimal]:
        """직원 부담 요율."""

    @abstractmethod
    def employer_rates(self) -> dict[str, Decimal]:
        """회사 부담 요율."""


class LocalizationAdapter(ABC):
    """국가 어댑터 — 도메인별 sub-adapter 컨테이너.

    각 국가 구현은 이 클래스를 상속받아 sub-adapter 인스턴스를 채운다.
    """

    country_code: str  # ISO-3166 alpha-2 (KR, US, JP, ...)
    country_name: str  # 한국어 명칭
    currency_code: str  # ISO-4217 (KRW, USD, JPY, ...)
    locale: str  # ko_KR, en_US 등

    tax: TaxAdapter
    calendar: CalendarAdapter
    tax_calendar: TaxCalendarAdapter
    identifier: IdentifierAdapter
    coa: ChartOfAccountsAdapter
    e_invoice: Optional[ElectronicInvoiceAdapter] = None
    social_insurance: Optional[SocialInsuranceAdapter] = None

    def __str__(self):
        return f'<LocalizationAdapter {self.country_code} ({self.country_name})>'
