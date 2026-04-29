"""대한민국 (KR) 로컬라이제이션 — prod 기준 구현.

K-GAAP · 국세청 · 홈택스/바로빌 · 4대보험 · 한국 공휴일.

자동 등록: import 시점에 register_adapter('KR', KRAdapter()) 호출.
"""
from apps.localizations.base import LocalizationAdapter
from apps.localizations.registry import register_adapter

from .tax import KRTaxAdapter
from .tax_calendar import KRTaxCalendarAdapter
from .identifier import KRIdentifierAdapter
from .calendar_kr import KRCalendarAdapter
from .coa import KRChartOfAccountsAdapter
from .e_invoice import KRElectronicInvoiceAdapter
from .social import KRSocialInsuranceAdapter


class KRAdapter(LocalizationAdapter):
    country_code = 'KR'
    country_name = '대한민국'
    currency_code = 'KRW'
    locale = 'ko_KR'

    def __init__(self):
        self.tax = KRTaxAdapter()
        self.tax_calendar = KRTaxCalendarAdapter()
        self.identifier = KRIdentifierAdapter()
        self.calendar = KRCalendarAdapter()
        self.coa = KRChartOfAccountsAdapter()
        self.e_invoice = KRElectronicInvoiceAdapter()
        self.social_insurance = KRSocialInsuranceAdapter()


register_adapter('KR', KRAdapter())
