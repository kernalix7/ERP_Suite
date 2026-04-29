"""LocalizationAdapter 통합 검증.

검증 항목:
- get_active_adapter() 가 settings.ACTIVE_COUNTRY 기반으로 KR을 반환
- SystemConfig('GENERAL', 'active_country') 가 settings를 우선
- KR 어댑터의 모든 sub-adapter 가 NotImplementedError 없이 동작
- 사업자번호 체크섬 검증 (유효/무효/공란/포맷 변형)
- KR 영업일·공휴일 계산 (Holiday 시드 의존)
- VAT 세율 / 신고기한 / 외환손익 PostingProfile / 4대보험 요율 응답 형식

본 테스트는 KR 어댑터의 contract 검증만 수행. 비즈니스 로직 정밀 테스트는
각 sub-adapter 별 단위 테스트(있는 경우)에서 다룬다.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase, override_settings


class LocalizationRegistryTests(TestCase):
    """레지스트리 / 활성 어댑터 선택 우선순위."""

    def test_default_active_is_kr(self):
        from apps.localizations import get_active_adapter
        adapter = get_active_adapter()
        self.assertEqual(adapter.country_code, 'KR')
        self.assertEqual(adapter.country_name, '대한민국')
        self.assertEqual(adapter.currency_code, 'KRW')
        self.assertEqual(adapter.locale, 'ko_KR')

    def test_get_adapter_explicit_kr(self):
        from apps.localizations import get_adapter
        adapter = get_adapter('KR')
        self.assertEqual(adapter.country_code, 'KR')

    def test_get_adapter_unknown_raises(self):
        from apps.localizations import get_adapter
        with self.assertRaises(LookupError):
            get_adapter('ZZ')

    def test_registered_codes_includes_kr(self):
        from apps.localizations import get_registered_codes
        codes = get_registered_codes()
        self.assertIn('KR', codes)

    @override_settings(ACTIVE_COUNTRY='KR')
    def test_settings_active_country_priority(self):
        from apps.localizations import get_active_adapter
        adapter = get_active_adapter()
        self.assertEqual(adapter.country_code, 'KR')

    def test_systemconfig_overrides_settings(self):
        """SystemConfig('GENERAL', 'active_country') 가 우선."""
        from apps.core.models import SystemConfig
        from apps.localizations import get_active_adapter

        SystemConfig.set_value('GENERAL', 'active_country', 'KR')
        try:
            adapter = get_active_adapter()
            self.assertEqual(adapter.country_code, 'KR')
        finally:
            # 정리 — 다른 테스트에 영향 안 주도록 비움
            try:
                SystemConfig.set_value('GENERAL', 'active_country', '')
            except Exception:
                pass


class KRTaxAdapterTests(TestCase):
    def test_vat_rate_is_10_percent(self):
        from apps.localizations import get_adapter
        adapter = get_adapter('KR')
        self.assertEqual(adapter.tax.vat_rate(), Decimal('0.10'))

    def test_withholding_rates_returns_dict(self):
        from apps.localizations import get_adapter
        adapter = get_adapter('KR')
        rates = adapter.tax.withholding_rates()
        self.assertIsInstance(rates, dict)
        # 핵심 세목 존재 검증
        self.assertIn('BUSINESS_INCOME', rates)
        self.assertIn('OTHER_INCOME', rates)
        # 사업소득 합산세율 3.3%
        self.assertEqual(rates['BUSINESS_INCOME'], Decimal('0.033'))

    def test_get_vat_rate_helper_returns_decimal(self):
        from apps.localizations import get_vat_rate, get_vat_multiplier
        self.assertEqual(get_vat_rate(), Decimal('0.10'))
        self.assertEqual(get_vat_multiplier(), Decimal('1.10'))


class KRTaxCalendarAdapterTests(TestCase):
    def test_vat_filing_due_q1_2026(self):
        from apps.localizations import get_adapter
        adapter = get_adapter('KR')
        # Q1 2026 → 4/25 (토요일이면 다음 영업일)
        due = adapter.tax_calendar.vat_filing_due(2026, 1)
        self.assertEqual(due.month, 4)
        self.assertGreaterEqual(due.day, 25)

    def test_vat_filing_due_invalid_quarter(self):
        from apps.localizations import get_adapter
        adapter = get_adapter('KR')
        with self.assertRaises(ValueError):
            adapter.tax_calendar.vat_filing_due(2026, 5)

    def test_withholding_filing_due_dec_rolls_to_next_year(self):
        from apps.localizations import get_adapter
        adapter = get_adapter('KR')
        due = adapter.tax_calendar.withholding_filing_due(2026, 12)
        self.assertEqual(due.year, 2027)
        self.assertEqual(due.month, 1)

    def test_corporate_tax_filing_due(self):
        from apps.localizations import get_adapter
        adapter = get_adapter('KR')
        # 12월 결산 가정 → 익년 3월 말일
        due = adapter.tax_calendar.corporate_tax_filing_due(2026)
        self.assertEqual(due.year, 2027)
        self.assertEqual(due.month, 3)


class KRIdentifierAdapterTests(TestCase):
    """사업자등록번호 체크섬 검증.

    국세청 표준 알고리즘으로 유효한 번호 1개 + 무효 케이스 다수 검증.
    """

    VALID_BUSINESS_NUMBER = '124-81-00998'  # 삼성전자 (체크섬 검증된 공개 사업자번호)

    def test_validate_valid_number(self):
        from apps.localizations import get_adapter
        adapter = get_adapter('KR')
        self.assertTrue(adapter.identifier.validate_business_number(self.VALID_BUSINESS_NUMBER))

    def test_validate_without_hyphens(self):
        from apps.localizations import get_adapter
        adapter = get_adapter('KR')
        # 하이픈 제거된 형식도 동일 결과
        digits = self.VALID_BUSINESS_NUMBER.replace('-', '')
        self.assertTrue(adapter.identifier.validate_business_number(digits))

    def test_validate_blank_returns_false(self):
        from apps.localizations import get_adapter
        adapter = get_adapter('KR')
        self.assertFalse(adapter.identifier.validate_business_number(''))
        self.assertFalse(adapter.identifier.validate_business_number(None))

    def test_validate_wrong_length(self):
        from apps.localizations import get_adapter
        adapter = get_adapter('KR')
        self.assertFalse(adapter.identifier.validate_business_number('123-45-6789'))   # 9자리
        self.assertFalse(adapter.identifier.validate_business_number('1234567890123'))  # 13자리

    def test_validate_wrong_checksum(self):
        from apps.localizations import get_adapter
        adapter = get_adapter('KR')
        self.assertFalse(adapter.identifier.validate_business_number('123-45-67890'))

    def test_format_is_korean_standard(self):
        from apps.localizations import get_adapter
        adapter = get_adapter('KR')
        self.assertEqual(adapter.identifier.business_number_format(), '###-##-#####')


class KRCalendarAdapterTests(TestCase):
    def test_is_business_day_does_not_raise(self):
        from apps.localizations import get_adapter
        adapter = get_adapter('KR')
        # 결과 자체는 Holiday 시드에 의존 — bool 응답만 검증
        result = adapter.calendar.is_business_day(date(2026, 1, 5))
        self.assertIsInstance(result, bool)

    def test_weekend_is_not_business_day(self):
        from apps.localizations import get_adapter
        adapter = get_adapter('KR')
        # 2026-01-04 일요일
        sunday = date(2026, 1, 4)
        self.assertFalse(adapter.calendar.is_business_day(sunday))

    def test_add_business_days_returns_date(self):
        from apps.localizations import get_adapter
        adapter = get_adapter('KR')
        result = adapter.calendar.add_business_days(date(2026, 1, 5), 3)
        self.assertIsInstance(result, date)


class KRChartOfAccountsAdapterTests(TestCase):
    def test_standard_is_kgaap(self):
        from apps.localizations import get_adapter
        adapter = get_adapter('KR')
        self.assertEqual(adapter.coa.standard_name(), 'K-GAAP')

    def test_format_is_9_step(self):
        from apps.localizations import get_adapter
        adapter = get_adapter('KR')
        self.assertEqual(adapter.coa.income_statement_format(), '9-step')

    def test_income_statement_steps_has_9_items(self):
        from apps.localizations import get_adapter
        adapter = get_adapter('KR')
        steps = adapter.coa.income_statement_steps()
        self.assertEqual(len(steps), 9)
        self.assertEqual(steps[0]['step'], 1)
        self.assertEqual(steps[-1]['step'], 9)


class KRElectronicInvoiceAdapterTests(TestCase):
    def test_is_supported(self):
        from apps.localizations import get_adapter
        adapter = get_adapter('KR')
        self.assertIsNotNone(adapter.e_invoice)
        self.assertTrue(adapter.e_invoice.is_supported())


class KRSocialInsuranceAdapterTests(TestCase):
    def test_insurance_types_includes_4(self):
        from apps.localizations import get_adapter
        adapter = get_adapter('KR')
        types = adapter.social_insurance.insurance_types()
        self.assertIn('국민연금', types)
        self.assertIn('건강보험', types)
        self.assertIn('고용보험', types)
        self.assertIn('산재보험', types)

    def test_employee_rates_pension_4_5(self):
        from apps.localizations import get_adapter
        adapter = get_adapter('KR')
        rates = adapter.social_insurance.employee_rates()
        self.assertEqual(rates['국민연금'], Decimal('4.5'))

    def test_calculate_employee_deductions(self):
        from apps.localizations import get_adapter
        adapter = get_adapter('KR')
        d = adapter.social_insurance.calculate_employee_deductions(Decimal('3000000'))
        # 국민연금 = 3,000,000 × 4.5% = 135,000
        self.assertEqual(d['국민연금'], 135000)


class CountrySeedTests(TestCase):
    def test_kr_country_seeded(self):
        from apps.localizations.models import Country
        kr = Country.objects.get(code='KR')
        self.assertEqual(kr.name, '대한민국')
        self.assertEqual(kr.currency_code, 'KRW')
        self.assertTrue(kr.is_default)
        self.assertTrue(kr.is_supported)

    def test_only_kr_default(self):
        """default 국가는 단일 행만 — prod 데이터 무결성."""
        from apps.localizations.models import Country
        defaults = Country.objects.filter(is_default=True, is_active=True).count()
        self.assertLessEqual(defaults, 1)


class CountryListViewTests(TestCase):
    def test_anonymous_redirected(self):
        resp = self.client.get('/localizations/countries/')
        self.assertIn(resp.status_code, (302, 401, 403))

    def test_admin_can_access(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admin = User.objects.create_user(
            username='loc_admin_test',
            password='x',
            email='loc_admin@test.local',
            role='admin',
        )
        self.client.force_login(admin)
        resp = self.client.get('/localizations/countries/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'KR')
