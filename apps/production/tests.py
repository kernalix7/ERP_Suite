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

    def _create_record(self, good_quantity,
                       defect_quantity=0, work_order=None):
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
        """양품수량이 0이면 PROD_IN 전표가 생성되지 않는지 확인
        단, 불량 수량이 있으면 원자재 소모(PROD_OUT)는 발생함"""
        self._create_record(good_quantity=0, defect_quantity=5)

        prod_in = StockMovement.objects.filter(movement_type='PROD_IN')
        self.assertEqual(prod_in.count(), 0)

        # 불량 5개 생산 → 원자재 소모 발생 (양품+불량 기준)
        prod_out = StockMovement.objects.filter(movement_type='PROD_OUT')
        self.assertEqual(prod_out.count(), 2)  # BOM 항목 2개

        # 원자재1: 소요량 2 * 불량 5 = 10
        rm1_out = prod_out.get(product=self.raw_material_1)
        self.assertEqual(rm1_out.quantity, 10)

        # 원자재2: 소요량 3 * 불량 5 = 15
        rm2_out = prod_out.get(product=self.raw_material_2)
        self.assertEqual(rm2_out.quantity, 15)

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


class BOMModelTest(TestCase):
    """BOM 모델 추가 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='bom_model_user', password='testpass123',
        )
        self.finished = Product.objects.create(
            code='BOM-FIN', name='BOM완제품', product_type='FINISHED',
            unit_price=50000, cost_price=30000, created_by=self.user,
        )
        self.raw1 = Product.objects.create(
            code='BOM-RAW1', name='BOM원자재1', product_type='RAW',
            unit_price=0, cost_price=1000, created_by=self.user,
        )
        self.raw2 = Product.objects.create(
            code='BOM-RAW2', name='BOM원자재2', product_type='RAW',
            unit_price=0, cost_price=2000, created_by=self.user,
        )

    def test_bom_str(self):
        """BOM 문자열 표현"""
        bom = BOM.objects.create(
            product=self.finished, version='2.0', created_by=self.user,
        )
        self.assertEqual(str(bom), 'BOM완제품 v2.0')

    def test_bom_unique_together(self):
        """같은 제품+버전 BOM 중복 불가"""
        from django.db import IntegrityError
        BOM.objects.create(
            product=self.finished, version='1.0', created_by=self.user,
        )
        with self.assertRaises(IntegrityError):
            BOM.objects.create(
                product=self.finished, version='1.0', created_by=self.user,
            )

    def test_bom_multiple_materials(self):
        """BOM에 여러 자재 항목"""
        bom = BOM.objects.create(
            product=self.finished, version='1.0', created_by=self.user,
        )
        BOMItem.objects.create(
            bom=bom, material=self.raw1,
            quantity=Decimal('5.000'), loss_rate=Decimal('0'),
            created_by=self.user,
        )
        BOMItem.objects.create(
            bom=bom, material=self.raw2,
            quantity=Decimal('3.000'), loss_rate=Decimal('0'),
            created_by=self.user,
        )
        # total = (5 * 1000) + (3 * 2000) = 5000 + 6000 = 11000
        self.assertEqual(bom.total_material_cost, 11000)

    def test_bom_item_str(self):
        """BOMItem 문자열 표현"""
        bom = BOM.objects.create(
            product=self.finished, version='1.0', created_by=self.user,
        )
        item = BOMItem.objects.create(
            bom=bom, material=self.raw1,
            quantity=Decimal('10.000'), loss_rate=Decimal('0'),
            created_by=self.user,
        )
        self.assertEqual(str(item), 'BOM원자재1 x 10.000')

    def test_bom_default_flag(self):
        """기본 BOM 플래그"""
        bom = BOM.objects.create(
            product=self.finished, version='1.0',
            is_default=True, created_by=self.user,
        )
        self.assertTrue(bom.is_default)

    def test_bom_soft_delete(self):
        """BOM soft delete"""
        bom = BOM.objects.create(
            product=self.finished, version='1.0', created_by=self.user,
        )
        bom.soft_delete()
        self.assertFalse(BOM.objects.filter(pk=bom.pk).exists())
        self.assertTrue(BOM.all_objects.filter(pk=bom.pk).exists())


class ProductionPlanModelTest(TestCase):
    """생산계획 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='plan_user', password='testpass123',
        )
        self.product = Product.objects.create(
            code='PLAN-FP', name='계획완제품', product_type='FINISHED',
            unit_price=10000, cost_price=5000, created_by=self.user,
        )
        self.raw = Product.objects.create(
            code='PLAN-RM', name='계획원자재', product_type='RAW',
            cost_price=1000, current_stock=10000, created_by=self.user,
        )
        self.bom = BOM.objects.create(
            product=self.product, version='1.0', created_by=self.user,
        )
        BOMItem.objects.create(
            bom=self.bom, material=self.raw,
            quantity=Decimal('2.000'), loss_rate=Decimal('0'),
            created_by=self.user,
        )

    def test_plan_str(self):
        """생산계획 문자열 표현"""
        plan = ProductionPlan.objects.create(
            plan_number='PP-STR-001',
            product=self.product, bom=self.bom,
            planned_quantity=100,
            planned_start=date.today(),
            planned_end=date.today() + timedelta(days=7),
            created_by=self.user,
        )
        self.assertIn('PP-STR-001', str(plan))
        self.assertIn('계획완제품', str(plan))

    def test_plan_status_choices(self):
        """생산계획 상태 선택지"""
        choices = dict(ProductionPlan.Status.choices)
        self.assertIn('DRAFT', choices)
        self.assertIn('CONFIRMED', choices)
        self.assertIn('IN_PROGRESS', choices)
        self.assertIn('COMPLETED', choices)
        self.assertIn('CANCELLED', choices)

    def test_plan_progress_rate_zero(self):
        """진행률 - 생산 전 0%"""
        plan = ProductionPlan.objects.create(
            plan_number='PP-PROG-001',
            product=self.product, bom=self.bom,
            planned_quantity=100,
            planned_start=date.today(),
            planned_end=date.today() + timedelta(days=7),
            created_by=self.user,
        )
        self.assertEqual(plan.progress_rate, 0)

    def test_plan_progress_rate_with_production(self):
        """진행률 - 생산 후 계산"""
        Warehouse.objects.create(
            code='WH-PLAN', name='계획창고',
            created_by=self.user,
        )
        plan = ProductionPlan.objects.create(
            plan_number='PP-PROG-002',
            product=self.product, bom=self.bom,
            planned_quantity=100,
            planned_start=date.today(),
            planned_end=date.today() + timedelta(days=7),
            status='IN_PROGRESS',
            created_by=self.user,
        )
        wo = WorkOrder.objects.create(
            order_number='WO-PROG-001',
            production_plan=plan,
            quantity=100,
            status='IN_PROGRESS',
            created_by=self.user,
        )
        ProductionRecord.objects.create(
            work_order=wo,
            good_quantity=50,
            record_date=date.today(),
            created_by=self.user,
        )
        self.assertEqual(plan.progress_rate, 50.0)

    def test_plan_soft_delete(self):
        """생산계획 soft delete"""
        plan = ProductionPlan.objects.create(
            plan_number='PP-SD-001',
            product=self.product, bom=self.bom,
            planned_quantity=10,
            planned_start=date.today(),
            planned_end=date.today() + timedelta(days=1),
            created_by=self.user,
        )
        plan.soft_delete()
        self.assertFalse(ProductionPlan.objects.filter(pk=plan.pk).exists())


class WorkOrderModelTest(TestCase):
    """작업지시 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='wo_user', password='testpass123',
        )
        self.product = Product.objects.create(
            code='WO-FP', name='작업지시완제품', product_type='FINISHED',
            unit_price=10000, cost_price=5000, created_by=self.user,
        )
        self.bom = BOM.objects.create(
            product=self.product, version='1.0', created_by=self.user,
        )
        self.plan = ProductionPlan.objects.create(
            plan_number='PP-WO-001',
            product=self.product, bom=self.bom,
            planned_quantity=100,
            planned_start=date.today(),
            planned_end=date.today() + timedelta(days=7),
            created_by=self.user,
        )

    def test_work_order_str(self):
        """작업지시 문자열 표현"""
        wo = WorkOrder.objects.create(
            order_number='WO-STR-001',
            production_plan=self.plan,
            quantity=50,
            created_by=self.user,
        )
        self.assertEqual(str(wo), 'WO-STR-001')

    def test_work_order_status_choices(self):
        """작업지시 상태 선택지"""
        choices = dict(WorkOrder.Status.choices)
        self.assertIn('PENDING', choices)
        self.assertIn('IN_PROGRESS', choices)
        self.assertIn('COMPLETED', choices)
        self.assertIn('CANCELLED', choices)

    def test_work_order_default_status(self):
        """기본 상태는 PENDING"""
        wo = WorkOrder.objects.create(
            order_number='WO-DEF-001',
            production_plan=self.plan,
            quantity=50,
            created_by=self.user,
        )
        self.assertEqual(wo.status, WorkOrder.Status.PENDING)

    def test_production_record_str(self):
        """생산실적 문자열 표현"""
        wo = WorkOrder.objects.create(
            order_number='WO-REC-STR',
            production_plan=self.plan,
            quantity=100,
            created_by=self.user,
        )
        rec = ProductionRecord.objects.create(
            work_order=wo,
            good_quantity=10,
            record_date=date(2026, 3, 17),
            created_by=self.user,
        )
        self.assertIn('WO-REC-STR', str(rec))
        self.assertIn('2026-03-17', str(rec))

    def test_production_record_total_quantity(self):
        """생산실적 총수량 = 양품 + 불량"""
        wo = WorkOrder.objects.create(
            order_number='WO-TOT-001',
            production_plan=self.plan,
            quantity=100,
            created_by=self.user,
        )
        rec = ProductionRecord.objects.create(
            work_order=wo,
            good_quantity=80,
            defect_quantity=5,
            record_date=date.today(),
            created_by=self.user,
        )
        self.assertEqual(rec.total_quantity, 85)


class StandardCostTest(TestCase):
    """표준원가 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='stdcost_user', password='testpass123', role='staff',
        )
        self.product = Product.objects.create(
            code='SC-FP-001', name='표준원가제품',
            product_type='FINISHED', unit_price=50000,
            cost_price=30000, created_by=self.user,
        )
        self.raw = Product.objects.create(
            code='SC-RM-001', name='표준원가원자재',
            product_type='RAW', cost_price=5000,
            created_by=self.user,
        )
        self.bom = BOM.objects.create(
            product=self.product, version='1.0',
            is_default=True, created_by=self.user,
        )
        BOMItem.objects.create(
            bom=self.bom, material=self.raw,
            quantity=Decimal('3.000'), loss_rate=Decimal('0'),
            created_by=self.user,
        )

    def test_standard_cost_auto_calculate(self):
        """save() 시 노무비/간접비/합계 자동 계산"""
        from apps.production.models import StandardCost
        sc = StandardCost.objects.create(
            product=self.product,
            version='1.0',
            effective_date=date.today(),
            material_cost=15000,
            direct_labor_hours=Decimal('2.00'),
            labor_rate_per_hour=10000,
            overhead_rate=Decimal('50.00'),
            is_current=True,
            created_by=self.user,
        )
        # 노무비 = 2.00 * 10000 = 20000
        self.assertEqual(sc.labor_cost, 20000)
        # 간접비 = 20000 * 50 / 100 = 10000
        self.assertEqual(sc.overhead_cost, 10000)
        # 합계 = 15000 + 20000 + 10000 = 45000
        self.assertEqual(sc.total_standard_cost, 45000)

    def test_is_current_auto_toggle(self):
        """동일 제품에 새 현행 표준원가 등록 시 기존 것이 자동 해제"""
        from apps.production.models import StandardCost
        sc1 = StandardCost.objects.create(
            product=self.product,
            version='1.0',
            effective_date=date.today(),
            material_cost=10000,
            is_current=True,
            created_by=self.user,
        )
        self.assertTrue(sc1.is_current)

        sc2 = StandardCost.objects.create(
            product=self.product,
            version='2.0',
            effective_date=date.today(),
            material_cost=12000,
            is_current=True,
            created_by=self.user,
        )
        # 새 것이 현행
        self.assertTrue(sc2.is_current)
        # 기존 것은 자동 해제
        sc1.refresh_from_db()
        self.assertFalse(sc1.is_current)


class ProductionCancelCascadeTest(TestCase):
    """생산계획/작업지시 취소 시 재고 복원 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='cancel_user', password='testpass123', role='staff',
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-CANCEL', name='취소테스트창고', created_by=self.user,
        )
        self.finished_product = Product.objects.create(
            code='CANCEL-FP', name='취소완제품',
            product_type='FINISHED', unit_price=50000,
            cost_price=30000, current_stock=0,
            created_by=self.user,
        )
        self.raw_material = Product.objects.create(
            code='CANCEL-RM', name='취소원자재',
            product_type='RAW', cost_price=5000,
            current_stock=1000, created_by=self.user,
        )
        self.bom = BOM.objects.create(
            product=self.finished_product, version='1.0',
            is_default=True, created_by=self.user,
        )
        BOMItem.objects.create(
            bom=self.bom, material=self.raw_material,
            quantity=Decimal('2.000'), loss_rate=Decimal('0'),
            created_by=self.user,
        )
        self.plan = ProductionPlan.objects.create(
            plan_number='PP-CANCEL-001',
            product=self.finished_product, bom=self.bom,
            planned_quantity=100,
            planned_start=date.today(),
            planned_end=date.today() + timedelta(days=7),
            status='IN_PROGRESS',
            created_by=self.user,
        )
        self.work_order = WorkOrder.objects.create(
            order_number='WO-CANCEL-001',
            production_plan=self.plan,
            quantity=100,
            status='IN_PROGRESS',
            created_by=self.user,
        )

    def test_plan_cancel_restores_stock(self):
        """ProductionPlan CANCELLED 시 재고이동 soft delete + 재고 복원"""
        # 생산실적 등록 → 완제품 +10, 원자재 -20
        ProductionRecord.objects.create(
            work_order=self.work_order,
            good_quantity=10,
            record_date=date.today(),
            worker=self.user,
            created_by=self.user,
        )
        self.finished_product.refresh_from_db()
        self.assertEqual(self.finished_product.current_stock, 10)
        self.raw_material.refresh_from_db()
        self.assertEqual(self.raw_material.current_stock, 980)

        # 생산계획 취소
        self.plan.status = 'CANCELLED'
        self.plan.save()

        # 재고이동이 soft delete되어 재고가 복원되어야 함
        self.finished_product.refresh_from_db()
        self.assertEqual(self.finished_product.current_stock, 0)
        self.raw_material.refresh_from_db()
        self.assertEqual(self.raw_material.current_stock, 1000)

        # soft delete된 재고이동 확인
        active_movements = StockMovement.objects.filter(
            movement_type__in=['PROD_IN', 'PROD_OUT'], is_active=True,
        )
        self.assertEqual(active_movements.count(), 0)

    def test_plan_cancel_cascades_workorder_status(self):
        """ProductionPlan CANCELLED 시 관련 WorkOrder도 CANCELLED로 변경"""
        # 작업지시가 IN_PROGRESS 상태
        self.assertEqual(self.work_order.status, 'IN_PROGRESS')

        # 두 번째 작업지시 추가
        wo2 = WorkOrder.objects.create(
            order_number='WO-CANCEL-002',
            production_plan=self.plan,
            quantity=50,
            status='PENDING',
            created_by=self.user,
        )

        # 생산계획 취소
        self.plan.status = 'CANCELLED'
        self.plan.save()

        # 모든 작업지시가 CANCELLED로 변경되어야 함
        self.work_order.refresh_from_db()
        self.assertEqual(self.work_order.status, 'CANCELLED')
        wo2.refresh_from_db()
        self.assertEqual(wo2.status, 'CANCELLED')

    def test_workorder_cancel_restores_stock(self):
        """WorkOrder CANCELLED 시 동일하게 재고 복원"""
        # 생산실적 등록 → 완제품 +10, 원자재 -20
        ProductionRecord.objects.create(
            work_order=self.work_order,
            good_quantity=10,
            record_date=date.today(),
            worker=self.user,
            created_by=self.user,
        )
        self.finished_product.refresh_from_db()
        self.assertEqual(self.finished_product.current_stock, 10)
        self.raw_material.refresh_from_db()
        self.assertEqual(self.raw_material.current_stock, 980)

        # 작업지시 취소
        self.work_order.status = 'CANCELLED'
        self.work_order.save()

        # 재고 복원 확인
        self.finished_product.refresh_from_db()
        self.assertEqual(self.finished_product.current_stock, 0)
        self.raw_material.refresh_from_db()
        self.assertEqual(self.raw_material.current_stock, 1000)


class MRPViewTest(TestCase):
    """MRP 뷰 테스트"""

    def setUp(self):
        self.manager = User.objects.create_user(
            username='mrp_manager', password='testpass123', role='manager',
        )
        self.staff = User.objects.create_user(
            username='mrp_staff', password='testpass123', role='staff',
        )
        self.finished = Product.objects.create(
            code='MRP-FP', name='MRP완제품',
            product_type='FINISHED', unit_price=50000,
            cost_price=30000, created_by=self.manager,
        )
        self.raw = Product.objects.create(
            code='MRP-RM', name='MRP원자재',
            product_type='RAW', cost_price=5000,
            current_stock=10, created_by=self.manager,
        )
        self.bom = BOM.objects.create(
            product=self.finished, version='1.0',
            is_default=True, created_by=self.manager,
        )
        BOMItem.objects.create(
            bom=self.bom, material=self.raw,
            quantity=Decimal('5.000'), loss_rate=Decimal('0'),
            created_by=self.manager,
        )

    def test_mrp_page_loads(self):
        """/production/mrp/ 페이지 접근 가능 (manager 권한)"""
        self.client.force_login(self.manager)
        response = self.client.get('/production/mrp/')
        self.assertEqual(response.status_code, 200)

    def test_mrp_calculates_shortage(self):
        """BOM 전개 후 부족 자재 수량 계산 확인"""
        self.client.force_login(self.manager)
        # 생산계획 생성: 100개 생산 → 원자재 5 * 100 = 500개 필요, 재고 10개 → 부족 490
        plan = ProductionPlan.objects.create(
            plan_number='PP-MRP-001',
            product=self.finished, bom=self.bom,
            planned_quantity=100,
            planned_start=date.today(),
            planned_end=date.today() + timedelta(days=7),
            status='CONFIRMED',
            created_by=self.manager,
        )
        response = self.client.get(
            '/production/mrp/', {'plan': str(plan.pk)},
        )
        self.assertEqual(response.status_code, 200)
        # context에서 mrp_items 확인
        mrp_items = response.context.get('mrp_items', [])
        self.assertTrue(len(mrp_items) > 0)
        # 첫 번째 결과의 부족 자재 확인
        shortage_item = mrp_items[0]
        self.assertEqual(shortage_item['material'].pk, self.raw.pk)
        # 필요: 500, 가용: 10, 부족: 490
        self.assertEqual(shortage_item['total_required'], Decimal('500.000'))
        self.assertEqual(shortage_item['shortage'], Decimal('490'))


class CostSyncTest(TestCase):
    """BOM/StandardCost → Product.cost_price 자동 동기화 시그널 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='costsync_user', password='testpass123', role='staff',
        )
        self.finished = Product.objects.create(
            code='CS-FP-001', name='원가동기화제품',
            product_type='FINISHED', unit_price=50000,
            cost_price=0, created_by=self.user,
        )
        self.raw1 = Product.objects.create(
            code='CS-RM-001', name='원가동기화원자재1',
            product_type='RAW', cost_price=5000,
            created_by=self.user,
        )
        self.raw2 = Product.objects.create(
            code='CS-RM-002', name='원가동기화원자재2',
            product_type='RAW', cost_price=3000,
            created_by=self.user,
        )

    def test_bom_item_save_syncs_cost_price(self):
        """BOMItem 저장 시 Product.cost_price가 BOM 자재원가로 갱신"""
        bom = BOM.objects.create(
            product=self.finished, version='1.0',
            is_default=True, created_by=self.user,
        )
        # BOMItem 추가: 2 * 5000 = 10000
        BOMItem.objects.create(
            bom=bom, material=self.raw1,
            quantity=Decimal('2.000'), loss_rate=Decimal('0'),
            created_by=self.user,
        )
        self.finished.refresh_from_db()
        self.assertEqual(self.finished.cost_price, 10000)

        # BOMItem 추가: 3 * 3000 = 9000, 합계 19000
        BOMItem.objects.create(
            bom=bom, material=self.raw2,
            quantity=Decimal('3.000'), loss_rate=Decimal('0'),
            created_by=self.user,
        )
        self.finished.refresh_from_db()
        self.assertEqual(self.finished.cost_price, 19000)

    def test_bom_item_delete_syncs_cost_price(self):
        """BOMItem 삭제 시 cost_price 재계산"""
        bom = BOM.objects.create(
            product=self.finished, version='1.0',
            is_default=True, created_by=self.user,
        )
        item1 = BOMItem.objects.create(
            bom=bom, material=self.raw1,
            quantity=Decimal('2.000'), loss_rate=Decimal('0'),
            created_by=self.user,
        )
        BOMItem.objects.create(
            bom=bom, material=self.raw2,
            quantity=Decimal('3.000'), loss_rate=Decimal('0'),
            created_by=self.user,
        )
        self.finished.refresh_from_db()
        self.assertEqual(self.finished.cost_price, 19000)

        # item1 삭제 → 남은 자재원가: 3 * 3000 = 9000
        item1.delete()
        self.finished.refresh_from_db()
        self.assertEqual(self.finished.cost_price, 9000)

    def test_standard_cost_overrides_bom(self):
        """StandardCost 등록 시 BOM보다 우선"""
        from apps.production.models import StandardCost

        bom = BOM.objects.create(
            product=self.finished, version='1.0',
            is_default=True, created_by=self.user,
        )
        BOMItem.objects.create(
            bom=bom, material=self.raw1,
            quantity=Decimal('2.000'), loss_rate=Decimal('0'),
            created_by=self.user,
        )
        self.finished.refresh_from_db()
        self.assertEqual(self.finished.cost_price, 10000)

        # StandardCost 등록 → BOM 원가(10000)보다 우선
        StandardCost.objects.create(
            product=self.finished,
            version='1.0',
            effective_date=date.today(),
            material_cost=10000,
            direct_labor_hours=Decimal('1.00'),
            labor_rate_per_hour=5000,
            overhead_rate=Decimal('20.00'),
            is_current=True,
            created_by=self.user,
        )
        # 합계: 10000 + 5000 + 1000 = 16000
        self.finished.refresh_from_db()
        self.assertEqual(self.finished.cost_price, 16000)

    def test_no_bom_no_stdcost_keeps_manual(self):
        """BOM/StandardCost 없으면 기존 수동 설정값 유지"""
        Product.objects.filter(pk=self.finished.pk).update(cost_price=25000)
        self.finished.refresh_from_db()
        self.assertEqual(self.finished.cost_price, 25000)

        # 기본이 아닌 BOM 생성 → cost_price 변경 없어야 함
        bom = BOM.objects.create(
            product=self.finished, version='1.0',
            is_default=False, created_by=self.user,
        )
        BOMItem.objects.create(
            bom=bom, material=self.raw1,
            quantity=Decimal('2.000'), loss_rate=Decimal('0'),
            created_by=self.user,
        )
        self.finished.refresh_from_db()
        self.assertEqual(self.finished.cost_price, 25000)

    def test_bom_default_change_syncs(self):
        """BOM is_default 변경 시 cost_price 동기화"""
        bom = BOM.objects.create(
            product=self.finished, version='1.0',
            is_default=False, created_by=self.user,
        )
        BOMItem.objects.create(
            bom=bom, material=self.raw1,
            quantity=Decimal('2.000'), loss_rate=Decimal('0'),
            created_by=self.user,
        )
        # 기본BOM이 아니므로 cost_price 변경 없음
        self.finished.refresh_from_db()
        self.assertEqual(self.finished.cost_price, 0)

        # is_default를 True로 변경 → cost_price 동기화
        bom.is_default = True
        bom.save()
        self.finished.refresh_from_db()
        self.assertEqual(self.finished.cost_price, 10000)


class BOMMultiLevelTest(TestCase):
    """BOM 다단계 전개 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='bom_ml_user', password='testpass123', role='staff',
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-ML', name='다단계창고', is_default=True, created_by=self.user,
        )
        # 원자재
        self.raw_a = Product.objects.create(
            code='RAW-MLA', name='원자재A', product_type='RAW',
            cost_price=1000, current_stock=100, created_by=self.user,
        )
        self.raw_b = Product.objects.create(
            code='RAW-MLB', name='원자재B', product_type='RAW',
            cost_price=2000, current_stock=100, created_by=self.user,
        )
        # 반제품
        self.semi = Product.objects.create(
            code='ASM-ML1', name='반제품1', product_type='SEMI',
            cost_price=5000, current_stock=50, created_by=self.user,
        )
        # 완제품
        self.finished = Product.objects.create(
            code='FIN-ML1', name='완제품1', product_type='FINISHED',
            cost_price=0, current_stock=0, created_by=self.user,
        )
        # 반제품 BOM: 원자재A x2, 원자재B x1
        self.semi_bom = BOM.objects.create(
            product=self.semi, version='1.0', is_default=True, created_by=self.user,
        )
        BOMItem.objects.create(
            bom=self.semi_bom, material=self.raw_a,
            quantity=Decimal('2.000'), loss_rate=Decimal('0'),
            created_by=self.user,
        )
        BOMItem.objects.create(
            bom=self.semi_bom, material=self.raw_b,
            quantity=Decimal('1.000'), loss_rate=Decimal('0'),
            created_by=self.user,
        )
        # 완제품 BOM: 반제품 x1, 원자재B x3
        self.fin_bom = BOM.objects.create(
            product=self.finished, version='1.0', is_default=True, created_by=self.user,
        )
        BOMItem.objects.create(
            bom=self.fin_bom, material=self.semi,
            quantity=Decimal('1.000'), loss_rate=Decimal('0'),
            created_by=self.user,
        )
        BOMItem.objects.create(
            bom=self.fin_bom, material=self.raw_b,
            quantity=Decimal('3.000'), loss_rate=Decimal('0'),
            created_by=self.user,
        )

    def test_explode_multilevel(self):
        """다단계 전개 시 반제품이 원자재로 분해되어야 한다"""
        result = self.fin_bom.explode_multilevel(quantity=1)
        # 레벨0: 반제품(is_leaf=False), 원자재B(is_leaf=True)
        # 레벨1: 원자재A(is_leaf=True), 원자재B(is_leaf=True)
        self.assertEqual(len(result), 4)

        # 반제품 항목 (is_leaf=False)
        semi_items = [r for r in result if not r['is_leaf']]
        self.assertEqual(len(semi_items), 1)
        self.assertEqual(semi_items[0]['material'], self.semi)
        self.assertEqual(semi_items[0]['level'], 0)

        # 최말단 원자재 항목들 (is_leaf=True)
        leaf_items = [r for r in result if r['is_leaf']]
        self.assertEqual(len(leaf_items), 3)

    def test_explode_multilevel_quantity(self):
        """수량 10개 전개 시 소요량이 정확해야 한다"""
        result = self.fin_bom.explode_multilevel(quantity=10)
        leaf_items = [r for r in result if r['is_leaf']]

        # 원자재A: 반제품 1개당 2개 x 완제품 10개 = 20
        raw_a_items = [r for r in leaf_items if r['material'] == self.raw_a]
        self.assertEqual(len(raw_a_items), 1)
        self.assertEqual(raw_a_items[0]['quantity'], Decimal('20'))

        # 원자재B: 반제품 1개당 1개 + 완제품 직접 3개 = (1*10 + 3*10) = 10 + 30
        raw_b_items = [r for r in leaf_items if r['material'] == self.raw_b]
        total_b = sum(r['quantity'] for r in raw_b_items)
        self.assertEqual(total_b, Decimal('40'))

    def test_max_depth_prevents_infinite(self):
        """max_depth 제한이 무한루프를 방지해야 한다"""
        result = self.fin_bom.explode_multilevel(quantity=1, max_depth=0)
        self.assertEqual(len(result), 0)

        result = self.fin_bom.explode_multilevel(quantity=1, max_depth=1)
        # 레벨0만 전개: 반제품(is_leaf=False이지만 하위 전개 안됨)과 원자재B
        # max_depth=1이면 level=0은 처리하되 level=1은 진입 불가
        # 반제품은 sub_bom이 있지만 level+1=1 >= max_depth=1이므로 하위 비전개
        # 그래도 반제품은 결과에 is_leaf=False로 포함되고, 하위 전개만 안됨
        self.assertEqual(len(result), 2)


class ScrapHandlingTest(TestCase):
    """불량품 재고 자동 차감 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='scrap_user', password='testpass123', role='staff',
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-SC', name='스크랩창고', is_default=True, created_by=self.user,
        )
        self.raw = Product.objects.create(
            code='RAW-SC1', name='스크랩원자재', product_type='RAW',
            cost_price=1000, current_stock=100, created_by=self.user,
        )
        self.finished = Product.objects.create(
            code='FIN-SC1', name='스크랩완제품', product_type='FINISHED',
            cost_price=5000, current_stock=0, created_by=self.user,
        )
        self.bom = BOM.objects.create(
            product=self.finished, version='1.0', is_default=True, created_by=self.user,
        )
        BOMItem.objects.create(
            bom=self.bom, material=self.raw,
            quantity=Decimal('2.000'), loss_rate=Decimal('0'),
            created_by=self.user,
        )
        self.plan = ProductionPlan.objects.create(
            product=self.finished, bom=self.bom,
            planned_quantity=20, planned_start=date.today(),
            planned_end=date.today() + timedelta(days=7),
            status='CONFIRMED', created_by=self.user,
        )
        self.wo = WorkOrder.objects.create(
            production_plan=self.plan, quantity=20,
            status='IN_PROGRESS', created_by=self.user,
        )

    def test_scrap_does_not_create_finished_adjustment(self):
        """불량은 완제품 입고에 포함되지 않으므로 별도 차감이 없어야 한다"""
        record = ProductionRecord.objects.create(
            work_order=self.wo, good_quantity=8, defect_quantity=2,
            record_date=date.today(), warehouse=self.warehouse,
            created_by=self.user,
        )
        # PROD_IN은 양품만 (8개)
        prod_in = StockMovement.objects.filter(
            movement_type='PROD_IN', product=self.finished, is_active=True,
        )
        self.assertEqual(prod_in.count(), 1)
        self.assertEqual(prod_in.first().quantity, Decimal('8'))

    def test_scrap_material_consumption(self):
        """불량 포함 총생산수량 기준으로 원자재 소모되어야 한다"""
        record = ProductionRecord.objects.create(
            work_order=self.wo, good_quantity=8, defect_quantity=2,
            record_date=date.today(), warehouse=self.warehouse,
            created_by=self.user,
        )
        # 원자재 소모: (양품8 + 불량2) x BOM소요량2 = 20
        prod_out = StockMovement.objects.filter(
            movement_type='PROD_OUT',
            product=self.raw,
            is_active=True,
        )
        self.assertEqual(prod_out.count(), 1)
        self.assertEqual(prod_out.first().quantity, Decimal('20'))

    def test_no_defect_only_good_quantity_in_prod_in(self):
        """불량 수량 0이면 PROD_IN에 양품만 반영되어야 한다"""
        record = ProductionRecord.objects.create(
            work_order=self.wo, good_quantity=10, defect_quantity=0,
            record_date=date.today(), warehouse=self.warehouse,
            created_by=self.user,
        )
        prod_in = StockMovement.objects.filter(
            movement_type='PROD_IN', product=self.finished, is_active=True,
        )
        self.assertEqual(prod_in.count(), 1)
        self.assertEqual(prod_in.first().quantity, Decimal('10'))

        # 원자재 소모: 양품 10 x BOM소요량 2 = 20
        prod_out = StockMovement.objects.filter(
            movement_type='PROD_OUT', product=self.raw, is_active=True,
        )
        self.assertEqual(prod_out.count(), 1)
        self.assertEqual(prod_out.first().quantity, Decimal('20'))


class ConditionalApprovalTest(TestCase):
    """조건부합격 후속 처리 테스트"""

    def setUp(self):
        from apps.production.models import QualityInspection
        self.user = User.objects.create_user(
            username='qc_user', password='testpass123', role='staff',
        )
        self.manager = User.objects.create_user(
            username='qc_manager', password='testpass123', role='manager',
        )
        self.product = Product.objects.create(
            code='QC-001', name='검수제품',
            product_type='FINISHED', unit_price=10000, cost_price=5000,
            created_by=self.user,
        )
        self.inspection = QualityInspection.objects.create(
            inspection_type='PRODUCTION',
            product=self.product,
            inspected_quantity=100,
            pass_quantity=90,
            fail_quantity=10,
            inspection_date=date.today(),
            result='CONDITIONAL',
            conditional_notes='표면 미세 스크래치 — 사용 가능 판단 필요',
            inspector=self.user,
            created_by=self.user,
        )

    def test_conditional_fields_saved(self):
        """조건부합격 필드가 정상 저장되는지 확인"""
        from apps.production.models import QualityInspection
        insp = QualityInspection.objects.get(pk=self.inspection.pk)
        self.assertEqual(insp.result, 'CONDITIONAL')
        self.assertEqual(insp.conditional_notes, '표면 미세 스크래치 — 사용 가능 판단 필요')
        self.assertIsNone(insp.conditional_approved_by)
        self.assertIsNone(insp.conditional_approved_at)

    def test_conditional_notification_created(self):
        """조건부합격 등록 시 매니저에게 알림이 생성되는지 확인"""
        from apps.core.notification import Notification
        notis = Notification.objects.filter(
            user=self.manager,
            noti_type='PRODUCTION',
            title__contains=self.inspection.inspection_number,
        )
        self.assertTrue(notis.exists())
        self.assertIn('조건부합격 승인 요청', notis.first().title)

    def test_conditional_approve(self):
        """조건부합격 승인 시 PASS로 전환"""
        from django.utils import timezone
        from apps.production.models import QualityInspection
        insp = self.inspection
        insp.result = QualityInspection.Result.PASS
        insp.conditional_approved_by = self.manager
        insp.conditional_approved_at = timezone.now()
        insp.save(update_fields=[
            'result', 'conditional_approved_by',
            'conditional_approved_at', 'updated_at',
        ])
        insp.refresh_from_db()
        self.assertEqual(insp.result, 'PASS')
        self.assertEqual(insp.conditional_approved_by, self.manager)
        self.assertIsNotNone(insp.conditional_approved_at)

    def test_conditional_reject(self):
        """조건부합격 반려 시 FAIL로 전환"""
        from django.utils import timezone
        from apps.production.models import QualityInspection
        insp = self.inspection
        insp.result = QualityInspection.Result.FAIL
        insp.conditional_approved_by = self.manager
        insp.conditional_approved_at = timezone.now()
        insp.save(update_fields=[
            'result', 'conditional_approved_by',
            'conditional_approved_at', 'updated_at',
        ])
        insp.refresh_from_db()
        self.assertEqual(insp.result, 'FAIL')
        self.assertEqual(insp.conditional_approved_by, self.manager)

    def test_approve_view_requires_manager(self):
        """ConditionalApproveView는 매니저 이상만 접근 가능"""
        self.client.force_login(self.user)
        url = f'/production/qc/{self.inspection.inspection_number}/conditional-approve/'
        resp = self.client.post(url, {'action': 'approve'})
        # staff는 접근 불가 (redirect to login or 403)
        self.assertIn(resp.status_code, [302, 403])

    def test_approve_view_manager_approve(self):
        """매니저가 승인 시 PASS 전환"""
        self.client.force_login(self.manager)
        url = f'/production/qc/{self.inspection.inspection_number}/conditional-approve/'
        resp = self.client.post(url, {'action': 'approve'})
        self.assertEqual(resp.status_code, 302)
        self.inspection.refresh_from_db()
        self.assertEqual(self.inspection.result, 'PASS')
        self.assertEqual(self.inspection.conditional_approved_by, self.manager)

    def test_approve_view_manager_reject(self):
        """매니저가 반려 시 FAIL 전환"""
        self.client.force_login(self.manager)
        url = f'/production/qc/{self.inspection.inspection_number}/conditional-approve/'
        resp = self.client.post(url, {'action': 'reject'})
        self.assertEqual(resp.status_code, 302)
        self.inspection.refresh_from_db()
        self.assertEqual(self.inspection.result, 'FAIL')

    def test_non_conditional_cannot_be_approved(self):
        """CONDITIONAL이 아닌 검수는 승인 불가"""
        self.inspection.result = 'PASS'
        self.inspection.save(update_fields=['result', 'updated_at'])
        self.client.force_login(self.manager)
        url = f'/production/qc/{self.inspection.inspection_number}/conditional-approve/'
        resp = self.client.post(url, {'action': 'approve'})
        self.assertEqual(resp.status_code, 302)
        self.inspection.refresh_from_db()
        self.assertEqual(self.inspection.result, 'PASS')  # 변경되지 않음


# ============================================================
# ProductionBatch (추적 관리 3계층) 테스트
# ============================================================

class ProductionBatchTest(TestCase):
    """ProductionBatch 자동 생성 + LOT/시리얼 연결 + Forward/Backward trace 검증"""

    def setUp(self):
        from apps.production.models import WorkCenter
        self.user = User.objects.create_user(
            username='batch_user', password='testpass123', role='staff',
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-BATCH', name='배치테스트창고', created_by=self.user,
        )
        self.work_center = WorkCenter.objects.create(
            code='WC01', name='배치테스트작업장', created_by=self.user,
        )
        self.finished = Product.objects.create(
            code='FP-BATCH', name='배치완제품', product_type='FINISHED',
            unit_price=10000, cost_price=5000, current_stock=0,
            serial_tracking=True, serial_prefix='BT',
            created_by=self.user,
        )
        self.raw = Product.objects.create(
            code='RM-BATCH', name='배치원자재', product_type='RAW',
            unit_price=0, cost_price=1000, current_stock=1000,
            created_by=self.user,
        )
        self.bom = BOM.objects.create(
            product=self.finished, version='1.0', is_default=True,
            created_by=self.user,
        )
        BOMItem.objects.create(
            bom=self.bom, material=self.raw,
            quantity=Decimal('2.000'), loss_rate=Decimal('0.00'),
            created_by=self.user,
        )
        self.plan = ProductionPlan.objects.create(
            plan_number='PP-BATCH', product=self.finished, bom=self.bom,
            planned_quantity=10, planned_start=date.today(),
            planned_end=date.today() + timedelta(days=1),
            status='IN_PROGRESS', created_by=self.user,
        )
        self.wo = WorkOrder.objects.create(
            order_number='WO-BATCH', production_plan=self.plan,
            work_center=self.work_center, quantity=10,
            status='IN_PROGRESS', created_by=self.user,
        )

    def test_batch_auto_created_on_production_record(self):
        """ProductionRecord 생성 시 ProductionBatch가 자동으로 생성된다"""
        from apps.production.models import ProductionBatch
        record = ProductionRecord.objects.create(
            work_order=self.wo, warehouse=self.warehouse,
            good_quantity=5, record_date=date.today(),
            created_by=self.user,
        )
        batch = ProductionBatch.objects.filter(production_record=record).first()
        self.assertIsNotNone(batch)
        self.assertEqual(batch.product, self.finished)
        self.assertEqual(batch.work_center, self.work_center)
        self.assertEqual(batch.total_quantity, Decimal('5'))
        self.assertEqual(batch.remaining_quantity, Decimal('5'))

    def test_batch_number_format(self):
        """배치번호 형식: {WC.code}-{YYYYMMDD}-{SHIFT}-{SEQ:03d}"""
        from apps.production.models import ProductionBatch
        today = date.today()
        record = ProductionRecord.objects.create(
            work_order=self.wo, warehouse=self.warehouse,
            good_quantity=3, record_date=today,
            created_by=self.user,
        )
        batch = ProductionBatch.objects.get(production_record=record)
        expected_prefix = f'WC01-{today.strftime("%Y%m%d")}-A-'
        self.assertTrue(
            batch.batch_number.startswith(expected_prefix),
            f'expected prefix {expected_prefix}, got {batch.batch_number}',
        )
        self.assertTrue(batch.batch_number.endswith('-001'))

    def test_same_line_date_shift_sequence_increments(self):
        """동일 (작업장, 일자, 시프트) 내 2건 이상 생산 시 sequence 자동증가"""
        from apps.production.models import ProductionBatch
        today = date.today()
        r1 = ProductionRecord.objects.create(
            work_order=self.wo, warehouse=self.warehouse,
            good_quantity=2, record_date=today,
            created_by=self.user,
        )
        wo2 = WorkOrder.objects.create(
            order_number='WO-BATCH-2', production_plan=self.plan,
            work_center=self.work_center, quantity=3,
            status='IN_PROGRESS', created_by=self.user,
        )
        r2 = ProductionRecord.objects.create(
            work_order=wo2, warehouse=self.warehouse,
            good_quantity=3, record_date=today,
            created_by=self.user,
        )
        b1 = ProductionBatch.objects.get(production_record=r1)
        b2 = ProductionBatch.objects.get(production_record=r2)
        self.assertEqual(b1.sequence, 1)
        self.assertEqual(b2.sequence, 2)
        self.assertTrue(b1.batch_number.endswith('-001'))
        self.assertTrue(b2.batch_number.endswith('-002'))

    def test_batch_linked_to_stock_lot(self):
        """PROD_IN → StockLot 자동생성 시 production_batch FK 연결"""
        from apps.inventory.models import StockLot
        record = ProductionRecord.objects.create(
            work_order=self.wo, warehouse=self.warehouse,
            good_quantity=5, record_date=date.today(),
            created_by=self.user,
        )
        lots = StockLot.objects.filter(
            product=self.finished, is_active=True,
        )
        self.assertTrue(lots.exists())
        self.assertTrue(all(lot.production_batch_id for lot in lots))
        self.assertEqual(lots.first().production_batch.production_record, record)

    def test_batch_linked_to_serial_numbers(self):
        """시리얼 추적 제품: 생산 시 생성된 SerialNumber에 production_batch FK 연결"""
        from apps.inventory.models import SerialNumber
        record = ProductionRecord.objects.create(
            work_order=self.wo, warehouse=self.warehouse,
            good_quantity=5, record_date=date.today(),
            created_by=self.user,
        )
        serials = SerialNumber.objects.filter(production_record=record)
        self.assertEqual(serials.count(), 5)
        self.assertTrue(all(sn.production_batch_id for sn in serials))

    def test_batch_remaining_depletes_on_out(self):
        """OUT 발생 시 FIFO로 ProductionBatch.remaining_quantity 감소"""
        from apps.production.models import ProductionBatch
        record = ProductionRecord.objects.create(
            work_order=self.wo, warehouse=self.warehouse,
            good_quantity=10, record_date=date.today(),
            created_by=self.user,
        )
        batch = ProductionBatch.objects.get(production_record=record)
        self.assertEqual(batch.remaining_quantity, Decimal('10'))

        # 4개 출고
        StockMovement.objects.create(
            movement_type='OUT', product=self.finished,
            warehouse=self.warehouse, quantity=Decimal('4'),
            unit_price=10000, movement_date=date.today(),
            created_by=self.user,
        )
        batch.refresh_from_db()
        self.assertEqual(batch.remaining_quantity, Decimal('6'))


class TraceabilityViewTest(TestCase):
    """추적 관리 4탭 뷰 접근성 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='trace_viewer', password='testpass123', role='staff',
        )
        self.client.force_login(self.user)

    def test_batch_list_accessible(self):
        resp = self.client.get('/production/trace/')
        self.assertEqual(resp.status_code, 200)

    def test_lot_list_accessible(self):
        resp = self.client.get('/production/trace/lots/')
        self.assertEqual(resp.status_code, 200)

    def test_serial_list_accessible(self):
        resp = self.client.get('/production/trace/serials/')
        self.assertEqual(resp.status_code, 200)

    def test_backward_accessible(self):
        resp = self.client.get('/production/trace/backward/')
        self.assertEqual(resp.status_code, 200)

    def test_backward_with_serial_query(self):
        resp = self.client.get('/production/trace/backward/', {'serial': 'BT'})
        self.assertEqual(resp.status_code, 200)
