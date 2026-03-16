from decimal import Decimal
from datetime import date, timedelta

from django.test import TestCase

from apps.accounts.models import User
from apps.inventory.models import Product, Warehouse, StockMovement
from apps.production.models import (
    BOM, BOMItem, ProductionPlan, WorkOrder, ProductionRecord,
)


class ProductionSignalTest(TestCase):
    """생산실적 시그널 테스트 — ProductionRecord 생성 시 재고 자동 처리 및 상태 전환 검증"""

    def setUp(self):
        """테스트에 필요한 사용자, 창고, 제품, BOM, 생산계획, 작업지시 생성"""
        self.user = User.objects.create_user(
            username='prod_user', password='testpass123', role='staff',
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-PROD', name='생산창고', created_by=self.user,
        )
        # 완제품
        self.finished_product = Product.objects.create(
            code='FP-001',
            name='완제품A',
            product_type='FINISHED',
            unit_price=50000,
            cost_price=30000,
            current_stock=0,
            created_by=self.user,
        )
        # 원자재 2종
        self.raw_material_1 = Product.objects.create(
            code='RM-001',
            name='원자재1',
            product_type='RAW',
            unit_price=0,
            cost_price=5000,
            current_stock=1000,
            created_by=self.user,
        )
        self.raw_material_2 = Product.objects.create(
            code='RM-002',
            name='원자재2',
            product_type='RAW',
            unit_price=0,
            cost_price=3000,
            current_stock=1000,
            created_by=self.user,
        )
        # BOM
        self.bom = BOM.objects.create(
            product=self.finished_product,
            version='1.0',
            is_default=True,
            created_by=self.user,
        )
        self.bom_item_1 = BOMItem.objects.create(
            bom=self.bom,
            material=self.raw_material_1,
            quantity=Decimal('2.000'),
            loss_rate=Decimal('0.00'),
            created_by=self.user,
        )
        self.bom_item_2 = BOMItem.objects.create(
            bom=self.bom,
            material=self.raw_material_2,
            quantity=Decimal('3.000'),
            loss_rate=Decimal('0.00'),
            created_by=self.user,
        )
        # 생산계획
        self.plan = ProductionPlan.objects.create(
            plan_number='PP-001',
            product=self.finished_product,
            bom=self.bom,
            planned_quantity=100,
            planned_start=date.today(),
            planned_end=date.today() + timedelta(days=7),
            status='IN_PROGRESS',
            created_by=self.user,
        )
        # 작업지시
        self.work_order = WorkOrder.objects.create(
            order_number='WO-001',
            production_plan=self.plan,
            quantity=100,
            status='IN_PROGRESS',
            created_by=self.user,
        )

    def _create_record(self, good_quantity, defect_quantity=0, work_order=None):
        """ProductionRecord 생성 헬퍼"""
        return ProductionRecord.objects.create(
            work_order=work_order or self.work_order,
            good_quantity=good_quantity,
            defect_quantity=defect_quantity,
            record_date=date.today(),
            worker=self.user,
            created_by=self.user,
        )

    # ── 재고 자동 처리 테스트 ────────────────────────────────

    def test_production_record_creates_prod_in_movement(self):
        """생산실적 등록 시 완제품 PROD_IN 전표가 생성되는지 확인"""
        self._create_record(good_quantity=10)

        prod_in = StockMovement.objects.filter(
            movement_type='PROD_IN', product=self.finished_product,
        )
        self.assertEqual(prod_in.count(), 1)
        self.assertEqual(prod_in.first().quantity, 10)

    def test_production_record_creates_prod_out_for_bom_items(self):
        """생산실적 등록 시 BOM 항목별 원자재 PROD_OUT 전표가 생성되는지 확인"""
        self._create_record(good_quantity=10)

        prod_out = StockMovement.objects.filter(movement_type='PROD_OUT')
        self.assertEqual(prod_out.count(), 2)

        # 원자재1: 소요량 2 * 양품 10 = 20
        rm1_out = prod_out.get(product=self.raw_material_1)
        self.assertEqual(rm1_out.quantity, 20)

        # 원자재2: 소요량 3 * 양품 10 = 30
        rm2_out = prod_out.get(product=self.raw_material_2)
        self.assertEqual(rm2_out.quantity, 30)

    def test_production_record_updates_product_stock(self):
        """생산실적 등록 시 제품 재고가 실제로 갱신되는지 확인"""
        self._create_record(good_quantity=10)

        self.finished_product.refresh_from_db()
        self.assertEqual(self.finished_product.current_stock, 10)

        self.raw_material_1.refresh_from_db()
        self.assertEqual(self.raw_material_1.current_stock, 980)  # 1000 - 20

        self.raw_material_2.refresh_from_db()
        self.assertEqual(self.raw_material_2.current_stock, 970)  # 1000 - 30

    # ── 상태 자동 전환 테스트 ────────────────────────────────

    def test_workorder_auto_completes(self):
        """총 생산량이 작업지시 수량 이상이면 작업지시가 COMPLETED로 전환되는지 확인"""
        # 작업지시 수량: 100, 먼저 60 생산
        self._create_record(good_quantity=60)
        self.work_order.refresh_from_db()
        self.assertNotEqual(self.work_order.status, 'COMPLETED')

        # 추가 40 생산 → 합계 100 ≥ 100
        self._create_record(good_quantity=40)
        self.work_order.refresh_from_db()
        self.assertEqual(self.work_order.status, 'COMPLETED')
        self.assertIsNotNone(self.work_order.completed_at)

    def test_plan_auto_completes_when_all_workorders_done(self):
        """모든 작업지시가 완료되면 생산계획이 COMPLETED로 전환되는지 확인"""
        # 작업지시 수량만큼 생산하여 작업지시 완료 처리
        self._create_record(good_quantity=100)

        self.work_order.refresh_from_db()
        self.assertEqual(self.work_order.status, 'COMPLETED')

        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, 'COMPLETED')
        self.assertGreater(self.plan.actual_cost, 0)

    # ── BOM 손실률 테스트 ────────────────────────────────────

    def test_bom_loss_rate_applied(self):
        """BOM 항목의 손실률이 자재 소모량에 반영되는지 확인"""
        # 원자재1의 손실률을 10%로 변경
        self.bom_item_1.loss_rate = Decimal('10.00')
        self.bom_item_1.save()

        self._create_record(good_quantity=10)

        # effective_quantity = 2.000 * (1 + 10/100) = 2.200
        # consumed = int(2.200 * 10) = 22
        rm1_out = StockMovement.objects.get(
            movement_type='PROD_OUT', product=self.raw_material_1,
        )
        self.assertEqual(rm1_out.quantity, 22)

    # ── 예외 케이스 테스트 ───────────────────────────────────

    def test_no_stock_movement_when_zero_good_quantity(self):
        """양품수량이 0이면 PROD_IN 전표가 생성되지 않는지 확인"""
        self._create_record(good_quantity=0, defect_quantity=5)

        prod_in = StockMovement.objects.filter(movement_type='PROD_IN')
        self.assertEqual(prod_in.count(), 0)

        # 원자재 소모도 없어야 함 (int(effective_qty * 0) = 0)
        prod_out = StockMovement.objects.filter(movement_type='PROD_OUT')
        self.assertEqual(prod_out.count(), 0)

    # ── 다중 실적 테스트 ─────────────────────────────────────

    def test_multiple_production_records(self):
        """여러 생산실적이 누적되어 재고와 상태에 반영되는지 확인"""
        self._create_record(good_quantity=30)
        self._create_record(good_quantity=30)
        self._create_record(good_quantity=40)

        # 완제품 재고: 30 + 30 + 40 = 100
        self.finished_product.refresh_from_db()
        self.assertEqual(self.finished_product.current_stock, 100)

        # 원자재1 소모: (2 * 30) + (2 * 30) + (2 * 40) = 200
        self.raw_material_1.refresh_from_db()
        self.assertEqual(self.raw_material_1.current_stock, 800)

        # 작업지시 완료 (총 100 ≥ 100)
        self.work_order.refresh_from_db()
        self.assertEqual(self.work_order.status, 'COMPLETED')

        # 생산계획도 완료
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, 'COMPLETED')


class BOMPropertyTest(TestCase):
    """BOM 및 BOMItem 프로퍼티 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='bom_user', password='testpass123',
        )
        self.product = Product.objects.create(
            code='FP-BOM', name='BOM제품', product_type='FINISHED',
            unit_price=10000, cost_price=5000, created_by=self.user,
        )
        self.material = Product.objects.create(
            code='RM-BOM', name='BOM원자재', product_type='RAW',
            unit_price=0, cost_price=2000, created_by=self.user,
        )
        self.bom = BOM.objects.create(
            product=self.product, version='1.0', created_by=self.user,
        )
        self.bom_item = BOMItem.objects.create(
            bom=self.bom, material=self.material,
            quantity=Decimal('3.000'), loss_rate=Decimal('5.00'),
            created_by=self.user,
        )

    def test_effective_quantity(self):
        """effective_quantity가 손실률 포함하여 계산되는지 확인"""
        # 3.000 * (1 + 5/100) = 3.150
        self.assertEqual(self.bom_item.effective_quantity, Decimal('3.150'))

    def test_material_cost(self):
        """material_cost가 유효소요량 * 원가로 계산되는지 확인"""
        # int(3.150 * 2000) = 6300
        self.assertEqual(self.bom_item.material_cost, 6300)

    def test_total_material_cost(self):
        """BOM total_material_cost가 전체 항목 합산인지 확인"""
        self.assertEqual(self.bom.total_material_cost, 6300)
