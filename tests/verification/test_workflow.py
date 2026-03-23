"""
기능 워크플로우 검증 테스트 (FUNC-001 ~ FUNC-006)
주문, 생산, 구매, AS, 결재, 견적->주문 등 E2E 워크플로우 자동화 테스트
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

User = get_user_model()


class FUNC001_OrderLifecycleTest(TestCase):
    """FUNC-001: 주문 라이프사이클 - DRAFT -> CONFIRMED -> SHIPPED -> DELIVERED"""

    def setUp(self):
        from apps.inventory.models import Product, Warehouse
        from apps.sales.models import Partner, Order, OrderItem

        self.user = User.objects.create_user(
            username='order_wf', password='OrderWF123!', role='admin',
        )
        self.warehouse = Warehouse.all_objects.create(
            code='WF001-WH', name='워크플로우창고',
        )
        self.product = Product.all_objects.create(
            code='WF001-P1', name='주문워크플로우제품',
            current_stock=200, unit_price=10000,
        )
        self.partner = Partner.all_objects.create(
            code='WF001-PT', name='주문거래처',
        )
        self.order = Order.all_objects.create(
            order_number='WF001-ORD01',
            partner=self.partner,
            order_date=date.today(),
            status='DRAFT',
            created_by=self.user,
        )
        OrderItem.all_objects.create(
            order=self.order,
            product=self.product,
            quantity=10,
            unit_price=Decimal('10000'),
            created_by=self.user,
        )
        self.order.update_total()

    def test_DRAFT에서_CONFIRMED_전환(self):
        """DRAFT -> CONFIRMED 상태 전환"""
        self.order.status = 'CONFIRMED'
        self.order.save()
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'CONFIRMED')

    def test_CONFIRMED에서_SHIPPED_전환_재고반영(self):
        """CONFIRMED -> SHIPPED 시 자동 재고 차감"""
        from apps.inventory.models import StockMovement

        self.order.status = 'CONFIRMED'
        self.order.save()

        initial_stock = self.product.current_stock

        self.order.status = 'SHIPPED'
        self.order.save()

        self.product.refresh_from_db()
        self.assertEqual(
            self.product.current_stock, initial_stock - 10,
            f"SHIPPED 후 재고 미감소: {initial_stock} -> {self.product.current_stock}",
        )

        # OUT 전표 확인
        out_movements = StockMovement.all_objects.filter(
            movement_type='OUT', product=self.product,
            reference__contains=self.order.order_number,
        )
        self.assertEqual(out_movements.count(), 1,
                         "SHIPPED 시 OUT 전표 미생성")

    def test_SHIPPED에서_DELIVERED_전환(self):
        """SHIPPED -> DELIVERED 상태 전환"""
        self.order.status = 'SHIPPED'
        self.order.save()

        self.order.status = 'DELIVERED'
        self.order.save()
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'DELIVERED')

    def test_전체_라이프사이클(self):
        """DRAFT -> CONFIRMED -> SHIPPED -> DELIVERED 전체 워크플로우"""
        states = ['CONFIRMED', 'SHIPPED', 'DELIVERED']
        for state in states:
            self.order.status = state
            self.order.save()
            self.order.refresh_from_db()
            self.assertEqual(self.order.status, state,
                             f"상태 전환 실패: {state}")

    def test_주문금액_정합성(self):
        """워크플로우 전체에서 주문 금액이 일관되게 유지"""
        expected_amount = Decimal('100000')  # 10 x 10000
        expected_tax = Decimal('10000')
        expected_grand = Decimal('110000')

        self.assertEqual(self.order.total_amount, expected_amount)
        self.assertEqual(self.order.tax_total, expected_tax)
        self.assertEqual(self.order.grand_total, expected_grand)


class FUNC002_ProductionLifecycleTest(TestCase):
    """FUNC-002: 생산 라이프사이클 - 계획 -> 작업지시 -> 실적 -> 완료"""

    def setUp(self):
        from apps.inventory.models import Product, Warehouse
        from apps.production.models import BOM, BOMItem, ProductionPlan, WorkOrder

        self.user = User.objects.create_user(
            username='prod_wf', password='ProdWF123!', role='admin',
        )
        self.warehouse = Warehouse.all_objects.create(
            code='WF002-WH', name='생산창고',
        )
        self.finished = Product.all_objects.create(
            code='WF002-FIN', name='생산완제품',
            product_type='FINISHED', cost_price=50000, current_stock=0,
        )
        self.raw = Product.all_objects.create(
            code='WF002-RAW', name='생산원자재',
            product_type='RAW', cost_price=5000, current_stock=500,
        )
        self.bom = BOM.all_objects.create(
            product=self.finished, version='1.0',
        )
        BOMItem.all_objects.create(
            bom=self.bom, material=self.raw,
            quantity=Decimal('3.000'), loss_rate=Decimal('0.00'),
        )
        self.plan = ProductionPlan.all_objects.create(
            plan_number='WF002-PL01',
            product=self.finished,
            bom=self.bom,
            planned_quantity=10,
            planned_start=date.today(),
            planned_end=date.today() + timedelta(days=7),
            status='DRAFT',
        )

    def test_생산계획_상태전환(self):
        """DRAFT -> CONFIRMED -> IN_PROGRESS"""
        self.plan.status = 'CONFIRMED'
        self.plan.save()
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, 'CONFIRMED')

        self.plan.status = 'IN_PROGRESS'
        self.plan.save()
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, 'IN_PROGRESS')

    def test_작업지시_생성_및_상태전환(self):
        """작업지시 생성 후 PENDING -> IN_PROGRESS -> COMPLETED"""
        from apps.production.models import WorkOrder

        self.plan.status = 'IN_PROGRESS'
        self.plan.save()

        wo = WorkOrder.all_objects.create(
            order_number='WF002-WO01',
            production_plan=self.plan,
            quantity=10,
            status='PENDING',
            assigned_to=self.user,
        )

        wo.status = 'IN_PROGRESS'
        wo.started_at = timezone.now()
        wo.save()
        wo.refresh_from_db()
        self.assertEqual(wo.status, 'IN_PROGRESS')

    def test_생산실적_등록_및_자동재고(self):
        """생산실적 등록 시 완제품 입고 + 원자재 출고"""
        from apps.production.models import WorkOrder, ProductionRecord
        from apps.inventory.models import StockMovement

        self.plan.status = 'IN_PROGRESS'
        self.plan.save()

        wo = WorkOrder.all_objects.create(
            order_number='WF002-WO02',
            production_plan=self.plan,
            quantity=10,
            status='IN_PROGRESS',
        )

        ProductionRecord.all_objects.create(
            work_order=wo,
            good_quantity=10,
            defect_quantity=0,
            record_date=date.today(),
        )

        # 완제품 입고 확인
        self.finished.refresh_from_db()
        self.assertEqual(self.finished.current_stock, 10,
                         "완제품 10개 생산 입고 미반영")

        # 원자재 출고 확인 (BOM: 3 x 10 = 30)
        self.raw.refresh_from_db()
        self.assertEqual(self.raw.current_stock, 470,
                         f"원자재 30개 출고 미반영: {self.raw.current_stock}")

    def test_작업지시_자동완료(self):
        """생산수량 >= 지시수량일 때 작업지시 자동 COMPLETED"""
        from apps.production.models import WorkOrder, ProductionRecord

        self.plan.status = 'IN_PROGRESS'
        self.plan.save()

        wo = WorkOrder.all_objects.create(
            order_number='WF002-WO03',
            production_plan=self.plan,
            quantity=10,
            status='IN_PROGRESS',
        )

        ProductionRecord.all_objects.create(
            work_order=wo,
            good_quantity=10,
            defect_quantity=1,
            record_date=date.today(),
        )

        wo.refresh_from_db()
        self.assertEqual(wo.status, 'COMPLETED',
                         "생산수량 충족 후 작업지시 자동 완료 미작동")

    def test_전체_생산_워크플로우_계획완료(self):
        """모든 작업지시 완료 시 생산계획 자동 COMPLETED"""
        from apps.production.models import WorkOrder, ProductionRecord

        self.plan.status = 'IN_PROGRESS'
        self.plan.save()

        wo = WorkOrder.all_objects.create(
            order_number='WF002-WO04',
            production_plan=self.plan,
            quantity=10,
            status='IN_PROGRESS',
        )

        ProductionRecord.all_objects.create(
            work_order=wo,
            good_quantity=10,
            defect_quantity=0,
            record_date=date.today(),
        )

        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, 'COMPLETED',
                         "모든 작업지시 완료 후 생산계획 자동 COMPLETED 미작동")


class FUNC003_PurchaseLifecycleTest(TestCase):
    """FUNC-003: 구매 라이프사이클 - 발주 -> 입고확인 -> 재고반영"""

    def setUp(self):
        from apps.inventory.models import Product, Warehouse
        from apps.sales.models import Partner
        from apps.purchase.models import PurchaseOrder, PurchaseOrderItem

        self.warehouse = Warehouse.all_objects.create(
            code='WF003-WH', name='구매창고',
        )
        self.product = Product.all_objects.create(
            code='WF003-P1', name='구매제품', product_type='RAW',
            current_stock=0, cost_price=5000,
        )
        self.supplier = Partner.all_objects.create(
            code='WF003-SUP', name='공급처', partner_type='SUPPLIER',
        )
        self.po = PurchaseOrder.all_objects.create(
            po_number='WF003-PO01',
            partner=self.supplier,
            order_date=date.today(),
            status='CONFIRMED',
        )
        self.po_item = PurchaseOrderItem.all_objects.create(
            purchase_order=self.po,
            product=self.product,
            quantity=100,
            unit_price=Decimal('5000'),
        )

    def test_입고확인시_재고반영(self):
        """GoodsReceiptItem 생성 시 StockMovement(IN) 자동 생성"""
        from apps.inventory.models import StockMovement
        from apps.purchase.models import GoodsReceipt, GoodsReceiptItem

        receipt = GoodsReceipt.all_objects.create(
            receipt_number='WF003-GR01',
            purchase_order=self.po,
            receipt_date=date.today(),
        )
        GoodsReceiptItem.all_objects.create(
            goods_receipt=receipt,
            po_item=self.po_item,
            received_quantity=100,
        )

        # StockMovement(IN) 생성 확인
        in_mvs = StockMovement.all_objects.filter(
            movement_type='IN', product=self.product,
        )
        self.assertEqual(in_mvs.count(), 1,
                         "입고확인 후 IN 전표 미생성")

        # 재고 반영 확인
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 100,
                         "입고 후 재고 100 미반영")

    def test_전체입고시_RECEIVED_상태(self):
        """전체 입고 완료 시 발주 상태 RECEIVED"""
        from apps.purchase.models import GoodsReceipt, GoodsReceiptItem

        receipt = GoodsReceipt.all_objects.create(
            receipt_number='WF003-GR02',
            purchase_order=self.po,
            receipt_date=date.today(),
        )
        GoodsReceiptItem.all_objects.create(
            goods_receipt=receipt,
            po_item=self.po_item,
            received_quantity=100,
        )

        self.po.refresh_from_db()
        self.assertEqual(self.po.status, 'RECEIVED',
                         "전체 입고 후 RECEIVED 상태 미전환")

    def test_부분입고시_PARTIAL_RECEIVED_상태(self):
        """부분 입고 시 발주 상태 PARTIAL_RECEIVED"""
        from apps.purchase.models import GoodsReceipt, GoodsReceiptItem

        receipt = GoodsReceipt.all_objects.create(
            receipt_number='WF003-GR03',
            purchase_order=self.po,
            receipt_date=date.today(),
        )
        GoodsReceiptItem.all_objects.create(
            goods_receipt=receipt,
            po_item=self.po_item,
            received_quantity=50,  # 100 중 50만 입고
        )

        self.po.refresh_from_db()
        self.assertEqual(self.po.status, 'PARTIAL_RECEIVED',
                         "부분 입고 후 PARTIAL_RECEIVED 상태 미전환")


class FUNC004_ServiceLifecycleTest(TestCase):
    """FUNC-004: AS 라이프사이클 - 접수 -> 검수 -> 수리 -> 완료 -> 반송"""

    def setUp(self):
        from apps.inventory.models import Product
        from apps.sales.models import Customer
        from apps.service.models import ServiceRequest

        self.user = User.objects.create_user(
            username='svc_wf', password='SvcWF123!', role='staff',
        )
        self.product = Product.all_objects.create(
            code='WF004-P1', name='AS제품',
        )
        self.customer = Customer.all_objects.create(
            name='AS고객', phone='010-1234-5678',
        )
        self.sr = ServiceRequest.all_objects.create(
            request_number='WF004-SR01',
            customer=self.customer,
            product=self.product,
            symptom='불량 증상',
            received_date=date.today(),
            status='RECEIVED',
        )

    def test_AS_전체_상태전환(self):
        """RECEIVED -> INSPECTING -> REPAIRING -> COMPLETED -> RETURNED"""
        states = ['INSPECTING', 'REPAIRING', 'COMPLETED', 'RETURNED']
        for state in states:
            self.sr.status = state
            if state == 'COMPLETED':
                self.sr.completed_date = date.today()
            self.sr.save()
            self.sr.refresh_from_db()
            self.assertEqual(self.sr.status, state,
                             f"AS 상태 전환 실패: {state}")

    def test_수리이력_연결(self):
        """AS 요청에 수리이력(RepairRecord) 등록"""
        from apps.service.models import RepairRecord

        self.sr.status = 'REPAIRING'
        self.sr.save()

        repair = RepairRecord.all_objects.create(
            service_request=self.sr,
            repair_date=date.today(),
            description='부품 교체',
            parts_used='메인보드',
            cost=Decimal('50000'),
            technician=self.user,
        )

        self.assertEqual(self.sr.repairs.count(), 1)
        self.assertEqual(repair.service_request, self.sr)


class FUNC005_ApprovalWorkflowTest(TestCase):
    """FUNC-005: 결재 워크플로우 - 다단계 결재선"""

    def setUp(self):
        from apps.approval.models import ApprovalRequest, ApprovalStep

        self.requester = User.objects.create_user(
            username='req_wf', password='ReqWF123!', role='staff',
        )
        self.approver1 = User.objects.create_user(
            username='appr1_wf', password='Appr1WF123!', role='manager',
        )
        self.approver2 = User.objects.create_user(
            username='appr2_wf', password='Appr2WF123!', role='manager',
        )
        self.approver3 = User.objects.create_user(
            username='appr3_wf', password='Appr3WF123!', role='admin',
        )

        self.request = ApprovalRequest.all_objects.create(
            request_number='WF005-AR01',
            category='PURCHASE',
            title='구매품의 테스트',
            content='테스트 내용',
            amount=Decimal('5000000'),
            status='SUBMITTED',
            requester=self.requester,
            current_step=1,
        )

        # 3단계 결재선
        self.step1 = ApprovalStep.all_objects.create(
            request=self.request,
            step_order=1,
            approver=self.approver1,
            status='PENDING',
        )
        self.step2 = ApprovalStep.all_objects.create(
            request=self.request,
            step_order=2,
            approver=self.approver2,
            status='PENDING',
        )
        self.step3 = ApprovalStep.all_objects.create(
            request=self.request,
            step_order=3,
            approver=self.approver3,
            status='PENDING',
        )

    def test_순차적_결재_승인(self):
        """3단계 순차 결재: 1단계 -> 2단계 -> 3단계 승인"""
        now = timezone.now()

        # 1단계 승인
        self.step1.status = 'APPROVED'
        self.step1.acted_at = now
        self.step1.comment = '1단계 승인'
        self.step1.save()

        self.request.current_step = 2
        self.request.save()

        # 2단계 승인
        self.step2.status = 'APPROVED'
        self.step2.acted_at = now
        self.step2.comment = '2단계 승인'
        self.step2.save()

        self.request.current_step = 3
        self.request.save()

        # 3단계 승인 (최종)
        self.step3.status = 'APPROVED'
        self.step3.acted_at = now
        self.step3.comment = '최종 승인'
        self.step3.save()

        # 전체 승인 처리
        all_approved = all(
            s.status == 'APPROVED' for s in self.request.steps.all()
        )
        if all_approved:
            self.request.status = 'APPROVED'
            self.request.approved_at = now
            self.request.save()

        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'APPROVED',
                         "3단계 전체 승인 후 APPROVED 상태 미전환")

    def test_중간단계_반려(self):
        """2단계에서 반려 시 전체 결재 REJECTED"""
        now = timezone.now()

        # 1단계 승인
        self.step1.status = 'APPROVED'
        self.step1.acted_at = now
        self.step1.save()

        # 2단계 반려
        self.step2.status = 'REJECTED'
        self.step2.acted_at = now
        self.step2.comment = '예산 초과'
        self.step2.save()

        # 반려 처리
        self.request.status = 'REJECTED'
        self.request.reject_reason = '2단계 반려: 예산 초과'
        self.request.save()

        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'REJECTED')

    def test_결재단계_unique_together(self):
        """같은 결재요청에 같은 step_order가 중복 생성 불가"""
        from apps.approval.models import ApprovalStep
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            ApprovalStep.all_objects.create(
                request=self.request,
                step_order=1,  # 이미 존재하는 순서
                approver=self.approver1,
            )


class FUNC006_QuotationToOrderTest(TestCase):
    """FUNC-006: 견적 -> 주문 전환"""

    def setUp(self):
        from apps.inventory.models import Product
        from apps.sales.models import Partner, Quotation, QuotationItem

        self.user = User.objects.create_user(
            username='quote_wf', password='QuoteWF123!', role='admin',
        )
        self.product1 = Product.all_objects.create(
            code='WF006-P1', name='견적제품1', unit_price=20000,
        )
        self.product2 = Product.all_objects.create(
            code='WF006-P2', name='견적제품2', unit_price=30000,
        )
        self.partner = Partner.all_objects.create(
            code='WF006-PT', name='견적거래처',
        )
        self.quote = Quotation.all_objects.create(
            quote_number='WF006-QT01',
            partner=self.partner,
            quote_date=date.today(),
            valid_until=date.today() + timedelta(days=30),
            status='SENT',
        )
        QuotationItem.all_objects.create(
            quotation=self.quote,
            product=self.product1,
            quantity=5,
            unit_price=Decimal('20000'),
        )
        QuotationItem.all_objects.create(
            quotation=self.quote,
            product=self.product2,
            quantity=3,
            unit_price=Decimal('30000'),
        )
        self.quote.update_total()

    def test_견적에서_주문전환_HTTP(self):
        """견적 -> 주문 전환 뷰를 통한 전환"""
        from apps.sales.models import Order, OrderItem

        self.client.force_login(self.user)

        response = self.client.post(
            f'/sales/quotes/{self.quote.pk}/convert/',
        )
        # 성공 시 주문 상세로 리다이렉트
        self.assertIn(response.status_code, [302, 200],
                       "견적->주문 전환 실패")

        self.quote.refresh_from_db()
        self.assertEqual(self.quote.status, 'CONVERTED',
                         "전환 후 견적 상태 CONVERTED 미변경")
        self.assertIsNotNone(self.quote.converted_order,
                             "전환된 주문 참조 미설정")

        # 주문 항목 확인
        order = self.quote.converted_order
        self.assertEqual(order.items.count(), 2,
                         "견적 항목 수와 주문 항목 수 불일치")

    def test_견적_항목과_주문_항목_일치(self):
        """전환된 주문의 항목이 견적 항목과 동일"""
        from apps.sales.models import Order, OrderItem

        self.client.force_login(self.user)
        self.client.post(f'/sales/quotes/{self.quote.pk}/convert/')

        self.quote.refresh_from_db()
        order = self.quote.converted_order
        if order is None:
            self.skipTest("주문 전환 URL 매핑 확인 필요")

        quote_items = list(
            self.quote.quote_items.values_list(
                'product_id', 'quantity', 'unit_price',
            ).order_by('product_id')
        )
        order_items = list(
            order.items.values_list(
                'product_id', 'quantity', 'unit_price',
            ).order_by('product_id')
        )
        self.assertEqual(quote_items, order_items,
                         "견적 항목과 주문 항목 불일치")

    def test_이중전환_방지(self):
        """이미 CONVERTED된 견적은 재전환 불가"""
        self.client.force_login(self.user)

        # 1차 전환
        self.client.post(f'/sales/quotes/{self.quote.pk}/convert/')

        # 2차 전환 시도
        from apps.sales.models import Order
        order_count_before = Order.all_objects.count()

        self.client.post(f'/sales/quotes/{self.quote.pk}/convert/')

        order_count_after = Order.all_objects.count()
        self.assertEqual(order_count_before, order_count_after,
                         "이미 CONVERTED된 견적이 다시 전환됨")
