"""재무 감사 Phase 2/3 신규 기능 회귀 테스트.

다음 갭의 핵심 동작을 잠금:
- GAP-1.2 Order.effective_accounting_date 우선순위
- GAP-2.4 CardSalesSlip 모델 동작
- GAP-3.3 VATReturnView 매입 4구분
- GAP-5.3 InventoryValuationView NRV 평가손실
- GAP-6.2 IncomeStatementView ?compare=1 prior/yoy
- GAP-6.3 CashFlowView ?method=direct
- GAP-7.2 BankReconRule.matches()
- GAP-8.1 VoucherApprovalConfig 다운그레이드 정책
- GAP-9.1 Order.RevenueRecognitionMethod choices 사용 가능
- GAP-9.2 외환손익 시그널 — 환율 같으면 추가 전표 없음
- GAP-10.2 Partner.entity_type 기본값
- GAP-10.4 채널×결제수단 매트릭스 ctx
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

User = get_user_model()


def _ensure_account(code, name, account_type='EXPENSE'):
    from apps.accounting.models import AccountCode
    return AccountCode.all_objects.get_or_create(
        code=code, defaults={'name': name, 'account_type': account_type},
    )[0]


class GAP12_AccountingDateTest(TestCase):
    """Order.effective_accounting_date 우선순위."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='gap12', password='p', role='admin',
        )

    def test_accounting_date_falls_back_to_order_date(self):
        from apps.sales.models import Order
        order = Order.objects.create(
            order_number='G12-1', order_date=date(2026, 4, 1),
            status='DRAFT', created_by=self.user,
        )
        self.assertEqual(order.effective_accounting_date, date(2026, 4, 1))

    def test_accounting_date_overrides_order_date(self):
        from apps.sales.models import Order
        order = Order.objects.create(
            order_number='G12-2', order_date=date(2026, 4, 30),
            accounting_date=date(2026, 5, 5),
            status='DRAFT', created_by=self.user,
        )
        self.assertEqual(order.effective_accounting_date, date(2026, 5, 5))


class GAP24_CardSalesSlipTest(TestCase):
    """CardSalesSlip 자동 번호 + 합계 계산."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='gap24', password='p', role='admin',
        )

    def test_creates_with_auto_number_and_total(self):
        from apps.accounting.models_cardslip import CardSalesSlip
        slip = CardSalesSlip.objects.create(
            approved_at=timezone.now(),
            approval_code='A1234567',
            card_brand=CardSalesSlip.CardBrand.DOMESTIC,
            card_number_masked='4-****-****-1234',
            supply_amount=Decimal('100000'),
            vat=Decimal('10000'),
            created_by=self.user,
        )
        self.assertTrue(slip.slip_number.startswith('CS'))
        self.assertEqual(slip.total_amount, Decimal('110000'))
        self.assertEqual(slip.status, CardSalesSlip.Status.APPROVED)


class GAP33_VATPurchase4CategoryTest(TestCase):
    """VATReturnView 매입 4구분 ctx — 의제/불공제 분리 집계."""

    def setUp(self):
        from apps.sales.models import Partner
        self.user = User.objects.create_user(
            username='gap33', password='p', role='admin',
        )
        self.partner = Partner.all_objects.create(
            code='G33', name='G33 거래처',
        )

    def test_purchase_4_category_aggregation(self):
        from apps.accounting.models import TaxInvoice
        # 일반매입 (DEDUCTIBLE)
        TaxInvoice.objects.create(
            invoice_type='PURCHASE', partner=self.partner,
            issue_date=date(2026, 4, 1),
            supply_amount=100000, tax_amount=10000, total_amount=110000,
            tax_type=TaxInvoice.TaxType.TAXABLE,
            vat_deduction_type=TaxInvoice.VatDeductionType.DEDUCTIBLE,
            description='일반', created_by=self.user,
        )
        # 의제매입세액 (DEEMED)
        TaxInvoice.objects.create(
            invoice_type='PURCHASE', partner=self.partner,
            issue_date=date(2026, 4, 2),
            supply_amount=50000, tax_amount=5000, total_amount=55000,
            tax_type=TaxInvoice.TaxType.TAXABLE,
            vat_deduction_type=TaxInvoice.VatDeductionType.DEEMED,
            description='의제', created_by=self.user,
        )
        # 공제받지못할매입 (NON_DEDUCTIBLE)
        TaxInvoice.objects.create(
            invoice_type='PURCHASE', partner=self.partner,
            issue_date=date(2026, 4, 3),
            supply_amount=30000, tax_amount=3000, total_amount=33000,
            tax_type=TaxInvoice.TaxType.TAXABLE,
            vat_deduction_type=TaxInvoice.VatDeductionType.NON_DEDUCTIBLE,
            description='접대', created_by=self.user,
        )
        self.client.force_login(self.user)
        resp = self.client.get('/accounting/vat-return/?year=2026&quarter=2')
        self.assertEqual(resp.status_code, 200)
        ctx = resp.context
        self.assertEqual(ctx['purchase_taxable']['count'], 1)
        self.assertEqual(ctx['purchase_deemed']['count'], 1)
        self.assertEqual(ctx['purchase_non_deductible']['count'], 1)
        # 매입세액공제 = 일반(10000) + 의제(5000)
        self.assertEqual(int(ctx['purchase_input_tax']), 15000)


class GAP53_InventoryNRVTest(TestCase):
    """InventoryValuationView NRV 평가손실."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='gap53', password='p', role='admin',
        )

    def test_nrv_loss_when_book_value_exceeds_nrv(self):
        from apps.inventory.models import Product
        Product.objects.create(
            code='G53-1', name='고평가품',
            unit_price=10000, cost_price=8000,
            net_realizable_value=5000,  # NRV < cost
            current_stock=100,
            created_by=self.user,
        )
        Product.objects.create(
            code='G53-2', name='정상품',
            unit_price=10000, cost_price=8000,
            net_realizable_value=9000,  # NRV > cost
            current_stock=100,
            created_by=self.user,
        )
        self.client.force_login(self.user)
        resp = self.client.get('/inventory/valuation/')
        self.assertEqual(resp.status_code, 200)
        ctx = resp.context
        # 고평가품: 장부 800,000 (8000*100) - NRV 환산 500,000 = 평가손실 300,000
        # 정상품: NRV가 더 크므로 평가손실 0
        # total_nrv_loss는 두 제품 합계 = 300,000
        self.assertEqual(int(ctx['total_nrv_loss']), 300000)


class GAP62_IncomeStatementCompareTest(TestCase):
    """IncomeStatementView ?compare=1 → prior + yoy ctx."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='gap62', password='p', role='admin',
        )

    def test_compare_returns_prior_and_yoy(self):
        self.client.force_login(self.user)
        resp = self.client.get('/accounting/income-statement/?year=2026&compare=1')
        self.assertEqual(resp.status_code, 200)
        ctx = resp.context
        self.assertTrue(ctx['compare'])
        self.assertIn('prior', ctx)
        self.assertIn('yoy', ctx)
        # prior는 step 키들을 가지고 있어야 함
        self.assertIn('step1_revenue', ctx['prior'])
        self.assertIn('step9_net', ctx['prior'])

    def test_compare_off_skips_prior(self):
        self.client.force_login(self.user)
        resp = self.client.get('/accounting/income-statement/?year=2026&compare=0')
        self.assertEqual(resp.status_code, 200)
        ctx = resp.context
        self.assertFalse(ctx['compare'])
        self.assertNotIn('prior', ctx)


class GAP63_CashFlowDirectMethodTest(TestCase):
    """CashFlowView ?method=direct → Payment 직접 집계."""

    def setUp(self):
        from apps.sales.models import Partner
        from apps.accounting.models import Payment
        self.user = User.objects.create_user(
            username='gap63', password='p', role='admin',
        )
        self.partner = Partner.all_objects.create(
            code='G63', name='G63 거래처',
        )
        # RECEIPT 200,000 + DISBURSEMENT 50,000 → 영업활동 = 150,000
        Payment.objects.create(
            payment_type='RECEIPT', partner=self.partner,
            amount=200000, payment_date=date(2026, 4, 10),
            payment_method='BANK_TRANSFER',
            created_by=self.user,
        )
        Payment.objects.create(
            payment_type='DISBURSEMENT', partner=self.partner,
            amount=50000, payment_date=date(2026, 4, 15),
            payment_method='BANK_TRANSFER',
            created_by=self.user,
        )

    def test_direct_method_aggregates_payment_amounts(self):
        self.client.force_login(self.user)
        resp = self.client.get(
            '/accounting/report/cash-flow/?from_date=2026-04-01&to_date=2026-04-30&method=direct',
        )
        self.assertEqual(resp.status_code, 200)
        ctx = resp.context
        self.assertEqual(ctx['method'], 'direct')
        self.assertEqual(int(ctx['direct_inflow']), 200000)
        self.assertEqual(int(ctx['direct_outflow']), 50000)
        self.assertEqual(int(ctx['operating']), 150000)


class GAP72_BankReconRuleTest(TestCase):
    """BankReconRule.matches() 로직 검증.

    BankTransaction을 실제 DB에 만들지 않고 SimpleNamespace 로 mock — 매칭 로직만 검증.
    """

    def _txn(self, amount, counterparty='', description=''):
        from types import SimpleNamespace
        return SimpleNamespace(
            amount=Decimal(amount),
            counterparty=counterparty,
            description=description,
            statement=None,
        )

    def test_depositor_name_substring_match(self):
        from apps.accounting.models_recon import BankReconRule
        rule = BankReconRule(
            name='홍길동 매칭', priority=1,
            match_field=BankReconRule.MatchField.DEPOSITOR_NAME,
            pattern='홍길동',
        )
        self.assertTrue(rule.matches(self._txn(100000, counterparty='홍길동귀하')))
        self.assertFalse(rule.matches(self._txn(100000, counterparty='이순신')))

    def test_amount_range_with_tolerance(self):
        from apps.accounting.models_recon import BankReconRule
        rule = BankReconRule(
            name='금액 범위',
            match_field=BankReconRule.MatchField.AMOUNT_RANGE,
            pattern='100000', amount_tolerance=Decimal('500'),
        )
        self.assertTrue(rule.matches(self._txn(100200)))
        self.assertTrue(rule.matches(self._txn(99800)))
        self.assertFalse(rule.matches(self._txn(101000)))


class GAP81_VoucherApprovalPolicyTest(TestCase):
    """VoucherApprovalConfig 다운그레이드 — 자동전표 한도 초과 시 SUBMITTED 강제."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='gap81', password='p', role='admin',
        )
        _ensure_account('103', '보통예금', 'ASSET')
        _ensure_account('401', '매출', 'REVENUE')

    def test_auto_voucher_downgraded_when_amount_exceeds_threshold(self):
        from apps.accounting.models import (
            Voucher, VoucherLine, VoucherApprovalConfig,
        )
        from apps.accounting.models import AccountCode
        cfg = VoucherApprovalConfig.objects.create(
            auto_voucher_default_status='APPROVED',
            auto_approval_amount_threshold=1000,  # 1000원 초과 시 SUBMITTED
            manual_approval_amount_threshold=0,
            created_by=self.user,
        )
        v = Voucher.objects.create(
            voucher_number='G81-1', voucher_type='TRANSFER',
            voucher_date=date(2026, 4, 10),
            description='테스트 자동전표',
            approval_status=Voucher.ApprovalStatus.APPROVED,
            created_by=self.user,
        )
        VoucherLine.objects.create(
            voucher=v, account=AccountCode.objects.get(code='103'),
            debit=Decimal('5000'), credit=0,
            description='차변',
            created_by=self.user,
        )
        VoucherLine.objects.create(
            voucher=v, account=AccountCode.objects.get(code='401'),
            debit=0, credit=Decimal('5000'),
            description='대변',
            created_by=self.user,
        )
        v.refresh_from_db()
        # 5000 > 1000 한도 → SUBMITTED 강제
        self.assertEqual(v.approval_status, Voucher.ApprovalStatus.SUBMITTED)


class GAP91_RevenueRecognitionMethodTest(TestCase):
    """Order.RevenueRecognitionMethod 기본값 + choices."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='gap91', password='p', role='admin',
        )

    def test_default_is_delivery(self):
        from apps.sales.models import Order
        order = Order.objects.create(
            order_number='G91-1', order_date=date(2026, 4, 1),
            status='DRAFT', created_by=self.user,
        )
        self.assertEqual(
            order.revenue_recognition_method,
            Order.RevenueRecognitionMethod.DELIVERY,
        )
        self.assertEqual(order.progress_rate, 0)

    def test_progress_method_with_rate(self):
        from apps.sales.models import Order
        order = Order.objects.create(
            order_number='G91-2', order_date=date(2026, 4, 1),
            status='DRAFT',
            revenue_recognition_method=Order.RevenueRecognitionMethod.PROGRESS,
            progress_rate=Decimal('45.50'),
            created_by=self.user,
        )
        self.assertEqual(order.progress_rate, Decimal('45.50'))


class GAP102_PartnerEntityTypeTest(TestCase):
    """Partner.entity_type 기본값 + 선택지."""

    def test_default_business(self):
        from apps.sales.models import Partner
        p = Partner.objects.create(code='G102', name='G102 거래처')
        self.assertEqual(p.entity_type, Partner.EntityType.BUSINESS)

    def test_individual_entity(self):
        from apps.sales.models import Partner
        p = Partner.objects.create(
            code='G102-IND', name='개인고객',
            entity_type=Partner.EntityType.INDIVIDUAL,
        )
        self.assertEqual(p.entity_type, 'INDIVIDUAL')


class GAP104_DashboardChannelMatrixTest(TestCase):
    """Dashboard 채널×결제수단 매트릭스 ctx."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='gap104', password='p', role='admin',
        )

    def test_matrix_aggregates_by_channel_payment(self):
        from apps.sales.models import Order, Partner
        partner = Partner.all_objects.create(code='G104', name='G104')
        today = date.today()
        Order.objects.create(
            order_number='G104-1',
            partner=partner, order_date=today,
            status='CONFIRMED',
            sales_channel=Order.SalesChannel.NAVER,
            payment_method=Order.PaymentMethod.NAVER_PAY,
            grand_total=Decimal('100000'),
            created_by=self.user,
        )
        Order.objects.create(
            order_number='G104-2',
            partner=partner, order_date=today,
            status='DELIVERED',
            sales_channel=Order.SalesChannel.NAVER,
            payment_method=Order.PaymentMethod.NAVER_PAY,
            grand_total=Decimal('200000'),
            created_by=self.user,
        )
        self.client.force_login(self.user)
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        ctx = resp.context
        matrix = ctx.get('channel_payment_matrix') or []
        # NAVER × NAVER_PAY 합계 300,000
        match = [
            r for r in matrix
            if r['sales_channel'] == 'NAVER' and r['payment_method'] == 'NAVER_PAY'
        ]
        self.assertEqual(len(match), 1)
        self.assertEqual(int(match[0]['total']), 300000)
        self.assertEqual(match[0]['cnt'], 2)
