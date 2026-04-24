"""
T5 검증 — ClosingPeriod 크로스 앱 확장 테스트

- accounting/sales/purchase/asset signals에서 마감기간 체크가 silent skip + Notification 발송하는지
- 공통 유틸 validate_closing_period 동작 검증
- 미마감 거래는 정상 처리되는지
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

User = get_user_model()


def _get_or_create_account(code, name, account_type='EXPENSE'):
    from apps.accounting.models import AccountCode
    acct, _ = AccountCode.all_objects.get_or_create(
        code=code,
        defaults={'name': name, 'account_type': account_type},
    )
    if not acct.is_active:
        acct.is_active = True
        acct.save(update_fields=['is_active'])
    return acct


class T5_01_ValidateClosingPeriodUtilTest(TestCase):
    """공통 유틸 validate_closing_period 기본 동작"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='t5util', password='pass', role='admin',
        )

    def test_미마감이면_True_반환(self):
        from apps.accounting.utils import validate_closing_period
        result = validate_closing_period(date(2099, 12, 15))
        self.assertTrue(result)

    def test_마감이면_raise_exception_True_일때_ValidationError(self):
        from apps.accounting.models import ClosingPeriod
        from apps.accounting.utils import validate_closing_period
        ClosingPeriod.objects.create(
            year=2099, month=11, is_closed=True, created_by=self.user,
        )
        with self.assertRaises(ValidationError):
            validate_closing_period(date(2099, 11, 10), raise_exception=True)

    def test_마감이면_raise_False_일때_False_반환_그리고_Notification_생성(self):
        from apps.accounting.models import ClosingPeriod
        from apps.accounting.utils import validate_closing_period
        from apps.core.notification import Notification
        ClosingPeriod.objects.create(
            year=2099, month=10, is_closed=True, created_by=self.user,
        )
        before = Notification.objects.filter(user=self.user).count()
        result = validate_closing_period(
            date(2099, 10, 5),
            raise_exception=False,
            notify_user=self.user,
            context='테스트 컨텍스트',
        )
        self.assertFalse(result)
        after = Notification.objects.filter(user=self.user).count()
        self.assertEqual(after, before + 1)
        noti = Notification.objects.filter(user=self.user).latest('created_at')
        self.assertIn('마감기간 자동처리 누락', noti.title)
        self.assertIn('테스트 컨텍스트', noti.message)

    def test_None_날짜면_True_반환(self):
        from apps.accounting.utils import validate_closing_period
        self.assertTrue(validate_closing_period(None))


class T5_02_SalesARClosingSkipTest(TestCase):
    """sales/signals — AR 자동생성이 마감기간이면 silent skip + 알림"""

    def setUp(self):
        from apps.sales.models import Partner
        self.user = User.objects.create_user(
            username='t5sales', password='pass', role='admin',
        )
        self.partner = Partner.objects.create(
            code='T5-P1', name='T5거래처', created_by=self.user,
        )
        _get_or_create_account('120', '미수금', 'ASSET')
        _get_or_create_account('401', '매출', 'REVENUE')

    def _create_order(self, order_date, status='DRAFT'):
        from apps.sales.models import Order
        return Order.objects.create(
            order_number=f'T5-ORD-{order_date.strftime("%m%d%H%M%S")}',
            partner=self.partner,
            order_date=order_date,
            status=status,
            created_by=self.user,
        )

    def test_마감월_주문확정시_AR_생성_스킵_그리고_알림(self):
        from apps.accounting.models import AccountReceivable, ClosingPeriod
        from apps.core.notification import Notification
        from apps.sales.signals import _auto_create_ar

        ClosingPeriod.objects.create(
            year=2099, month=3, is_closed=True, created_by=self.user,
        )
        order = self._create_order(date(2099, 3, 15))
        # grand_total을 확보하기 위해 직접 amount 주입
        order.total_amount = Decimal('10000')
        order.tax_total = Decimal('1000')
        order.grand_total = Decimal('11000')
        order.save(update_fields=['total_amount', 'tax_total', 'grand_total'])

        before_ars = AccountReceivable.objects.filter(order=order).count()
        before_notis = Notification.objects.filter(user=self.user).count()

        _auto_create_ar(order)

        after_ars = AccountReceivable.objects.filter(order=order).count()
        after_notis = Notification.objects.filter(user=self.user).count()
        self.assertEqual(after_ars, before_ars, '마감기간이면 AR 생성 스킵 필요')
        self.assertEqual(after_notis, before_notis + 1, '알림이 발송되어야 함')

    def test_미마감월_주문확정시_AR_정상생성(self):
        from apps.accounting.models import AccountReceivable
        from apps.sales.signals import _auto_create_ar

        order = self._create_order(date(2099, 5, 10))
        order.total_amount = Decimal('10000')
        order.tax_total = Decimal('1000')
        order.grand_total = Decimal('11000')
        order.save(update_fields=['total_amount', 'tax_total', 'grand_total'])

        _auto_create_ar(order)
        self.assertTrue(
            AccountReceivable.objects.filter(order=order, is_active=True).exists(),
            '미마감이면 AR이 정상 생성되어야 함',
        )


class T5_03_PurchaseAPClosingSkipTest(TestCase):
    """purchase/signals — AP 자동생성이 마감기간이면 silent skip + 알림"""

    def setUp(self):
        from apps.sales.models import Partner
        self.user = User.objects.create_user(
            username='t5pur', password='pass', role='admin',
        )
        self.partner = Partner.objects.create(
            code='T5-P2', name='T5공급처', created_by=self.user,
        )
        _get_or_create_account('501', '매입원가', 'EXPENSE')
        _get_or_create_account('253', '미지급금', 'LIABILITY')

    def test_마감월_발주입고완료시_AP_스킵_그리고_알림(self):
        from apps.accounting.models import AccountPayable, ClosingPeriod
        from apps.core.notification import Notification
        from apps.purchase.models import PurchaseOrder
        from apps.purchase.signals import _auto_create_ap

        ClosingPeriod.objects.create(
            year=date.today().year, month=date.today().month,
            is_closed=True, created_by=self.user,
        )
        po = PurchaseOrder.objects.create(
            po_number='T5-PO-01',
            partner=self.partner,
            order_date=date.today(),
            created_by=self.user,
        )
        po.total_amount = Decimal('5000')
        po.tax_total = Decimal('500')
        po.grand_total = Decimal('5500')
        po.save(update_fields=['total_amount', 'tax_total', 'grand_total'])

        before_aps = AccountPayable.objects.filter(purchase_order=po).count()
        before_notis = Notification.objects.filter(user=self.user).count()

        _auto_create_ap(po)

        after_aps = AccountPayable.objects.filter(purchase_order=po).count()
        after_notis = Notification.objects.filter(user=self.user).count()
        self.assertEqual(after_aps, before_aps, '마감기간이면 AP 생성 스킵')
        self.assertGreaterEqual(after_notis, before_notis + 1, '알림 발송 필요')


class T5_04_AccountingVoucherClosingSkipTest(TestCase):
    """accounting/signals — Voucher/AR/AP 자동전표가 마감기간이면 skip + 알림"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='t5acc', password='pass', role='admin',
        )
        _get_or_create_account('120', '미수금', 'ASSET')
        _get_or_create_account('401', '매출', 'REVENUE')

    def test_AR_생성시_마감월이면_자동전표_스킵(self):
        from apps.accounting.models import (
            AccountReceivable, ClosingPeriod, Voucher,
        )
        from apps.core.notification import Notification
        from apps.sales.models import Partner

        partner = Partner.objects.create(
            code='T5-P3', name='T5AR', created_by=self.user,
        )
        ClosingPeriod.objects.create(
            year=2099, month=6, is_closed=True, created_by=self.user,
        )

        before_v = Voucher.objects.count()
        before_n = Notification.objects.filter(user=self.user).count()

        ar = AccountReceivable.objects.create(
            partner=partner,
            amount=Decimal('10000'),
            due_date=date(2099, 6, 20),
            status='PENDING',
            created_by=self.user,
        )
        # AR은 생성되지만 자동전표는 스킵되어야 함
        self.assertTrue(ar.pk)
        after_v = Voucher.objects.count()
        after_n = Notification.objects.filter(user=self.user).count()
        self.assertEqual(after_v, before_v, '마감월이면 자동전표 스킵')
        self.assertGreaterEqual(after_n, before_n + 1, '알림 발송 필요')

    def test_AR_생성시_미마감월이면_자동전표_생성(self):
        from apps.accounting.models import AccountReceivable, Voucher
        from apps.sales.models import Partner

        partner = Partner.objects.create(
            code='T5-P4', name='T5AR2', created_by=self.user,
        )
        before_v = Voucher.objects.count()
        AccountReceivable.objects.create(
            partner=partner,
            amount=Decimal('10000'),
            due_date=date(2099, 7, 20),
            status='PENDING',
            created_by=self.user,
        )
        after_v = Voucher.objects.count()
        self.assertEqual(after_v, before_v + 1, '미마감이면 자동전표 생성')


class T5_05_VoucherDirectCreateBlockTest(TestCase):
    """수동 Voucher 생성은 여전히 마감기간이면 ValidationError로 차단"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='t5vblk', password='pass', role='admin',
        )

    def test_마감월_수동전표_생성시_ValidationError(self):
        from apps.accounting.models import ClosingPeriod, Voucher
        ClosingPeriod.objects.create(
            year=2099, month=8, is_closed=True, created_by=self.user,
        )
        with self.assertRaises(ValidationError):
            Voucher.objects.create(
                voucher_number='T5-VBLK-01',
                voucher_type='TRANSFER',
                voucher_date=date(2099, 8, 15),
                description='수동전표',
                created_by=self.user,
            )
