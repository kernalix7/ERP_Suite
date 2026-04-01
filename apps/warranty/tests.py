from datetime import date, timedelta
from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase

from apps.inventory.models import Product
from apps.sales.models import Customer, Order, OrderItem

from .models import ProductRegistration


class ProductRegistrationTests(TestCase):
    """정품등록 모델 테스트"""

    def setUp(self):
        self.product = Product.objects.create(
            code='PRD-W01',
            name='보증 테스트 제품',
            product_type=Product.ProductType.FINISHED,
        )

    def test_creation(self):
        """정품등록 생성"""
        reg = ProductRegistration.objects.create(
            serial_number='SN-2026-0001',
            product=self.product,
            customer_name='김테스트',
            phone='010-1111-2222',
            email='test@example.com',
            purchase_date=date(2026, 1, 15),
            warranty_start=date(2026, 1, 15),
            warranty_end=date(2027, 1, 14),
        )
        self.assertEqual(reg.serial_number, 'SN-2026-0001')
        self.assertEqual(reg.product, self.product)
        self.assertFalse(reg.is_verified)
        self.assertEqual(str(reg), 'SN-2026-0001 - 김테스트')

    def test_is_warranty_valid_active(self):
        """보증기간 내 (유효)"""
        future_end = date.today() + timedelta(days=180)
        reg = ProductRegistration.objects.create(
            serial_number='SN-VALID',
            product=self.product,
            customer_name='유효고객',
            phone='010-0000-0001',
            purchase_date=date(2026, 1, 1),
            warranty_start=date(2026, 1, 1),
            warranty_end=future_end,
        )
        self.assertTrue(reg.is_warranty_valid)

    def test_is_warranty_valid_expired(self):
        """보증기간 만료 (무효)"""
        start = date(2024, 1, 1)
        # warranty_days를 어제까지로 설정하면 만료
        days_until_yesterday = (date.today() - timedelta(days=1) - start).days
        reg = ProductRegistration.objects.create(
            serial_number='SN-EXPIRED',
            product=self.product,
            customer_name='만료고객',
            phone='010-0000-0002',
            purchase_date=start,
            warranty_start=start,
            warranty_days=days_until_yesterday,
            warranty_end=date.today() - timedelta(days=1),
        )
        self.assertFalse(reg.is_warranty_valid)

    def test_is_warranty_valid_boundary(self):
        """보증 만료일 당일 (경계값 - 유효)"""
        today = date.today()
        start = date(2025, 3, 16)
        days_until_today = (today - start).days
        reg = ProductRegistration.objects.create(
            serial_number='SN-BOUNDARY',
            product=self.product,
            customer_name='경계고객',
            phone='010-0000-0003',
            purchase_date=start,
            warranty_start=start,
            warranty_days=days_until_today,
            warranty_end=today,
        )
        # warranty_end >= date.today() → 당일은 유효
        self.assertTrue(reg.is_warranty_valid)

    def test_serial_number_uniqueness(self):
        """시리얼번호 중복 불가"""
        ProductRegistration.objects.create(
            serial_number='SN-UNIQUE-001',
            product=self.product,
            customer_name='고객A',
            phone='010-0000-1111',
            purchase_date=date(2026, 2, 1),
            warranty_start=date(2026, 2, 1),
            warranty_end=date(2027, 1, 31),
        )
        with self.assertRaises(IntegrityError):
            ProductRegistration.objects.create(
                serial_number='SN-UNIQUE-001',
                product=self.product,
                customer_name='고객B',
                phone='010-0000-2222',
                purchase_date=date(2026, 3, 1),
                warranty_start=date(2026, 3, 1),
                warranty_end=date(2027, 2, 28),
            )

    def test_verification_status(self):
        """인증 상태 변경"""
        reg = ProductRegistration.objects.create(
            serial_number='SN-VERIFY',
            product=self.product,
            customer_name='인증고객',
            phone='010-0000-3333',
            purchase_date=date(2026, 1, 1),
            warranty_start=date(2026, 1, 1),
            warranty_end=date(2027, 1, 1),
        )
        self.assertFalse(reg.is_verified)

        reg.is_verified = True
        reg.save()
        reg.refresh_from_db()
        self.assertTrue(reg.is_verified)


class ProductRegistrationSignalTests(TestCase):
    """정품등록 시 주문 자동 연결 시그널 테스트"""

    def setUp(self):
        self.product = Product.objects.create(
            code='PRD-WS-001',
            name='시그널 보증 제품',
            product_type=Product.ProductType.FINISHED,
            unit_price=Decimal('100000'),
        )
        self.customer = Customer.objects.create(
            code='CUST-WRT01', name='보증고객',
            phone='010-7777-8888',
        )
        self.order = Order.objects.create(
            order_date=date(2026, 3, 1),
            customer=self.customer,
            status=Order.Status.DELIVERED,
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=1,
            unit_price=Decimal('100000'),
        )

    def test_auto_link_order_on_registration(self):
        """주문번호 기반 serial_number로 고객 자동 연결"""
        serial = f'{self.order.order_number}-{self.order_item.pk}'
        reg = ProductRegistration.objects.create(
            serial_number=serial,
            product=self.product,
            customer_name='보증고객',
            phone='010-7777-8888',
            purchase_date=date(2026, 3, 1),
            warranty_start=date(2026, 3, 1),
            warranty_end=date(2027, 3, 1),
        )
        reg.refresh_from_db()
        self.assertEqual(reg.customer_id, self.customer.pk)

    def test_non_order_serial_no_link(self):
        """ORD-로 시작하지 않는 serial은 연결 안 함"""
        reg = ProductRegistration.objects.create(
            serial_number='CUSTOM-SN-12345',
            product=self.product,
            customer_name='일반고객',
            phone='010-0000-1111',
            purchase_date=date(2026, 3, 1),
            warranty_start=date(2026, 3, 1),
            warranty_end=date(2027, 3, 1),
        )
        reg.refresh_from_db()
        self.assertIsNone(reg.customer_id)

    def test_already_has_customer_no_overwrite(self):
        """이미 customer가 있으면 덮어쓰지 않음"""
        other_customer = Customer.objects.create(
            code='CUST-OTHER', name='다른고객',
            phone='010-1111-2222',
        )
        serial = f'{self.order.order_number}-{self.order_item.pk}'
        reg = ProductRegistration.objects.create(
            serial_number=serial,
            product=self.product,
            customer=other_customer,
            customer_name='다른고객',
            phone='010-1111-2222',
            purchase_date=date(2026, 3, 1),
            warranty_start=date(2026, 3, 1),
            warranty_end=date(2027, 3, 1),
        )
        reg.refresh_from_db()
        self.assertEqual(reg.customer_id, other_customer.pk)
