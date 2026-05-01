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
    RFQ, RFQItem, RFQResponse, VendorScore,
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


class ReceiptOverQuantityTest(TestCase):
    """입고 초과 방지 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='overuser', password='testpass123', role='manager',
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-OVER', name='초과테스트창고', is_default=True,
            created_by=self.user,
        )
        self.partner = Partner.objects.create(
            code='SUP-OVER', name='초과공급처',
            partner_type=Partner.PartnerType.SUPPLIER,
        )
        self.product = Product.objects.create(
            code='OVER-PRD-001', name='초과제품',
            product_type='RAW', cost_price=1000,
            current_stock=0, created_by=self.user,
        )
        self.po = PurchaseOrder.objects.create(
            po_number='PO-OVER-001',
            partner=self.partner,
            order_date=date.today(),
            status=PurchaseOrder.Status.CONFIRMED,
            created_by=self.user,
        )
        self.po_item = PurchaseOrderItem.objects.create(
            purchase_order=self.po,
            product=self.product,
            quantity=100,
            unit_price=Decimal('1000'),
            created_by=self.user,
        )
        self.receipt = GoodsReceipt.objects.create(
            receipt_number='GR-OVER-001',
            purchase_order=self.po,
            receipt_date=date.today(),
            created_by=self.user,
        )

    def test_receipt_exceeds_po_quantity(self):
        """입고수량이 발주 잔여수량 초과 시 차단"""
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            GoodsReceiptItem.objects.create(
                goods_receipt=self.receipt,
                po_item=self.po_item,
                received_quantity=150,  # 발주 100개 초과
                created_by=self.user,
            )

    def test_receipt_partial_then_exceed(self):
        """부분입고 후 잔여 초과 시 차단"""
        from django.core.exceptions import ValidationError
        # 1차 입고: 80개
        GoodsReceiptItem.objects.create(
            goods_receipt=self.receipt,
            po_item=self.po_item,
            received_quantity=80,
            created_by=self.user,
        )
        self.po_item.refresh_from_db()
        self.assertEqual(self.po_item.received_quantity, 80)

        # 2차 입고 시도: 30개 (잔여 20개 초과)
        receipt2 = GoodsReceipt.objects.create(
            receipt_number='GR-OVER-002',
            purchase_order=self.po,
            receipt_date=date.today(),
            created_by=self.user,
        )
        with self.assertRaises(ValidationError):
            GoodsReceiptItem.objects.create(
                goods_receipt=receipt2,
                po_item=self.po_item,
                received_quantity=30,
                created_by=self.user,
            )

    def test_receipt_exact_quantity_succeeds(self):
        """발주수량과 정확히 같은 입고 성공"""
        item = GoodsReceiptItem.objects.create(
            goods_receipt=self.receipt,
            po_item=self.po_item,
            received_quantity=100,
            created_by=self.user,
        )
        self.assertIsNotNone(item.pk)

    def test_receipt_partial_within_limit(self):
        """잔여 범위 내 부분입고 성공"""
        GoodsReceiptItem.objects.create(
            goods_receipt=self.receipt,
            po_item=self.po_item,
            received_quantity=60,
            created_by=self.user,
        )
        receipt2 = GoodsReceipt.objects.create(
            receipt_number='GR-OVER-003',
            purchase_order=self.po,
            receipt_date=date.today(),
            created_by=self.user,
        )
        item2 = GoodsReceiptItem.objects.create(
            goods_receipt=receipt2,
            po_item=self.po_item,
            received_quantity=40,  # 잔여 정확히 40
            created_by=self.user,
        )
        self.assertIsNotNone(item2.pk)


class OverduePOTaskTest(TestCase):
    """입고 지연 Celery 태스크 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='overdue_user', password='testpass123', role='admin',
        )
        Warehouse.objects.create(
            code='WH-OD', name='지연창고', is_default=True, created_by=self.user,
        )
        self.partner = Partner.objects.create(
            code='SUP-OD1', name='지연공급처', partner_type='SUPPLIER',
            created_by=self.user,
        )

    def test_overdue_po_detected(self):
        """입고 예정일 경과 PO가 감지되어야 한다"""
        from apps.purchase.tasks import check_overdue_purchase_orders

        # 지연된 PO
        PurchaseOrder.objects.create(
            partner=self.partner,
            order_date=date.today() - timedelta(days=30),
            expected_date=date.today() - timedelta(days=5),
            status='CONFIRMED',
            created_by=self.user,
        )
        # 정상 PO
        PurchaseOrder.objects.create(
            partner=self.partner,
            order_date=date.today(),
            expected_date=date.today() + timedelta(days=10),
            status='CONFIRMED',
            created_by=self.user,
        )

        result = check_overdue_purchase_orders()
        self.assertIn('1 overdue POs', result)

    def test_no_overdue(self):
        """예정일 전이면 0건이어야 한다"""
        from apps.purchase.tasks import check_overdue_purchase_orders

        PurchaseOrder.objects.create(
            partner=self.partner,
            order_date=date.today(),
            expected_date=date.today() + timedelta(days=10),
            status='CONFIRMED',
            created_by=self.user,
        )
        result = check_overdue_purchase_orders()
        self.assertIn('0 overdue POs', result)


class APDuplicatePreventionTest(TestCase):
    """AP 중복 생성 방지 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='ap_dup_user', password='testpass123', role='admin',
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-AP', name='AP창고', is_default=True, created_by=self.user,
        )
        self.partner = Partner.objects.create(
            code='SUP-AP1', name='AP공급처', partner_type='SUPPLIER',
            created_by=self.user,
        )
        self.product = Product.objects.create(
            code='PRD-AP1', name='AP제품', product_type='RAW',
            cost_price=10000, current_stock=0, created_by=self.user,
        )

    def test_ap_uses_purchase_order_fk(self):
        """AP가 purchase_order FK로 생성되어야 한다"""
        from apps.accounting.models import AccountPayable

        po = PurchaseOrder.objects.create(
            partner=self.partner, order_date=date.today(),
            expected_date=date.today() + timedelta(days=30),
            status='CONFIRMED', created_by=self.user,
        )
        PurchaseOrderItem.objects.create(
            purchase_order=po, product=self.product,
            quantity=10, unit_price=10000,
            amount=100000, created_by=self.user,
        )
        po.update_total()

        # 전량 입고
        receipt = GoodsReceipt.objects.create(
            purchase_order=po, receipt_date=date.today(),
            warehouse=self.warehouse, created_by=self.user,
        )
        GoodsReceiptItem.objects.create(
            goods_receipt=receipt, po_item=po.items.first(),
            received_quantity=10, created_by=self.user,
        )

        # AP가 purchase_order FK로 생성되었는지 확인
        ap = AccountPayable.objects.filter(
            purchase_order=po, is_active=True,
        )
        self.assertEqual(ap.count(), 1)


class VendorScoreAutoCalcTest(TestCase):
    """공급처 평가 종합점수 자동 계산"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='vsuser', password='testpass123', role='manager',
        )
        self.partner = Partner.objects.create(
            code='VS-SUP-001', name='평가공급처',
            partner_type=Partner.PartnerType.SUPPLIER,
            created_by=self.user,
        )

    def test_vendor_score_total_auto_calc(self):
        """save() 시 4항목 평균이 overall_score 에 자동 반영"""
        vs = VendorScore.objects.create(
            partner=self.partner,
            evaluation_date=date.today(),
            delivery_score=5,
            quality_score=4,
            price_score=3,
            service_score=4,
            evaluator=self.user,
            created_by=self.user,
        )
        # (5+4+3+4)/4 = 4.0
        self.assertEqual(vs.overall_score, Decimal('4.0'))

        # 점수 변경 시 재계산
        vs.delivery_score = 3
        vs.quality_score = 3
        vs.price_score = 3
        vs.service_score = 3
        vs.save()
        vs.refresh_from_db()
        self.assertEqual(vs.overall_score, Decimal('3.0'))

    def test_vendor_score_quantize_to_one_decimal(self):
        """비정수 평균은 소수 1자리로 양자화"""
        vs = VendorScore.objects.create(
            partner=self.partner,
            evaluation_date=date.today(),
            delivery_score=5, quality_score=4, price_score=4, service_score=4,
            evaluator=self.user, created_by=self.user,
        )
        # (5+4+4+4)/4 = 4.25 → 4.2 또는 4.3 (ROUND_HALF_EVEN: 4.2)
        self.assertEqual(vs.overall_score.as_tuple().exponent, -1)


class RFQAwardAutoCreatePOTest(TestCase):
    """RFQResponse 낙찰 시 PurchaseOrder 자동 생성"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='rfquser', password='testpass123', role='manager',
        )
        self.partner = Partner.objects.create(
            code='RFQ-SUP-001', name='RFQ공급처',
            partner_type=Partner.PartnerType.SUPPLIER,
            created_by=self.user,
        )
        self.partner_b = Partner.objects.create(
            code='RFQ-SUP-002', name='RFQ공급처B',
            partner_type=Partner.PartnerType.SUPPLIER,
            created_by=self.user,
        )
        self.product = Product.objects.create(
            code='RFQ-PRD-001', name='견적제품',
            product_type='RAW', unit_price=0, cost_price=1000,
            created_by=self.user,
        )
        self.rfq = RFQ.objects.create(
            title='Q1 자재 견적', requested_by=self.user,
            status=RFQ.Status.SENT, created_by=self.user,
        )
        RFQItem.objects.create(
            rfq=self.rfq, product=self.product, quantity=Decimal('100'),
            created_by=self.user,
        )

    def test_rfq_response_select_creates_po(self):
        """is_selected False → True 전환 시 PO 자동 생성"""
        response = RFQResponse.objects.create(
            rfq=self.rfq, partner=self.partner,
            response_date=date.today(),
            total_amount=Decimal('500000'),
            delivery_days=7,
            is_selected=False,
            created_by=self.user,
        )
        self.assertEqual(PurchaseOrder.objects.count(), 0)

        response.is_selected = True
        response.save()

        po_qs = PurchaseOrder.objects.filter(partner=self.partner)
        self.assertEqual(po_qs.count(), 1)
        po = po_qs.first()
        self.assertEqual(po.status, PurchaseOrder.Status.DRAFT)
        self.assertEqual(po.items.count(), 1)
        item = po.items.first()
        self.assertEqual(item.quantity, 100)
        # 500000 / 100 = 5000 단가
        self.assertEqual(item.unit_price, 5000)

        # RFQ 상태 → COMPARED
        self.rfq.refresh_from_db()
        self.assertEqual(self.rfq.status, RFQ.Status.COMPARED)

    def test_rfq_response_already_selected_no_duplicate(self):
        """이미 낙찰된 응답 재저장은 PO 중복 생성하지 않음"""
        response = RFQResponse.objects.create(
            rfq=self.rfq, partner=self.partner,
            response_date=date.today(),
            total_amount=Decimal('500000'),
            delivery_days=7,
            is_selected=True,
            created_by=self.user,
        )
        # 최초 생성(pk 없는 시점)에는 시그널 무시 → PO 0개
        self.assertEqual(PurchaseOrder.objects.count(), 0)

        # 재저장 — 이미 True 상태 유지 → 추가 PO 없음
        response.total_amount = Decimal('600000')
        response.save()
        self.assertEqual(PurchaseOrder.objects.count(), 0)

    def test_rfq_award_unselects_other_responses(self):
        """낙찰 시 다른 응답의 is_selected 자동 해제"""
        r1 = RFQResponse.objects.create(
            rfq=self.rfq, partner=self.partner,
            response_date=date.today(),
            total_amount=Decimal('500000'), delivery_days=7,
            is_selected=False, created_by=self.user,
        )
        r2 = RFQResponse.objects.create(
            rfq=self.rfq, partner=self.partner_b,
            response_date=date.today(),
            total_amount=Decimal('480000'), delivery_days=10,
            is_selected=False, created_by=self.user,
        )
        # r1 낙찰
        r1.is_selected = True
        r1.save()
        # r2 낙찰 — r1 해제되고 PO 는 r2 의 partner_b 로 생성
        r2.is_selected = True
        r2.save()

        r1.refresh_from_db()
        r2.refresh_from_db()
        self.assertFalse(r1.is_selected)
        self.assertTrue(r2.is_selected)

        po_b = PurchaseOrder.objects.filter(partner=self.partner_b)
        self.assertEqual(po_b.count(), 1)
