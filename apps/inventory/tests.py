from decimal import Decimal
from datetime import date

from django.test import TestCase

from apps.accounts.models import User
from apps.inventory.models import (
    Product, Category, Warehouse, StockMovement,
)


class StockMovementSignalTest(TestCase):
    """입출고 시그널 테스트 — StockMovement 생성/삭제 시 Product.current_stock 자동 갱신 검증"""

    def setUp(self):
        """테스트에 필요한 사용자, 창고, 제품 생성"""
        self.user = User.objects.create_user(
            username='testuser', password='testpass123', role='staff',
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-001', name='메인창고', created_by=self.user,
        )
        self.product = Product.objects.create(
            code='PRD-001',
            name='테스트 제품',
            product_type='FINISHED',
            unit_price=10000,
            cost_price=7000,
            safety_stock=10,
            current_stock=0,
            created_by=self.user,
        )
        self._movement_seq = 0

    def _create_movement(self, movement_type, quantity, product=None):
        """StockMovement 헬퍼 — 고유 전표번호 자동 생성"""
        self._movement_seq += 1
        return StockMovement.objects.create(
            movement_number=f'MOV-{self._movement_seq:04d}',
            movement_type=movement_type,
            product=product or self.product,
            warehouse=self.warehouse,
            quantity=quantity,
            unit_price=1000,
            movement_date=date.today(),
            created_by=self.user,
        )

    def _refresh_product(self, product=None):
        """DB에서 제품 정보를 다시 읽어온다 (F() 표현식 갱신 반영)"""
        p = product or self.product
        p.refresh_from_db()
        return p

    # ── 입고 테스트 ──────────────────────────────────────────

    def test_inbound_increases_stock(self):
        """IN 타입 입고 시 재고가 증가하는지 확인"""
        self._create_movement('IN', 50)
        self._refresh_product()
        self.assertEqual(self.product.current_stock, 50)

    def test_all_inbound_types(self):
        """ADJ_PLUS, PROD_IN, RETURN 타입 모두 재고가 증가하는지 확인"""
        for i, mtype in enumerate(['ADJ_PLUS', 'PROD_IN', 'RETURN']):
            product = Product.objects.create(
                code=f'PRD-IN-{i}',
                name=f'입고테스트-{mtype}',
                product_type='FINISHED',
                unit_price=1000,
                cost_price=500,
                current_stock=0,
                created_by=self.user,
            )
            self._create_movement(mtype, 10, product=product)
            product.refresh_from_db()
            self.assertEqual(
                product.current_stock, 10,
                f'{mtype} 타입 입고 후 재고가 10이어야 합니다',
            )

    # ── 출고 테스트 ──────────────────────────────────────────

    def test_outbound_decreases_stock(self):
        """OUT 타입 출고 시 재고가 감소하는지 확인"""
        self._create_movement('IN', 100)
        self._create_movement('OUT', 30)
        self._refresh_product()
        self.assertEqual(self.product.current_stock, 70)

    def test_all_outbound_types(self):
        """ADJ_MINUS, PROD_OUT 타입 모두 재고가 감소하는지 확인"""
        for i, mtype in enumerate(['ADJ_MINUS', 'PROD_OUT']):
            product = Product.objects.create(
                code=f'PRD-OUT-{i}',
                name=f'출고테스트-{mtype}',
                product_type='FINISHED',
                unit_price=1000,
                cost_price=500,
                current_stock=100,
                created_by=self.user,
            )
            self._create_movement(mtype, 25, product=product)
            product.refresh_from_db()
            self.assertEqual(
                product.current_stock, 75,
                f'{mtype} 타입 출고 후 재고가 75이어야 합니다',
            )

    # ── 삭제 복원 테스트 ─────────────────────────────────────

    def test_delete_inbound_reverses_stock(self):
        """입고 전표 삭제 시 증가분이 복원되는지 확인"""
        movement = self._create_movement('IN', 40)
        self._refresh_product()
        self.assertEqual(self.product.current_stock, 40)

        movement.delete()
        self._refresh_product()
        self.assertEqual(self.product.current_stock, 0)

    def test_delete_outbound_reverses_stock(self):
        """출고 전표 삭제 시 감소분이 복원되는지 확인"""
        self._create_movement('IN', 100)
        out_movement = self._create_movement('OUT', 30)
        self._refresh_product()
        self.assertEqual(self.product.current_stock, 70)

        out_movement.delete()
        self._refresh_product()
        self.assertEqual(self.product.current_stock, 100)

    # ── 누적/동시 테스트 ─────────────────────────────────────

    def test_multiple_movements_accumulate(self):
        """여러 입출고 전표가 누적되어 재고에 반영되는지 확인"""
        self._create_movement('IN', 100)
        self._create_movement('IN', 50)
        self._create_movement('OUT', 30)
        self._create_movement('ADJ_PLUS', 10)
        self._create_movement('ADJ_MINUS', 5)
        self._refresh_product()
        # 100 + 50 - 30 + 10 - 5 = 125
        self.assertEqual(self.product.current_stock, 125)

    def test_concurrent_movements(self):
        """다수의 입출고를 연속 생성한 뒤 최종 재고가 정확한지 확인"""
        for _ in range(10):
            self._create_movement('IN', 5)
        for _ in range(3):
            self._create_movement('OUT', 10)
        self._refresh_product()
        # (10 * 5) - (3 * 10) = 50 - 30 = 20
        self.assertEqual(self.product.current_stock, 20)

    # ── Product 프로퍼티 테스트 ──────────────────────────────

    def test_product_is_below_safety_stock(self):
        """현재고가 안전재고 미만일 때 is_below_safety_stock이 True인지 확인"""
        # safety_stock=10, current_stock=0
        self.assertTrue(self.product.is_below_safety_stock)

        self._create_movement('IN', 15)
        self._refresh_product()
        self.assertFalse(self.product.is_below_safety_stock)

    def test_product_shortage(self):
        """부족량(shortage) 계산이 정확한지 확인"""
        # safety_stock=10, current_stock=0 → shortage=10
        self.assertEqual(self.product.shortage, 10)

        self._create_movement('IN', 6)
        self._refresh_product()
        self.assertEqual(self.product.shortage, 4)

        self._create_movement('IN', 10)
        self._refresh_product()
        self.assertEqual(self.product.shortage, 0)

    def test_product_profit_margin(self):
        """이익률(profit_margin) 계산이 정확한지 확인"""
        # unit_price=10000, cost_price=7000 → (10000-7000)/10000*100 = 30.0
        self.assertEqual(self.product.profit_margin, 30.0)

    def test_product_profit_margin_zero_price(self):
        """판매단가가 0일 때 이익률이 0인지 확인"""
        product = Product.objects.create(
            code='PRD-ZERO',
            name='단가0제품',
            product_type='FINISHED',
            unit_price=0,
            cost_price=0,
            created_by=self.user,
        )
        self.assertEqual(product.profit_margin, 0)


class CategoryModelTest(TestCase):
    """카테고리 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='catuser', password='testpass123', role='staff',
        )

    def test_category_creation(self):
        """카테고리 생성"""
        cat = Category.objects.create(
            name='전자부품', created_by=self.user,
        )
        self.assertEqual(cat.name, '전자부품')

    def test_category_str(self):
        """카테고리 문자열 표현"""
        cat = Category.objects.create(
            name='기계부품', created_by=self.user,
        )
        self.assertEqual(str(cat), '기계부품')

    def test_category_hierarchy(self):
        """카테고리 상하위 관계"""
        parent = Category.objects.create(
            name='원자재', created_by=self.user,
        )
        child = Category.objects.create(
            name='금속', parent=parent, created_by=self.user,
        )
        self.assertEqual(child.parent, parent)
        self.assertIn(child, parent.children.all())

    def test_category_ordering(self):
        """카테고리는 이름순 정렬"""
        Category.objects.create(name='ZZZ', created_by=self.user)
        Category.objects.create(name='AAA', created_by=self.user)
        cats = list(Category.objects.all())
        self.assertEqual(cats[0].name, 'AAA')

    def test_category_soft_delete(self):
        """카테고리 soft delete"""
        cat = Category.objects.create(
            name='삭제테스트', created_by=self.user,
        )
        cat.soft_delete()
        self.assertFalse(Category.objects.filter(pk=cat.pk).exists())
        self.assertTrue(Category.all_objects.filter(pk=cat.pk).exists())


class WarehouseModelTest(TestCase):
    """창고 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='whuser', password='testpass123', role='staff',
        )

    def test_warehouse_creation(self):
        """창고 생성"""
        wh = Warehouse.objects.create(
            code='WH-TEST', name='테스트창고',
            location='서울시 강남구', created_by=self.user,
        )
        self.assertEqual(wh.code, 'WH-TEST')
        self.assertEqual(wh.name, '테스트창고')

    def test_warehouse_str(self):
        """창고 문자열 표현"""
        wh = Warehouse.objects.create(
            code='WH-STR', name='문자열창고', created_by=self.user,
        )
        self.assertEqual(str(wh), '문자열창고')

    def test_warehouse_unique_code(self):
        """창고코드 중복 불가"""
        from django.db import IntegrityError
        Warehouse.objects.create(
            code='WH-DUP', name='창고1', created_by=self.user,
        )
        with self.assertRaises(IntegrityError):
            Warehouse.objects.create(
                code='WH-DUP', name='창고2', created_by=self.user,
            )


class StockTransferModelTest(TestCase):
    """창고간 이동 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='tfuser', password='testpass123', role='staff',
        )
        self.wh1 = Warehouse.objects.create(
            code='WH-FROM', name='출발창고', created_by=self.user,
        )
        self.wh2 = Warehouse.objects.create(
            code='WH-TO', name='도착창고', created_by=self.user,
        )
        self.product = Product.objects.create(
            code='TF-PRD-001', name='이동제품',
            product_type='FINISHED', unit_price=1000, cost_price=500,
            current_stock=100, created_by=self.user,
        )

    def test_transfer_creation(self):
        """창고간 이동 생성"""
        from apps.inventory.models import StockTransfer
        transfer = StockTransfer.objects.create(
            transfer_number='TF-001',
            from_warehouse=self.wh1,
            to_warehouse=self.wh2,
            product=self.product,
            quantity=50,
            transfer_date=date.today(),
            created_by=self.user,
        )
        self.assertEqual(transfer.from_warehouse, self.wh1)
        self.assertEqual(transfer.to_warehouse, self.wh2)
        self.assertEqual(transfer.quantity, 50)

    def test_transfer_str(self):
        """창고간 이동 문자열 표현"""
        from apps.inventory.models import StockTransfer
        transfer = StockTransfer.objects.create(
            transfer_number='TF-STR-001',
            from_warehouse=self.wh1,
            to_warehouse=self.wh2,
            product=self.product,
            quantity=10,
            transfer_date=date.today(),
            created_by=self.user,
        )
        self.assertEqual(str(transfer), 'TF-STR-001')

    def test_transfer_unique_number(self):
        """이동번호 중복 불가"""
        from django.db import IntegrityError
        from apps.inventory.models import StockTransfer
        StockTransfer.objects.create(
            transfer_number='TF-DUP-001',
            from_warehouse=self.wh1,
            to_warehouse=self.wh2,
            product=self.product,
            quantity=10,
            transfer_date=date.today(),
            created_by=self.user,
        )
        with self.assertRaises(IntegrityError):
            StockTransfer.objects.create(
                transfer_number='TF-DUP-001',
                from_warehouse=self.wh2,
                to_warehouse=self.wh1,
                product=self.product,
                quantity=5,
                transfer_date=date.today(),
                created_by=self.user,
            )

    def test_transfer_soft_delete(self):
        """창고간 이동 soft delete"""
        from apps.inventory.models import StockTransfer
        transfer = StockTransfer.objects.create(
            transfer_number='TF-SD-001',
            from_warehouse=self.wh1,
            to_warehouse=self.wh2,
            product=self.product,
            quantity=10,
            transfer_date=date.today(),
            created_by=self.user,
        )
        transfer.soft_delete()
        qs = StockTransfer.objects.filter(pk=transfer.pk)
        self.assertFalse(qs.exists())
        qs_all = StockTransfer.all_objects.filter(pk=transfer.pk)
        self.assertTrue(qs_all.exists())


class StockMovementModelTest(TestCase):
    """StockMovement 모델 자체 프로퍼티 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='smuser', password='testpass123', role='staff',
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-SM', name='프로퍼티창고', created_by=self.user,
        )
        self.product = Product.objects.create(
            code='SM-PRD-001', name='프로퍼티제품',
            product_type='FINISHED', unit_price=10000, cost_price=5000,
            current_stock=0, created_by=self.user,
        )

    def test_total_amount_property(self):
        """total_amount = quantity * unit_price"""
        movement = StockMovement.objects.create(
            movement_number='SM-AMT-001',
            movement_type='IN',
            product=self.product,
            warehouse=self.warehouse,
            quantity=10,
            unit_price=5000,
            movement_date=date.today(),
            created_by=self.user,
        )
        self.assertEqual(movement.total_amount, 50000)

    def test_stock_movement_str(self):
        """StockMovement 문자열 표현"""
        movement = StockMovement.objects.create(
            movement_number='SM-STR-001',
            movement_type='IN',
            product=self.product,
            warehouse=self.warehouse,
            quantity=10,
            unit_price=1000,
            movement_date=date.today(),
            created_by=self.user,
        )
        result = str(movement)
        self.assertIn('SM-STR-001', result)
        self.assertIn('입고', result)

    def test_product_type_choices(self):
        """제품 유형 선택지 확인"""
        choices = dict(Product.ProductType.choices)
        self.assertIn('RAW', choices)
        self.assertIn('SEMI', choices)
        self.assertIn('FINISHED', choices)
