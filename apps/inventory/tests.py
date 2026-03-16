from decimal import Decimal
from datetime import date

from django.test import TestCase

from apps.accounts.models import User
from apps.inventory.models import Product, Warehouse, StockMovement


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
