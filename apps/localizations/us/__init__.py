"""United States (US) localization — stub implementation.

향후 실 구현 예정. 현재는 등록만 수행하여 다국가 분기 인터페이스를 검증한다.

자동 등록: import 시점에 register_adapter('US', USAdapter()) 호출.
"""
from apps.localizations.base import LocalizationAdapter
from apps.localizations.registry import register_adapter

from .tax import USTaxAdapter
from .tax_calendar import USTaxCalendarAdapter
from .identifier import USIdentifierAdapter
from .calendar_us import USCalendarAdapter
from .coa import USChartOfAccountsAdapter
from .e_invoice import USElectronicInvoiceAdapter
from .social import USSocialInsuranceAdapter


class USAdapter(LocalizationAdapter):
    country_code = 'US'
    country_name = 'United States'
    currency_code = 'USD'
    locale = 'en_US'

    def __init__(self):
        self.tax = USTaxAdapter()
        self.tax_calendar = USTaxCalendarAdapter()
        self.identifier = USIdentifierAdapter()
        self.calendar = USCalendarAdapter()
        self.coa = USChartOfAccountsAdapter()
        self.e_invoice = USElectronicInvoiceAdapter()
        self.social_insurance = USSocialInsuranceAdapter()


register_adapter('US', USAdapter())
