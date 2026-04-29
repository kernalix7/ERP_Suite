"""日本 (JP) 로컬라이제이션 — 스텁 구현.

추후 실 구현 예정. 현재는 등록만 수행하여 다국가 분기 인터페이스를 검증한다.

자동 등록: import 시점에 register_adapter('JP', JPAdapter()) 호출.
"""
from apps.localizations.base import LocalizationAdapter
from apps.localizations.registry import register_adapter

from .tax import JPTaxAdapter
from .tax_calendar import JPTaxCalendarAdapter
from .identifier import JPIdentifierAdapter
from .calendar_jp import JPCalendarAdapter
from .coa import JPChartOfAccountsAdapter
from .e_invoice import JPElectronicInvoiceAdapter
from .social import JPSocialInsuranceAdapter


class JPAdapter(LocalizationAdapter):
    country_code = 'JP'
    country_name = '日本'
    currency_code = 'JPY'
    locale = 'ja_JP'

    def __init__(self):
        self.tax = JPTaxAdapter()
        self.tax_calendar = JPTaxCalendarAdapter()
        self.identifier = JPIdentifierAdapter()
        self.calendar = JPCalendarAdapter()
        self.coa = JPChartOfAccountsAdapter()
        self.e_invoice = JPElectronicInvoiceAdapter()
        self.social_insurance = JPSocialInsuranceAdapter()


register_adapter('JP', JPAdapter())
