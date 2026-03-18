from datetime import date, timedelta
from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.inventory.models import Product, Warehouse, StockMovement
from apps.sales.models import Partner
from apps.purchase.models import (
    PurchaseOrder, PurchaseOrderItem, GoodsReceipt, GoodsReceiptItem,
)

User = get_user_model()


class PurchaseOrderModelTest(TestCase):
    """발주서 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='pouser', password='testpass123', role='manager',
        )
        self.partner = Partner.objects.create(
            code='SUP-001', name='공급처A',
            partner_type=Partner.PartnerType.SUPPLIER,
            created_by=self.user,
        )
        self.product = Product.objects.create(
            code='PO-PRD-001', name='구매제품',
            product_type='RAW', unit_price=0, cost_price=5000,
            created_by=self.user,
        )

    def test_po_creation(self):
        """발주서 생성"""
        po = PurchaseOrder.objects.create(
            po_number='PO-2026-001',
            partner=self.partner,
            order_date=date.today(),
            status=PurchaseOrder.Status.DRAFT,
            created_by=self.user,
        )
        self.assertEqual(po.po_number, 'PO-2026-001')
        self.assertEqual(po.status, 'DRAFT')

    def test_po_str(self):
        """발주서 문자열 표현"""
        po = PurchaseOrder.objects.create(
            po_number='PO-STR-001',
            partner=self.partner,
            order_date=date.today(),
            created_by=self.user,
        )
        self.assertEqual(str(po), 'PO-STR-001')

    def test_po_unique_number(self):
        """발주번호 중복 불가"""
        PurchaseOrder.objects.create(
            po_number='PO-DUP-001',
            partner=self.partner,
            order_date=date.today(),
            created_by=self.user,
        )
        with self.assertRaises(IntegrityError):
            PurchaseOrder.objects.create(
                po_number='PO-DUP-001',
                partner=self.partner,
                order_date=date.today(),
                created_by=self.user,
            )

    def test_po_update_total(self):
        """발주서 합계 갱신"""
        po = PurchaseOrder.objects.create(
            po_number='PO-TOTAL-001',
            partner=self.partner,
            order_date=date.today(),
            created_by=self.user,
        )
        PurchaseOrderItem.objects.create(
            purchase_order=po,
            product=self.product,
            quantity=10,
            unit_price=Decimal('5000'),
            created_by=self.user,
        )
        po.update_total()
        po.refresh_from_db()
        self.assertEqual(po.total_amount, Decimal('50000'))
        self.assertEqual(po.tax_total, Decimal('5000'))
        self.assertEqual(po.grand_total, Decimal('55000'))

    def test_po_status_choices(self):
        """발주서 상태 선택지"""
        statuses = dict(PurchaseOrder.Status.choices)
        self.assertIn('DRAFT', statuses)
        self.assertIn('CONFIRMED', statuses)
        self.assertIn('RECEIVED', statuses)
        self.assertIn('CANCELLED', statuses)

    def test_po_soft_delete(self):
        """발주서 soft delete"""
        po = PurchaseOrder.objects.create(
            po_number='PO-SD-001',
            partner=self.partner,
            order_date=date.today(),
            created_by=self.user,
        )
        po.soft_delete()
        self.assertFalse(PurchaseOrder.objects.filter(pk=po.pk).exists())
        self.assertTrue(PurchaseOrder.all_objects.filter(pk=po.pk).exists())


class PurchaseOrderItemTest(TestCase):
    """발주항목 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='poitemuser', password='testpass123', role='manager',
        )
        self.partner = Partner.objects.create(
            code='SUP-ITEM-001', name='공급처B',
            partner_type=Partner.PartnerType.SUPPLIER,
        )
        self.product = Product.objects.create(
            code='POI-PRD-001', name='발주항목제품',
            product_type='RAW', unit_price=0, cost_price=3000,
            created_by=self.user,
        )
        self.po = PurchaseOrder.objects.create(
            po_number='PO-ITEM-001',
            partner=self.partner,
            order_date=date.today(),
            created_by=self.user,
        )

    def test_item_auto_calculates_amount(self):
        """발주항목 저장 시 공급가액 자동 계산"""
        item = PurchaseOrderItem.objects.create(
            purchase_order=self.po,
            product=self.product,
            quantity=20,
            unit_price=Decimal('3000'),
            created_by=self.user,
        )
        self.assertEqual(item.amount, Decimal('60000'))

    def test_item_auto_calculates_tax(self):
        """발주항목 저장 시 부가세 10% 자동 계산"""
        item = PurchaseOrderItem.objects.create(
            purchase_order=self.po,
            product=self.product,
            quantity=20,
            unit_price=Decimal('3000'),
            created_by=self.user,
        )
        self.assertEqual(item.tax_amount, Decimal('6000'))

    def test_item_str(self):
        """발주항목 문자열 표현"""
        item = PurchaseOrderItem.objects.create(
            purchase_order=self.po,
            product=self.product,
            quantity=5,
            unit_price=Decimal('3000'),
            created_by=self.user,
        )
        self.assertEqual(str(item), '발주항목제품 x 5')

    def test_remaining_quantity(self):
        """잔여수량 계산"""
        item = PurchaseOrderItem.objects.create(
            purchase_order=self.po,
            product=self.product,
            quantity=100,
            unit_price=Decimal('3000'),
            created_by=self.user,
        )
        self.assertEqual(item.remaining_quantity, 100)
        item.received_quantity = 40
        item.save()
        self.assertEqual(item.remaining_quantity, 60)


class GoodsReceiptSignalTest(TestCase):
    """입고 시그널 테스트 - GoodsReceiptItem 생성 시 재고/발주 상태 자동 갱신"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='gruser', password='testpass123', role='manager',
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-GR', name='입고창고', created_by=self.user,
        )
        self.partner = Partner.objects.create(
            code='SUP-GR-001', name='입고공급처',
            partner_type=Partner.PartnerType.SUPPLIER,
        )
        self.product = Product.objects.create(
            code='GR-PRD-001', name='입고제품',
            product_type='RAW', cost_price=2000,
            current_stock=0, created_by=self.user,
        )
        self.po = PurchaseOrder.objects.create(
            po_number='PO-GR-001',
            partner=self.partner,
            order_date=date.today(),
            status=PurchaseOrder.Status.CONFIRMED,
            created_by=self.user,
        )
        self.po_item = PurchaseOrderItem.objects.create(
            purchase_order=self.po,
            product=self.product,
            quantity=100,
            unit_price=Decimal('2000'),
            created_by=self.user,
        )
        self.receipt = GoodsReceipt.objects.create(
            receipt_number='GR-001',
            purchase_order=self.po,
            receipt_date=date.today(),
            created_by=self.user,
        )

    def test_receipt_creates_stock_movement(self):
        """입고항목 생성 시 StockMovement IN 생성"""
        GoodsReceiptItem.objects.create(
            goods_receipt=self.receipt,
            po_item=self.po_item,
            received_quantity=50,
            created_by=self.user,
        )
        movements = StockMovement.objects.filter(
            movement_type='IN', product=self.product,
        )
        self.assertEqual(movements.count(), 1)
        self.assertEqual(movements.first().quantity, 50)

    def test_receipt_updates_product_stock(self):
        """입고 시 제품 현재고 증가"""
        GoodsReceiptItem.objects.create(
            goods_receipt=self.receipt,
            po_item=self.po_item,
            received_quantity=50,
            created_by=self.user,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 50)

    def test_receipt_updates_po_item_received_quantity(self):
        """입고 시 발주항목의 입고수량 갱신"""
        GoodsReceiptItem.objects.create(
            goods_receipt=self.receipt,
            po_item=self.po_item,
            received_quantity=30,
            created_by=self.user,
        )
        self.po_item.refresh_from_db()
        self.assertEqual(self.po_item.received_quantity, 30)

    def test_partial_receipt_updates_po_status(self):
        """부분 입고 시 발주서 상태가 PARTIAL_RECEIVED로 변경"""
        GoodsReceiptItem.objects.create(
            goods_receipt=self.receipt,
            po_item=self.po_item,
            received_quantity=50,
            created_by=self.user,
        )
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, PurchaseOrder.Status.PARTIAL_RECEIVED)

    def test_full_receipt_updates_po_status(self):
        """전체 입고 시 발주서 상태가 RECEIVED로 변경"""
        GoodsReceiptItem.objects.create(
            goods_receipt=self.receipt,
            po_item=self.po_item,
            received_quantity=100,
            created_by=self.user,
        )
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, PurchaseOrder.Status.RECEIVED)

    def test_multiple_receipts_accumulate(self):
        """여러 입고가 누적되어 발주항목 입고수량에 반영"""
        GoodsReceiptItem.objects.create(
            goods_receipt=self.receipt,
            po_item=self.po_item,
            received_quantity=40,
            created_by=self.user,
        )
        receipt2 = GoodsReceipt.objects.create(
            receipt_number='GR-002',
            purchase_order=self.po,
            receipt_date=date.today(),
            created_by=self.user,
        )
        GoodsReceiptItem.objects.create(
            goods_receipt=receipt2,
            po_item=self.po_item,
            received_quantity=60,
            created_by=self.user,
        )
        self.po_item.refresh_from_db()
        self.assertEqual(self.po_item.received_quantity, 100)

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 100)

        self.po.refresh_from_db()
        self.assertEqual(self.po.status, PurchaseOrder.Status.RECEIVED)


class GoodsReceiptModelTest(TestCase):
    """입고확인 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='grmodel', password='testpass123', role='manager',
        )
        self.partner = Partner.objects.create(
            code='SUP-GRM-001', name='모델공급처',
            partner_type=Partner.PartnerType.SUPPLIER,
        )
        self.po = PurchaseOrder.objects.create(
            po_number='PO-GRM-001',
            partner=self.partner,
            order_date=date.today(),
            created_by=self.user,
        )

    def test_receipt_str(self):
        """입고확인 문자열 표현"""
        receipt = GoodsReceipt.objects.create(
            receipt_number='GR-STR-001',
            purchase_order=self.po,
            receipt_date=date.today(),
            created_by=self.user,
        )
        self.assertEqual(str(receipt), 'GR-STR-001')

    def test_receipt_unique_number(self):
        """입고번호 중복 불가"""
        GoodsReceipt.objects.create(
            receipt_number='GR-DUP-001',
            purchase_order=self.po,
            receipt_date=date.today(),
            created_by=self.user,
        )
        with self.assertRaises(IntegrityError):
            GoodsReceipt.objects.create(
                receipt_number='GR-DUP-001',
                purchase_order=self.po,
                receipt_date=date.today(),
                created_by=self.user,
            )
