from datetime import date, timedelta

from django.db import IntegrityError
from django.test import TestCase
from unittest.mock import patch

from apps.inventory.models import Product

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
        past_end = date.today() - timedelta(days=1)
        reg = ProductRegistration.objects.create(
            serial_number='SN-EXPIRED',
            product=self.product,
            customer_name='만료고객',
            phone='010-0000-0002',
            purchase_date=date(2024, 1, 1),
            warranty_start=date(2024, 1, 1),
            warranty_end=past_end,
        )
        self.assertFalse(reg.is_warranty_valid)

    def test_is_warranty_valid_boundary(self):
        """보증 만료일 당일 (경계값 - 유효)"""
        today = date.today()
        reg = ProductRegistration.objects.create(
            serial_number='SN-BOUNDARY',
            product=self.product,
            customer_name='경계고객',
            phone='010-0000-0003',
            purchase_date=date(2025, 3, 16),
            warranty_start=date(2025, 3, 16),
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
