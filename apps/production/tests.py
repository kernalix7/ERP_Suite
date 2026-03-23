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
