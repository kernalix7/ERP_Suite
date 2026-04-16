from decimal import Decimal
from datetime import date, timedelta

from django.test import TestCase

from apps.accounts.models import User
from apps.inventory.models import (
    Product, Category, Warehouse, StockMovement, StockTransfer,
    WarehouseStock, SerialNumber,
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

    def _create_movement(self, movement_type, quantity, product=None,
                         unit_price=1000):
        """StockMovement 헬퍼 — 고유 전표번호 자동 생성"""
        self._movement_seq += 1
        return StockMovement.objects.create(
            movement_number=f'MOV-{self._movement_seq:04d}',
            movement_type=movement_type,
            product=product or self.product,
            warehouse=self.warehouse,
            quantity=quantity,
            unit_price=unit_price,
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

    # ── 이동평균단가 테스트 ──────────────────────────────────

    def test_weighted_avg_cost_single_receipt(self):
        """단일 입고 시 cost_price가 입고단가로 갱신"""
        # 기존 재고 0, cost_price 7000 → 입고 50개 @ 8000
        self._create_movement('IN', 50, unit_price=8000)
        self._refresh_product()
        # (0*7000 + 50*8000) / 50 = 8000
        self.assertEqual(self.product.cost_price, Decimal('8000'))

    def test_weighted_avg_cost_multiple_receipts(self):
        """서로 다른 단가로 여러 번 입고 시 가중평균 계산"""
        # 1차: 100개 @ 1000원
        self._create_movement('IN', 100, unit_price=1000)
        self._refresh_product()
        self.assertEqual(self.product.cost_price, Decimal('1000'))
        # 2차: 50개 @ 1600원
        # (100*1000 + 50*1600) / 150 = 180000/150 = 1200
        self._create_movement('IN', 50, unit_price=1600)
        self._refresh_product()
        self.assertEqual(self.product.cost_price, Decimal('1200'))

    def test_weighted_avg_cost_with_existing_stock(self):
        """기존 재고가 있는 상태에서 입고 시 가중평균"""
        # 기존 재고 100개 @ 7000원 (setUp의 cost_price)
        self.product.current_stock = 100
        self.product.save(update_fields=['current_stock'])
        # 입고 50개 @ 10000원
        # (100*7000 + 50*10000) / 150 = 1200000/150 = 8000
        self._create_movement('IN', 50, unit_price=10000)
        self._refresh_product()
        self.assertEqual(self.product.cost_price, Decimal('8000'))

    def test_weighted_avg_cost_out_does_not_change(self):
        """출고 시 cost_price는 변경되지 않음"""
        self._create_movement('IN', 100, unit_price=5000)
        self._refresh_product()
        cost_before = self.product.cost_price
        self._create_movement('OUT', 30, unit_price=5000)
        self._refresh_product()
        self.assertEqual(self.product.cost_price, cost_before)

    def test_weighted_avg_cost_return_does_not_change(self):
        """반품(RETURN) 입고 시 cost_price는 변경되지 않음"""
        self._create_movement('IN', 100, unit_price=5000)
        self._refresh_product()
        cost_before = self.product.cost_price
        self._create_movement('RETURN', 10, unit_price=5000)
        self._refresh_product()
        self.assertEqual(self.product.cost_price, cost_before)

    def test_weighted_avg_cost_zero_price_ignored(self):
        """unit_price=0인 입고는 원가 변경 없음"""
        self._create_movement('IN', 100, unit_price=5000)
        self._refresh_product()
        cost_before = self.product.cost_price
        self._create_movement('IN', 50, unit_price=0)
        self._refresh_product()
        self.assertEqual(self.product.cost_price, cost_before)

    def test_weighted_avg_cost_rounding(self):
        """이동평균단가 반올림 (KRW — 소수점 없음)"""
        # 재고 0 → 입고 3개 @ 1000원 → cost=1000
        self._create_movement('IN', 3, unit_price=1000)
        # 재고 3 → 입고 2개 @ 1100원
        # (3*1000 + 2*1100) / 5 = 5200/5 = 1040
        self._create_movement('IN', 2, unit_price=1100)
        self._refresh_product()
        self.assertEqual(self.product.cost_price, Decimal('1040'))

    def test_weighted_avg_cost_prod_in(self):
        """생산입고(PROD_IN)도 이동평균 적용"""
        self.product.current_stock = 100
        self.product.cost_price = Decimal('5000')
        self.product.save(update_fields=['current_stock', 'cost_price'])
        # 생산입고 50개 @ 4000원
        # (100*5000 + 50*4000) / 150 = 700000/150 ≈ 4667
        self._create_movement('PROD_IN', 50, unit_price=4000)
        self._refresh_product()
        self.assertEqual(self.product.cost_price, Decimal('4667'))

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
            code='CAT-ELC', name='전자부품', created_by=self.user,
        )
        self.assertEqual(cat.name, '전자부품')
        self.assertEqual(cat.code, 'CAT-ELC')

    def test_category_str(self):
        """카테고리 문자열 표현"""
        cat = Category.objects.create(
            code='CAT-MCH', name='기계부품', created_by=self.user,
        )
        self.assertEqual(str(cat), '[CAT-MCH] 기계부품')

    def test_category_hierarchy(self):
        """카테고리 상하위 관계"""
        parent = Category.objects.create(
            code='CAT-RAW', name='원자재', created_by=self.user,
        )
        child = Category.objects.create(
            code='CAT-MTL', name='금속', parent=parent, created_by=self.user,
        )
        self.assertEqual(child.parent, parent)
        self.assertIn(child, parent.children.all())

    def test_category_ordering(self):
        """카테고리는 코드순 정렬"""
        Category.objects.create(code='CAT-ZZZ', name='ZZZ', created_by=self.user)
        Category.objects.create(code='CAT-AAA', name='AAA', created_by=self.user)
        cats = list(Category.objects.all())
        self.assertEqual(cats[0].code, 'CAT-AAA')

    def test_category_soft_delete(self):
        """카테고리 soft delete"""
        cat = Category.objects.create(
            code='CAT-DEL', name='삭제테스트', created_by=self.user,
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
        # 출발창고 재고 설정 (창고이동 검증용)
        WarehouseStock.objects.create(
            warehouse=self.wh1, product=self.product,
            quantity=100, created_by=self.user,
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


class StockLotTest(TestCase):
    """FIFO/LIFO 재고평가 LOT 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='lotuser', password='testpass123', role='staff',
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-LOT', name='LOT창고', created_by=self.user,
        )
        self.product = Product.objects.create(
            code='LOT-PRD-001',
            name='LOT테스트제품',
            product_type='FINISHED',
            unit_price=10000,
            cost_price=5000,
            current_stock=0,
            valuation_method='FIFO',
            created_by=self.user,
        )
        self._movement_seq = 0

    def _create_movement(self, movement_type, quantity, product=None,
                         unit_price=1000, movement_date=None):
        """StockMovement 헬퍼 — 고유 전표번호 자동 생성"""
        self._movement_seq += 1
        return StockMovement.objects.create(
            movement_number=f'LOT-MOV-{self._movement_seq:04d}',
            movement_type=movement_type,
            product=product or self.product,
            warehouse=self.warehouse,
            quantity=quantity,
            unit_price=unit_price,
            movement_date=movement_date or date.today(),
            created_by=self.user,
        )

    def test_inbound_creates_stock_lot(self):
        """IN 타입 StockMovement 생성 시 StockLot 자동 생성 확인"""
        from apps.inventory.models import StockLot
        self._create_movement('IN', 50, unit_price=3000)
        lots = StockLot.objects.filter(product=self.product)
        self.assertEqual(lots.count(), 1)
        lot = lots.first()
        self.assertEqual(lot.initial_quantity, 50)
        self.assertEqual(lot.remaining_quantity, 50)
        self.assertEqual(lot.unit_cost, 3000)

    def test_lot_number_auto_generated(self):
        """lot_number가 자동 채번되는지"""
        from apps.inventory.models import StockLot
        mv = self._create_movement('IN', 10)
        lot = StockLot.objects.filter(product=self.product).first()
        self.assertIsNotNone(lot)
        # LOT-{product.code}-{YYYYMMDD}-{seq}
        self.assertTrue(lot.lot_number.startswith(f'LOT-{self.product.code}-'))
        self.assertRegex(lot.lot_number, r'LOT-LOT-PRD-001-\d{8}-\d{3}')

    def test_fifo_consumes_oldest_first(self):
        """FIFO 제품의 OUT 시 가장 오래된 LOT부터 소진"""
        from apps.inventory.models import StockLot
        # 먼저 오래된 입고
        self._create_movement(
            'IN', 30, unit_price=1000,
            movement_date=date.today() - timedelta(days=10),
        )
        # 최근 입고
        self._create_movement(
            'IN', 30, unit_price=2000,
            movement_date=date.today(),
        )
        lots = StockLot.objects.filter(
            product=self.product,
        ).order_by('received_date', 'pk')
        self.assertEqual(lots.count(), 2)

        # 출고 20개 — FIFO이므로 오래된 LOT(1000원)부터 소진
        self._create_movement('OUT', 20)
        lots_after = StockLot.objects.filter(
            product=self.product,
        ).order_by('received_date', 'pk')
        # 오래된 LOT: 30 - 20 = 10 잔여
        self.assertEqual(lots_after[0].remaining_quantity, 10)
        # 최근 LOT: 30 그대로
        self.assertEqual(lots_after[1].remaining_quantity, 30)

    def test_lifo_consumes_newest_first(self):
        """LIFO 제품의 OUT 시 최근 LOT부터 소진"""
        from apps.inventory.models import StockLot
        self.product.valuation_method = 'LIFO'
        self.product.save(update_fields=['valuation_method'])

        # 오래된 입고
        self._create_movement(
            'IN', 30, unit_price=1000,
            movement_date=date.today() - timedelta(days=10),
        )
        # 최근 입고
        self._create_movement(
            'IN', 30, unit_price=2000,
            movement_date=date.today(),
        )

        # 출고 20개 — LIFO이므로 최근 LOT(2000원)부터 소진
        self._create_movement('OUT', 20)
        lots_after = StockLot.objects.filter(
            product=self.product,
        ).order_by('received_date', 'pk')
        # 오래된 LOT: 30 그대로
        self.assertEqual(lots_after[0].remaining_quantity, 30)
        # 최근 LOT: 30 - 20 = 10
        self.assertEqual(lots_after[1].remaining_quantity, 10)

    def test_avg_creates_lot_but_no_special_consume(self):
        """AVG 제품도 LOT 생성하지만 소진 순서는 FIFO"""
        from apps.inventory.models import StockLot
        self.product.valuation_method = 'AVG'
        self.product.save(update_fields=['valuation_method'])

        # 오래된 입고
        self._create_movement(
            'IN', 30, unit_price=1000,
            movement_date=date.today() - timedelta(days=10),
        )
        # 최근 입고
        self._create_movement(
            'IN', 30, unit_price=2000,
            movement_date=date.today(),
        )
        lots = StockLot.objects.filter(product=self.product)
        self.assertEqual(lots.count(), 2)

        # 출고 20개 — AVG는 FIFO 순서로 소진
        self._create_movement('OUT', 20)
        lots_after = StockLot.objects.filter(
            product=self.product,
        ).order_by('received_date', 'pk')
        # 오래된 LOT부터 소진: 30 - 20 = 10
        self.assertEqual(lots_after[0].remaining_quantity, 10)
        self.assertEqual(lots_after[1].remaining_quantity, 30)


class StockLotSoftDeleteTest(TestCase):
    """StockMovement soft delete 시 StockLot 복원 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='lotsduser', password='testpass123', role='staff',
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-LOTSD', name='LOT삭제테스트창고', created_by=self.user,
        )
        self.product = Product.objects.create(
            code='LOTSD-001',
            name='LOT삭제테스트제품',
            product_type='FINISHED',
            unit_price=10000,
            cost_price=5000,
            current_stock=0,
            valuation_method='FIFO',
            created_by=self.user,
        )
        self._movement_seq = 0

    def _create_movement(self, movement_type, quantity, unit_price=1000,
                         movement_date=None):
        self._movement_seq += 1
        return StockMovement.objects.create(
            movement_number=f'LOTSD-{self._movement_seq:04d}',
            movement_type=movement_type,
            product=self.product,
            warehouse=self.warehouse,
            quantity=quantity,
            unit_price=unit_price,
            movement_date=movement_date or date.today(),
            created_by=self.user,
        )

    def test_inbound_soft_delete_removes_lot(self):
        """입고 soft delete 시 연결된 StockLot도 soft delete"""
        from apps.inventory.models import StockLot
        mv = self._create_movement('IN', 50, unit_price=3000)
        self.assertEqual(StockLot.objects.filter(product=self.product).count(), 1)

        # soft delete
        mv.is_active = False
        mv.save()

        # LOT도 soft delete됨
        self.assertEqual(
            StockLot.objects.filter(product=self.product).count(), 0,
        )
        self.assertEqual(
            StockLot.all_objects.filter(product=self.product).count(), 1,
        )

    def test_outbound_soft_delete_restores_lot(self):
        """출고 soft delete 시 소진된 StockLot remaining_quantity 복원"""
        from apps.inventory.models import StockLot
        # 입고 50개
        self._create_movement('IN', 50, unit_price=3000)
        # 출고 20개 → LOT remaining: 50 - 20 = 30
        out_mv = self._create_movement('OUT', 20)

        lot = StockLot.objects.get(product=self.product)
        self.assertEqual(lot.remaining_quantity, 30)

        # 출고 soft delete → LOT remaining 복원
        out_mv.is_active = False
        out_mv.save()

        lot.refresh_from_db()
        self.assertEqual(lot.remaining_quantity, 50)

    def test_outbound_soft_delete_restores_multiple_lots_fifo(self):
        """FIFO 출고 soft delete 시 여러 LOT 복원"""
        from apps.inventory.models import StockLot
        # 입고 2건: 30개씩
        self._create_movement(
            'IN', 30, unit_price=1000,
            movement_date=date.today() - timedelta(days=5),
        )
        self._create_movement(
            'IN', 30, unit_price=2000,
            movement_date=date.today(),
        )
        # 출고 40개 → LOT1: 0잔여, LOT2: 20잔여
        out_mv = self._create_movement('OUT', 40)

        lots = StockLot.objects.filter(
            product=self.product,
        ).order_by('received_date', 'pk')
        self.assertEqual(lots[0].remaining_quantity, 0)
        self.assertEqual(lots[1].remaining_quantity, 20)

        # 출고 soft delete → LOT 복원
        out_mv.is_active = False
        out_mv.save()

        lots = StockLot.objects.filter(
            product=self.product,
        ).order_by('received_date', 'pk')
        self.assertEqual(lots[0].remaining_quantity, 30)
        self.assertEqual(lots[1].remaining_quantity, 30)


class ReservedStockTest(TestCase):
    """재고 예약 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='rsuser', password='testpass123', role='staff',
        )

    def test_reserved_stock_default_zero(self):
        """새 제품의 reserved_stock은 0"""
        product = Product.objects.create(
            code='RS-001', name='예약재고제품',
            product_type='FINISHED', unit_price=1000,
            cost_price=500, created_by=self.user,
        )
        self.assertEqual(product.reserved_stock, 0)

    def test_available_stock_property(self):
        """available_stock = current_stock - reserved_stock"""
        product = Product.objects.create(
            code='RS-002', name='가용재고제품',
            product_type='FINISHED', unit_price=1000,
            cost_price=500, current_stock=100,
            reserved_stock=30, created_by=self.user,
        )
        self.assertEqual(product.available_stock, 70)

    def test_reserved_stock_non_negative_constraint(self):
        """reserved_stock이 음수가 되면 DB 에러"""
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Product.objects.create(
                code='RS-NEG', name='음수예약제품',
                product_type='FINISHED', unit_price=1000,
                cost_price=500, reserved_stock=-1,
                created_by=self.user,
            )


class StockLotViewTest(TestCase):
    """StockLot 뷰 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='lotviewuser', password='testpass123', role='staff',
        )
        self.client.force_login(self.user)
        self.warehouse = Warehouse.objects.create(
            code='WH-LV', name='LOT뷰창고', created_by=self.user,
        )
        self.product = Product.objects.create(
            code='LV-PRD-001', name='LOT뷰제품',
            product_type='FINISHED', unit_price=10000, cost_price=5000,
            current_stock=0, valuation_method='FIFO',
            created_by=self.user,
        )
        self._movement_seq = 0

    def _create_movement(self, movement_type, quantity, unit_price=1000):
        self._movement_seq += 1
        return StockMovement.objects.create(
            movement_number=f'LV-MOV-{self._movement_seq:04d}',
            movement_type=movement_type,
            product=self.product,
            warehouse=self.warehouse,
            quantity=quantity,
            unit_price=unit_price,
            movement_date=date.today(),
            created_by=self.user,
        )

    def test_stocklot_list_page_loads(self):
        """StockLot 목록 페이지 접근 가능"""
        response = self.client.get('/inventory/stock-lots/')
        self.assertEqual(response.status_code, 200)

    def test_stocklot_list_shows_lots(self):
        """입고 시 생성된 LOT가 목록에 표시"""
        from apps.inventory.models import StockLot
        self._create_movement('IN', 50, unit_price=3000)
        response = self.client.get('/inventory/stock-lots/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['lots']), 1)

    def test_stocklot_list_hides_empty_by_default(self):
        """기본적으로 잔량 0인 LOT는 숨김"""
        from apps.inventory.models import StockLot
        self._create_movement('IN', 10, unit_price=1000)
        self._create_movement('OUT', 10)  # 전량 소진
        response = self.client.get('/inventory/stock-lots/')
        self.assertEqual(len(response.context['lots']), 0)

    def test_stocklot_list_show_empty_filter(self):
        """show_empty=1이면 소진 LOT도 표시"""
        from apps.inventory.models import StockLot
        self._create_movement('IN', 10, unit_price=1000)
        self._create_movement('OUT', 10)
        response = self.client.get('/inventory/stock-lots/?show_empty=1')
        self.assertEqual(len(response.context['lots']), 1)

    def test_stocklot_list_search(self):
        """제품명으로 LOT 검색"""
        self._create_movement('IN', 50, unit_price=3000)
        response = self.client.get('/inventory/stock-lots/?q=LOT뷰제품')
        self.assertEqual(len(response.context['lots']), 1)
        response = self.client.get('/inventory/stock-lots/?q=없는제품')
        self.assertEqual(len(response.context['lots']), 0)

    def test_stocklot_list_warehouse_filter(self):
        """창고 필터"""
        self._create_movement('IN', 50, unit_price=3000)
        response = self.client.get(f'/inventory/stock-lots/?warehouse={self.warehouse.pk}')
        self.assertEqual(len(response.context['lots']), 1)
        # 존재하지 않는 창고 ID
        response = self.client.get('/inventory/stock-lots/?warehouse=99999')
        self.assertEqual(len(response.context['lots']), 0)

    def test_stocklot_detail_page_loads(self):
        """StockLot 상세 페이지 접근 가능"""
        from apps.inventory.models import StockLot
        self._create_movement('IN', 50, unit_price=3000)
        lot = StockLot.objects.filter(product=self.product).first()
        response = self.client.get(f'/inventory/stock-lots/{lot.lot_number}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['lot'], lot)

    def test_stocklot_detail_shows_movements(self):
        """LOT 상세에서 연관 입출고 이력 표시"""
        from apps.inventory.models import StockLot
        self._create_movement('IN', 50, unit_price=3000)
        lot = StockLot.objects.filter(product=self.product).first()
        response = self.client.get(f'/inventory/stock-lots/{lot.lot_number}/')
        self.assertIn('movements', response.context)


class StockFormTest(TestCase):
    """StockInForm / StockOutForm 폼 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='formuser', password='testpass123', role='manager',
        )
        self.client.force_login(self.user)
        self.warehouse = Warehouse.objects.create(
            code='WH-FM', name='폼테스트창고', created_by=self.user,
        )
        self.product = Product.objects.create(
            code='FM-PRD-001', name='폼테스트제품',
            product_type='FINISHED', unit_price=10000, cost_price=5000,
            current_stock=100, created_by=self.user,
        )

    def test_stock_in_form_valid(self):
        """StockInForm 유효한 데이터"""
        from apps.inventory.forms import StockInForm
        data = {
            'movement_type': 'IN',
            'product': self.product.pk,
            'warehouse': self.warehouse.pk,
            'quantity': '50',
            'unit_price': '3000',
            'movement_date': date.today().isoformat(),
            'reference': '테스트 입고',
            'notes': '',
        }
        form = StockInForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_stock_in_form_rejects_outbound_type(self):
        """StockInForm은 출고 유형 거부"""
        from apps.inventory.forms import StockInForm
        data = {
            'movement_type': 'OUT',
            'product': self.product.pk,
            'warehouse': self.warehouse.pk,
            'quantity': '50',
            'unit_price': '3000',
            'movement_date': date.today().isoformat(),
        }
        form = StockInForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('movement_type', form.errors)

    def test_stock_in_form_choices(self):
        """StockInForm의 movement_type 선택지 확인"""
        from apps.inventory.forms import StockInForm
        form = StockInForm()
        choice_values = [c[0] for c in form.fields['movement_type'].choices]
        self.assertIn('IN', choice_values)
        self.assertIn('ADJ_PLUS', choice_values)
        self.assertIn('PROD_IN', choice_values)
        self.assertIn('RETURN', choice_values)
        self.assertNotIn('OUT', choice_values)

    def test_stock_out_form_valid(self):
        """StockOutForm 유효한 데이터"""
        from apps.inventory.forms import StockOutForm
        data = {
            'movement_type': 'OUT',
            'product': self.product.pk,
            'warehouse': self.warehouse.pk,
            'quantity': '30',
            'unit_price': '5000',
            'movement_date': date.today().isoformat(),
            'reference': '테스트 출고',
            'notes': '',
        }
        form = StockOutForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_stock_out_form_rejects_inbound_type(self):
        """StockOutForm은 입고 유형 거부"""
        from apps.inventory.forms import StockOutForm
        data = {
            'movement_type': 'IN',
            'product': self.product.pk,
            'warehouse': self.warehouse.pk,
            'quantity': '30',
            'unit_price': '5000',
            'movement_date': date.today().isoformat(),
        }
        form = StockOutForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('movement_type', form.errors)

    def test_stock_out_form_choices(self):
        """StockOutForm의 movement_type 선택지 확인"""
        from apps.inventory.forms import StockOutForm
        form = StockOutForm()
        choice_values = [c[0] for c in form.fields['movement_type'].choices]
        self.assertIn('OUT', choice_values)
        self.assertIn('ADJ_MINUS', choice_values)
        self.assertIn('PROD_OUT', choice_values)
        self.assertNotIn('IN', choice_values)

    def test_stock_in_view_loads(self):
        """입고 전용 등록 페이지 접근 가능"""
        response = self.client.get('/inventory/movements/stock-in/')
        self.assertEqual(response.status_code, 200)

    def test_stock_out_view_loads(self):
        """출고 전용 등록 페이지 접근 가능"""
        response = self.client.get('/inventory/movements/stock-out/')
        self.assertEqual(response.status_code, 200)

    def test_stock_in_creates_movement(self):
        """입고 전용 폼으로 StockMovement 생성"""
        data = {
            'movement_type': 'IN',
            'product': self.product.pk,
            'warehouse': self.warehouse.pk,
            'quantity': '25',
            'unit_price': '4000',
            'movement_date': date.today().isoformat(),
            'reference': '',
            'notes': '',
        }
        response = self.client.post('/inventory/movements/stock-in/', data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            StockMovement.objects.filter(
                product=self.product, movement_type='IN', quantity=25,
            ).exists()
        )

    def test_stock_out_creates_movement(self):
        """출고 전용 폼으로 StockMovement 생성"""
        data = {
            'movement_type': 'OUT',
            'product': self.product.pk,
            'warehouse': self.warehouse.pk,
            'quantity': '10',
            'unit_price': '5000',
            'movement_date': date.today().isoformat(),
            'reference': '',
            'notes': '',
        }
        response = self.client.post('/inventory/movements/stock-out/', data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            StockMovement.objects.filter(
                product=self.product, movement_type='OUT', quantity=10,
            ).exists()
        )


class InventoryValuationViewTest(TestCase):
    """재고평가 뷰 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='valuser', password='testpass123', role='staff',
        )
        self.client.force_login(self.user)

    def test_valuation_page_loads(self):
        """/inventory/valuation/ 페이지 접근 가능"""
        response = self.client.get('/inventory/valuation/')
        self.assertEqual(response.status_code, 200)


class StockNegativePreventionTest(TestCase):
    """재고 마이너스 방지 + 창고이동 재고 검증 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='neguser', password='testpass123', role='staff',
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-NEG', name='마이너스테스트창고', created_by=self.user,
        )
        self.warehouse2 = Warehouse.objects.create(
            code='WH-NEG2', name='도착창고', created_by=self.user,
        )
        self.product = Product.objects.create(
            code='NEG-PRD-001', name='재고검증제품',
            product_type='FINISHED', unit_price=10000, cost_price=5000,
            current_stock=0, created_by=self.user,
        )
        self._seq = 0

    def _create_movement(self, movement_type, quantity, product=None,
                         warehouse=None, unit_price=1000):
        self._seq += 1
        return StockMovement.objects.create(
            movement_number=f'NEG-{self._seq:04d}',
            movement_type=movement_type,
            product=product or self.product,
            warehouse=warehouse or self.warehouse,
            quantity=quantity,
            unit_price=unit_price,
            movement_date=date.today(),
            created_by=self.user,
        )

    # ── 재고 마이너스 방지 ─────────────────────────────────

    def test_stock_negative_prevention(self):
        """재고 부족 시 OUT 출고 차단 검증"""
        from django.core.exceptions import ValidationError
        # 재고 10개
        self._create_movement('IN', 10)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal('10'))

        # 15개 출고 시도 → ValidationError
        with self.assertRaises(ValidationError):
            self._create_movement('OUT', 15)

        # 재고 변동 없음 확인
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal('10'))

    def test_stock_negative_prevention_adj_minus(self):
        """ADJ_MINUS 타입도 재고 부족 시 차단"""
        from django.core.exceptions import ValidationError
        self._create_movement('IN', 5)
        with self.assertRaises(ValidationError):
            self._create_movement('ADJ_MINUS', 10)

    def test_stock_negative_prevention_prod_out(self):
        """PROD_OUT 타입도 재고 부족 시 차단"""
        from django.core.exceptions import ValidationError
        # 재고 0인 상태에서 생산출고 시도
        with self.assertRaises(ValidationError):
            self._create_movement('PROD_OUT', 5)

    def test_stock_negative_allowed_for_service(self):
        """SERVICE 타입 제품은 재고 추적 안 함 — 음수 허용(시그널 스킵)"""
        service = Product.objects.create(
            code='SVC-NEG-001', name='서비스제품',
            product_type='SERVICE', unit_price=5000, cost_price=0,
            current_stock=0, created_by=self.user,
        )
        # SERVICE 타입은 is_stockable=False → 시그널이 재고 갱신/검증 스킵
        self._seq += 1
        movement = StockMovement.objects.create(
            movement_number=f'NEG-SVC-{self._seq:04d}',
            movement_type='OUT',
            product=service,
            warehouse=self.warehouse,
            quantity=10,
            unit_price=0,
            movement_date=date.today(),
            created_by=self.user,
        )
        self.assertIsNotNone(movement.pk)
        # SERVICE 제품은 current_stock 미갱신
        service.refresh_from_db()
        self.assertEqual(service.current_stock, Decimal('0'))

    def test_normal_outbound_succeeds(self):
        """정상 출고 성공 확인 — 재고 충분 시 출고 가능"""
        self._create_movement('IN', 100)
        self._create_movement('OUT', 30)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal('70'))

    def test_exact_stock_outbound_succeeds(self):
        """재고와 정확히 같은 수량 출고 가능"""
        self._create_movement('IN', 50)
        self._create_movement('OUT', 50)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal('0'))

    # ── 창고간이동 재고 검증 ───────────────────────────────

    def test_transfer_insufficient_stock(self):
        """창고이동 시 출발창고 재고 부족 차단"""
        from django.core.exceptions import ValidationError
        # 출발창고에 10개 입고
        self._create_movement('IN', 10, warehouse=self.warehouse)
        # 20개 이동 시도 → 출발창고 재고 부족
        with self.assertRaises(ValidationError):
            StockTransfer.objects.create(
                transfer_number='TF-FAIL-001',
                from_warehouse=self.warehouse,
                to_warehouse=self.warehouse2,
                product=self.product,
                quantity=20,
                transfer_date=date.today(),
                created_by=self.user,
            )

    def test_transfer_no_warehouse_stock(self):
        """출발창고에 WarehouseStock 레코드 없을 때 이동 차단"""
        from django.core.exceptions import ValidationError
        # WarehouseStock 없는 상태에서 이동 시도
        with self.assertRaises(ValidationError):
            StockTransfer.objects.create(
                transfer_number='TF-FAIL-002',
                from_warehouse=self.warehouse2,  # 입고한 적 없는 창고
                to_warehouse=self.warehouse,
                product=self.product,
                quantity=5,
                transfer_date=date.today(),
                created_by=self.user,
            )

    def test_transfer_sufficient_stock_succeeds(self):
        """창고이동 — 재고 충분 시 정상 이동"""
        self._create_movement('IN', 50, warehouse=self.warehouse)
        transfer = StockTransfer.objects.create(
            transfer_number='TF-OK-001',
            from_warehouse=self.warehouse,
            to_warehouse=self.warehouse2,
            product=self.product,
            quantity=30,
            transfer_date=date.today(),
            created_by=self.user,
        )
        self.assertIsNotNone(transfer.pk)
        # 글로벌 재고 변동 없음 (OUT + IN 상쇄)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal('50'))
        # 출발창고 재고 감소
        ws_from = WarehouseStock.objects.get(
            warehouse=self.warehouse, product=self.product,
        )
        self.assertEqual(ws_from.quantity, Decimal('20'))
        # 도착창고 재고 증가
        ws_to = WarehouseStock.objects.get(
            warehouse=self.warehouse2, product=self.product,
        )
        self.assertEqual(ws_to.quantity, Decimal('30'))


class SerialTrackingTest(TestCase):
    """시리얼번호 자동 생성 테스트 — 생산실적 등록 시 시리얼 추적 검증"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123', role='staff',
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-001', name='메인창고', is_default=True, created_by=self.user,
        )
        self.product = Product.objects.create(
            code='FIN-0001',
            name='시리얼 추적 제품',
            product_type='FINISHED',
            unit_price=10000,
            cost_price=7000,
            safety_stock=10,
            current_stock=100,
            serial_tracking=True,
            serial_prefix='SN-FIN0001-',
            created_by=self.user,
        )
        self.product_no_serial = Product.objects.create(
            code='FIN-0002',
            name='비추적 제품',
            product_type='FINISHED',
            unit_price=5000,
            cost_price=3000,
            current_stock=50,
            serial_tracking=False,
            created_by=self.user,
        )
        # BOM + 생산계획 + 작업지시 세팅
        from apps.production.models import BOM, BOMItem, ProductionPlan, WorkOrder
        self.raw_material = Product.objects.create(
            code='RAW-0001',
            name='원자재A',
            product_type='RAW',
            cost_price=1000,
            current_stock=1000,
            created_by=self.user,
        )
        self.bom = BOM.objects.create(
            product=self.product,
            version='v1',
            is_default=True,
            created_by=self.user,
        )
        BOMItem.objects.create(
            bom=self.bom,
            material=self.raw_material,
            quantity=2,
            created_by=self.user,
        )
        self.plan = ProductionPlan.objects.create(
            product=self.product,
            bom=self.bom,
            planned_quantity=100,
            planned_start=date.today(),
            planned_end=date.today(),
            status='IN_PROGRESS',
            created_by=self.user,
        )
        self.work_order = WorkOrder.objects.create(
            production_plan=self.plan,
            quantity=50,
            status='IN_PROGRESS',
            created_by=self.user,
        )
        # 비추적 제품용
        self.bom2 = BOM.objects.create(
            product=self.product_no_serial,
            version='v1',
            is_default=True,
            created_by=self.user,
        )
        BOMItem.objects.create(
            bom=self.bom2,
            material=self.raw_material,
            quantity=1,
            created_by=self.user,
        )
        self.plan2 = ProductionPlan.objects.create(
            product=self.product_no_serial,
            bom=self.bom2,
            planned_quantity=50,
            planned_start=date.today(),
            planned_end=date.today(),
            status='IN_PROGRESS',
            created_by=self.user,
        )
        self.work_order2 = WorkOrder.objects.create(
            production_plan=self.plan2,
            quantity=20,
            status='IN_PROGRESS',
            created_by=self.user,
        )

    def test_serial_auto_generation(self):
        """생산 시 serial_tracking=True 제품은 시리얼번호가 자동 생성되어야 한다"""
        from apps.production.models import ProductionRecord
        record = ProductionRecord.objects.create(
            work_order=self.work_order,
            good_quantity=5,
            record_date=date.today(),
            created_by=self.user,
        )
        serials = SerialNumber.objects.filter(
            production_record=record,
            product=self.product,
        )
        self.assertEqual(serials.count(), 5)
        for sn in serials:
            self.assertEqual(sn.status, SerialNumber.Status.IN_STOCK)
            self.assertEqual(sn.production_date, date.today())
            self.assertIsNotNone(sn.warehouse)

    def test_serial_not_generated_for_non_tracking(self):
        """serial_tracking=False 제품은 시리얼번호가 생성되지 않아야 한다"""
        from apps.production.models import ProductionRecord
        record = ProductionRecord.objects.create(
            work_order=self.work_order2,
            good_quantity=3,
            record_date=date.today(),
            created_by=self.user,
        )
        serials = SerialNumber.objects.filter(production_record=record)
        self.assertEqual(serials.count(), 0)

    def test_serial_unique(self):
        """시리얼번호는 unique 제약을 가져야 한다"""
        from django.db import IntegrityError
        SerialNumber.objects.create(
            serial='UNIQUE-001',
            product=self.product,
            status=SerialNumber.Status.IN_STOCK,
            created_by=self.user,
        )
        with self.assertRaises(IntegrityError):
            SerialNumber.objects.create(
                serial='UNIQUE-001',
                product=self.product,
                status=SerialNumber.Status.IN_STOCK,
                created_by=self.user,
            )

    def test_serial_prefix_format(self):
        """시리얼번호가 접두사 + 날짜 + 순번 형식이어야 한다"""
        from apps.production.models import ProductionRecord
        from django.utils import timezone

        record = ProductionRecord.objects.create(
            work_order=self.work_order,
            good_quantity=3,
            record_date=date.today(),
            created_by=self.user,
        )
        serials = SerialNumber.objects.filter(
            production_record=record,
        ).order_by('serial')

        today_str = timezone.now().strftime('%Y%m%d')
        prefix = self.product.serial_prefix

        for i, sn in enumerate(serials, start=1):
            expected = f'{prefix}{today_str}-{i:04d}'
            self.assertEqual(sn.serial, expected)

    def test_serial_list_view(self):
        """시리얼 목록 뷰 접근 및 필터 동작"""
        sn = SerialNumber.objects.create(
            serial='VIEW-LIST-001',
            product=self.product,
            status=SerialNumber.Status.IN_STOCK,
            warehouse=self.warehouse,
            created_by=self.user,
        )
        self.client.force_login(self.user)

        # 기본 목록 접근
        response = self.client.get('/inventory/serials/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'VIEW-LIST-001')

        # 상태 필터
        response = self.client.get('/inventory/serials/?status=IN_STOCK')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'VIEW-LIST-001')

        # 제품 필터
        response = self.client.get(f'/inventory/serials/?product={self.product.pk}')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'VIEW-LIST-001')

        # 창고 필터
        response = self.client.get(f'/inventory/serials/?warehouse={self.warehouse.pk}')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'VIEW-LIST-001')

        # 검색 (시리얼번호)
        response = self.client.get('/inventory/serials/?q=VIEW-LIST')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'VIEW-LIST-001')

        # 존재하지 않는 필터 — 결과 없음
        response = self.client.get('/inventory/serials/?status=DISPOSED')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'VIEW-LIST-001')

    def test_serial_detail_view(self):
        """시리얼 상세 뷰 접근"""
        sn = SerialNumber.objects.create(
            serial='VIEW-DETAIL-001',
            product=self.product,
            status=SerialNumber.Status.IN_STOCK,
            warehouse=self.warehouse,
            production_date=date.today(),
            created_by=self.user,
        )
        self.client.force_login(self.user)

        response = self.client.get(f'/inventory/serials/{sn.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'VIEW-DETAIL-001')
        self.assertContains(response, self.product.name)


class SafetyStockTaskTest(TestCase):
    """안전재고 Celery 태스크 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='safety_user', password='testpass123', role='admin',
        )
        Warehouse.objects.create(
            code='WH-SF', name='안전재고창고', is_default=True, created_by=self.user,
        )

    def test_safety_stock_alert(self):
        """안전재고 미달 제품이 올바르게 감지되어야 한다"""
        from apps.inventory.tasks import check_safety_stock

        # 안전재고 미달 제품
        Product.objects.create(
            code='SAFE-001', name='부족제품', product_type='FINISHED',
            current_stock=5, safety_stock=10, created_by=self.user,
        )
        # 안전재고 충분 제품
        Product.objects.create(
            code='SAFE-002', name='충분제품', product_type='FINISHED',
            current_stock=20, safety_stock=10, created_by=self.user,
        )
        # 서비스 제품 (미추적 대상)
        Product.objects.create(
            code='SAFE-003', name='서비스', product_type='SERVICE',
            current_stock=0, safety_stock=10, created_by=self.user,
        )

        result = check_safety_stock()
        self.assertIn('1 products below safety stock', result)

    def test_no_alert_when_all_sufficient(self):
        """모든 제품이 안전재고 이상이면 0건이어야 한다"""
        from apps.inventory.tasks import check_safety_stock

        Product.objects.create(
            code='SAFE-OK1', name='충분1', product_type='FINISHED',
            current_stock=20, safety_stock=10, created_by=self.user,
        )
        result = check_safety_stock()
        self.assertIn('0 products below safety stock', result)


class ReorderPointTaskTest(TestCase):
    """재주문점 Celery 태스크 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='reorder_user', password='testpass123', role='staff',
        )
        self.manager = User.objects.create_user(
            username='reorder_mgr', password='testpass123', role='manager',
        )

    def test_alert_when_below_reorder_point(self):
        """현재고가 재주문점 이하이면 알림 생성"""
        from apps.inventory.tasks import check_reorder_point
        from apps.core.notification import Notification

        Product.objects.create(
            code='RP-001', name='재주문제품', product_type='RAW',
            current_stock=5, reorder_point=10, lead_time_days=3,
            created_by=self.user,
        )
        result = check_reorder_point()
        self.assertIn('1 products below reorder point', result)
        # 매니저에게 알림 생성 확인
        notis = Notification.objects.filter(
            user=self.manager, noti_type='STOCK_LOW',
        )
        self.assertTrue(notis.exists())
        self.assertIn('재주문점 미달', notis.first().title)

    def test_no_alert_when_stock_above_reorder_point(self):
        """현재고가 재주문점 초과이면 알림 없음"""
        from apps.inventory.tasks import check_reorder_point

        Product.objects.create(
            code='RP-002', name='충분제품', product_type='RAW',
            current_stock=20, reorder_point=10,
            created_by=self.user,
        )
        result = check_reorder_point()
        self.assertIn('0 products below reorder point', result)

    def test_no_alert_when_reorder_point_zero(self):
        """재주문점이 0이면 검사 대상에서 제외"""
        from apps.inventory.tasks import check_reorder_point

        Product.objects.create(
            code='RP-003', name='미설정제품', product_type='RAW',
            current_stock=0, reorder_point=0,
            created_by=self.user,
        )
        result = check_reorder_point()
        self.assertIn('0 products below reorder point', result)

    def test_service_products_excluded(self):
        """서비스/무형상품은 재주문점 체크에서 제외"""
        from apps.inventory.tasks import check_reorder_point

        Product.objects.create(
            code='RP-SVC', name='서비스', product_type='SERVICE',
            current_stock=0, reorder_point=10,
            created_by=self.user,
        )
        result = check_reorder_point()
        self.assertIn('0 products below reorder point', result)

    def test_reorder_point_field_default(self):
        """reorder_point 기본값은 0"""
        p = Product.objects.create(
            code='RP-DEF', name='기본값', product_type='RAW',
            created_by=self.user,
        )
        self.assertEqual(p.reorder_point, 0)


class CostCascadeTest(TestCase):
    """자재 원가 변동 시 BOM 완제품 원가 캐스케이드 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='costuser', password='testpass123', role='staff',
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-CC', name='원가테스트창고', created_by=self.user,
        )
        # 원자재 2종
        self.mat_a = Product.objects.create(
            code='MAT-A', name='자재A', product_type='RAW',
            cost_price=1000, created_by=self.user,
        )
        self.mat_b = Product.objects.create(
            code='MAT-B', name='자재B', product_type='RAW',
            cost_price=2000, created_by=self.user,
        )
        # 완제품
        self.finished = Product.objects.create(
            code='FIN-CC', name='완제품', product_type='FINISHED',
            cost_price=0, created_by=self.user,
        )
        # BOM: 자재A x 2 + 자재B x 1 = 2000 + 2000 = 4000
        from apps.production.models import BOM, BOMItem
        self.bom = BOM.objects.create(
            product=self.finished, version='1.0',
            is_default=True, created_by=self.user,
        )
        BOMItem.objects.create(
            bom=self.bom, material=self.mat_a,
            quantity=2, created_by=self.user,
        )
        BOMItem.objects.create(
            bom=self.bom, material=self.mat_b,
            quantity=1, created_by=self.user,
        )

    def test_bom_item_save_syncs_product_cost(self):
        """BOMItem 저장 시 완제품 cost_price가 BOM 원가로 동기화"""
        self.finished.refresh_from_db()
        # BOM 원가: 1000*2 + 2000*1 = 4000
        self.assertEqual(self.finished.cost_price, 4000)

    def test_material_cost_change_cascades_to_finished(self):
        """자재 원가 변경 시 완제품 cost_price 자동 재계산"""
        # 자재A 원가 1000 → 1500 (이동평균 시뮬레이션: 직접 업데이트 + 캐스케이드)
        Product.objects.filter(pk=self.mat_a.pk).update(cost_price=1500)
        from apps.production.signals import _cascade_cost_to_parents
        _cascade_cost_to_parents(self.mat_a.pk)

        self.finished.refresh_from_db()
        # 새 BOM 원가: 1500*2 + 2000*1 = 5000
        self.assertEqual(self.finished.cost_price, 5000)

    def test_multilevel_cascade(self):
        """반제품→완제품 다단계 캐스케이드"""
        from apps.production.models import BOM, BOMItem

        # 반제품 생성 (자재A x 3 = 3000)
        semi = Product.objects.create(
            code='SEMI-CC', name='반제품', product_type='SEMI',
            cost_price=0, created_by=self.user,
        )
        semi_bom = BOM.objects.create(
            product=semi, version='1.0',
            is_default=True, created_by=self.user,
        )
        BOMItem.objects.create(
            bom=semi_bom, material=self.mat_a,
            quantity=3, created_by=self.user,
        )
        semi.refresh_from_db()
        self.assertEqual(semi.cost_price, 3000)

        # 최종완제품 (반제품 x 1 + 자재B x 1)
        final = Product.objects.create(
            code='FIN-ML', name='최종완제품', product_type='FINISHED',
            cost_price=0, created_by=self.user,
        )
        final_bom = BOM.objects.create(
            product=final, version='1.0',
            is_default=True, created_by=self.user,
        )
        BOMItem.objects.create(
            bom=final_bom, material=semi,
            quantity=1, created_by=self.user,
        )
        BOMItem.objects.create(
            bom=final_bom, material=self.mat_b,
            quantity=1, created_by=self.user,
        )
        final.refresh_from_db()
        # 반제품(3000) + 자재B(2000) = 5000
        self.assertEqual(final.cost_price, 5000)

        # 자재A 원가 변경: 1000 → 2000
        Product.objects.filter(pk=self.mat_a.pk).update(cost_price=2000)
        from apps.production.signals import _cascade_cost_to_parents
        _cascade_cost_to_parents(self.mat_a.pk)

        semi.refresh_from_db()
        # 반제품: 2000*3 = 6000
        self.assertEqual(semi.cost_price, 6000)

        final.refresh_from_db()
        # 최종: 반제품(6000) + 자재B(2000) = 8000
        self.assertEqual(final.cost_price, 8000)

    def test_weighted_avg_triggers_cascade(self):
        """입고 시 이동평균 원가 변동 → 상위 BOM 캐스케이드"""
        # 자재A 현재고 10, 원가 1000 → 입고 10 @ 2000
        Product.objects.filter(pk=self.mat_a.pk).update(
            current_stock=10, cost_price=1000,
        )
        mv_seq = 0
        mv_seq += 1
        StockMovement.objects.create(
            movement_number=f'CC-IN-{mv_seq:04d}',
            movement_type='IN',
            product=self.mat_a,
            warehouse=self.warehouse,
            quantity=10,
            unit_price=2000,
            movement_date=date.today(),
            created_by=self.user,
        )
        # 이동평균: (10*1000 + 10*2000) / 20 = 1500
        self.mat_a.refresh_from_db()
        self.assertEqual(self.mat_a.cost_price, 1500)

        # 완제품 원가도 갱신: 1500*2 + 2000*1 = 5000
        self.finished.refresh_from_db()
        self.assertEqual(self.finished.cost_price, 5000)


class CostBasisConfigTest(TestCase):
    """원가기준 설정 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='cfguser', password='testpass123', role='staff',
        )
        self.product = Product.objects.create(
            code='CFG-001', name='테스트제품', product_type='FINISHED',
            cost_price=5000, created_by=self.user,
        )

    def test_default_returns_product_cost(self):
        """설정 없으면 제품 현재원가 반환"""
        from apps.inventory.models import CostBasisConfig
        cost = CostBasisConfig.get_cost_for_product(self.product, 'ORDER')
        self.assertEqual(cost, 5000)

    def test_configured_basis_product(self):
        """PRODUCT 기준 설정 시 제품 현재원가 반환"""
        from apps.inventory.models import CostBasisConfig
        CostBasisConfig.objects.create(
            stage='ORDER', primary_basis='PRODUCT',
            fallback_basis='BOM', created_by=self.user,
        )
        cost = CostBasisConfig.get_cost_for_product(self.product, 'ORDER')
        self.assertEqual(cost, 5000)

    def test_configured_basis_bom_with_fallback(self):
        """BOM 기준인데 BOM 없으면 fallback으로 제품원가"""
        from apps.inventory.models import CostBasisConfig
        CostBasisConfig.objects.create(
            stage='QUOTATION', primary_basis='BOM',
            fallback_basis='PRODUCT', created_by=self.user,
        )
        cost = CostBasisConfig.get_cost_for_product(self.product, 'QUOTATION')
        # BOM 없으므로 fallback → PRODUCT → 5000
        self.assertEqual(cost, 5000)

    def test_bulk_costs(self):
        """일괄 원가 조회"""
        from apps.inventory.models import CostBasisConfig
        p2 = Product.objects.create(
            code='CFG-002', name='테스트제품2', product_type='RAW',
            cost_price=3000, created_by=self.user,
        )
        CostBasisConfig.objects.create(
            stage='ORDER', primary_basis='PRODUCT',
            fallback_basis='BOM', created_by=self.user,
        )
        costs = CostBasisConfig.get_costs_bulk(
            [self.product.pk, p2.pk], 'ORDER',
        )
        self.assertEqual(costs[str(self.product.pk)], 5000)
        self.assertEqual(costs[str(p2.pk)], 3000)

    def test_recalculate_cost_price_from_bom(self):
        """Product.recalculate_cost_price()가 BOM 기반으로 원가 재계산"""
        from apps.production.models import BOM, BOMItem
        mat = Product.objects.create(
            code='MAT-RC', name='재계산자재', product_type='RAW',
            cost_price=1000, created_by=self.user,
        )
        bom = BOM.objects.create(
            product=self.product, version='1.0',
            is_default=True, created_by=self.user,
        )
        BOMItem.objects.create(
            bom=bom, material=mat, quantity=3, created_by=self.user,
        )
        # BOM 시그널이 이미 동기화했을 수 있으므로 수동 호출 테스트
        self.product.refresh_from_db()
        self.product.cost_price = 0  # 리셋
        Product.objects.filter(pk=self.product.pk).update(cost_price=0)
        changed = self.product.recalculate_cost_price()
        self.assertTrue(changed)
        self.product.refresh_from_db()
        self.assertEqual(self.product.cost_price, 3000)


class AutoStandardCostTest(TestCase):
    """auto_standard_cost 활성화 시 표준원가 자동 버전 생성 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='autostd', password='testpass123', role='staff',
        )
        self.mat = Product.objects.create(
            code='MAT-AS', name='자재', product_type='RAW',
            cost_price=1000, created_by=self.user,
        )
        self.finished = Product.objects.create(
            code='FIN-AS', name='완제품', product_type='FINISHED',
            cost_price=0, auto_standard_cost=True,
            created_by=self.user,
        )
        from apps.production.models import BOM, BOMItem
        self.bom = BOM.objects.create(
            product=self.finished, version='1.0',
            is_default=True, created_by=self.user,
        )
        BOMItem.objects.create(
            bom=self.bom, material=self.mat,
            quantity=5, created_by=self.user,
        )

    def test_auto_creates_standard_cost_on_bom_sync(self):
        """BOM 동기화 시 auto_standard_cost가 켜져 있으면 표준원가 자동 생성"""
        from apps.production.models import StandardCost
        stds = StandardCost.objects.filter(
            product=self.finished, is_current=True, is_active=True,
        )
        self.assertEqual(stds.count(), 1)
        std = stds.first()
        self.assertTrue(std.version.startswith('AUTO-'))
        self.assertEqual(std.material_cost, 5000)  # 1000 * 5
        self.assertEqual(std.total_standard_cost, 5000)  # 노무비/간접비 없음

    def test_auto_versions_on_material_cost_change(self):
        """자재 원가 변동 시 새 표준원가 버전 생성"""
        from apps.production.models import StandardCost
        from apps.production.signals import _cascade_cost_to_parents

        # 초기 표준원가 확인
        self.assertEqual(
            StandardCost.objects.filter(product=self.finished, is_active=True).count(), 1,
        )

        # 자재 원가 변경: 1000 → 2000
        Product.objects.filter(pk=self.mat.pk).update(cost_price=2000)
        _cascade_cost_to_parents(self.mat.pk)

        # 새 버전 생성 확인
        all_stds = StandardCost.objects.filter(
            product=self.finished, is_active=True,
        ).order_by('-effective_date', '-pk')
        self.assertGreaterEqual(all_stds.count(), 2)

        # 현행 표준원가 = 새 자재원가
        current = all_stds.filter(is_current=True).first()
        self.assertEqual(current.material_cost, 10000)  # 2000 * 5
        self.assertEqual(current.total_standard_cost, 10000)

        # 이전 버전은 is_current=False
        old = all_stds.filter(is_current=False).first()
        self.assertIsNotNone(old)
        self.assertEqual(old.material_cost, 5000)

    def test_auto_version_material_cost_only(self):
        """자동생성 표준원가는 자재원가만 기록, 노무비/간접비는 0 (수동 관리)"""
        from apps.production.models import StandardCost
        from apps.production.signals import _cascade_cost_to_parents

        # 기존 표준원가에 노무비/간접비 수동 설정
        std = StandardCost.objects.filter(
            product=self.finished, is_current=True,
        ).first()
        std.direct_labor_hours = 2
        std.labor_rate_per_hour = 10000
        std.overhead_rate = 50  # 간접비 50%
        std.save()

        # 자재 원가 변경 트리거
        Product.objects.filter(pk=self.mat.pk).update(cost_price=1500)
        _cascade_cost_to_parents(self.mat.pk)

        current = StandardCost.objects.filter(
            product=self.finished, is_current=True,
        ).first()
        # 자동생성은 자재원가만 — 노무비/간접비는 0
        self.assertEqual(current.material_cost, 7500)  # 1500*5
        self.assertEqual(current.direct_labor_hours, 0)
        self.assertEqual(current.labor_rate_per_hour, 0)
        self.assertEqual(current.overhead_rate, 0)
        self.assertEqual(current.labor_cost, 0)
        self.assertEqual(current.overhead_cost, 0)
        self.assertEqual(current.total_standard_cost, 7500)  # 자재원가만

    def test_no_version_when_disabled(self):
        """auto_standard_cost=False이면 표준원가 자동 생성 안함"""
        from apps.production.models import StandardCost, BOM, BOMItem
        from apps.production.signals import _cascade_cost_to_parents

        product = Product.objects.create(
            code='FIN-NO', name='수동제품', product_type='FINISHED',
            cost_price=0, auto_standard_cost=False,
            created_by=self.user,
        )
        bom = BOM.objects.create(
            product=product, version='1.0',
            is_default=True, created_by=self.user,
        )
        BOMItem.objects.create(
            bom=bom, material=self.mat, quantity=3, created_by=self.user,
        )
        # auto_standard_cost=False → 표준원가 생성 안됨
        self.assertEqual(
            StandardCost.objects.filter(product=product).count(), 0,
        )

    def test_skip_when_no_cost_change(self):
        """자재원가 변동 없으면 새 버전 생성하지 않음"""
        from apps.production.models import StandardCost
        from apps.production.signals import _sync_product_cost_price

        initial_count = StandardCost.objects.filter(
            product=self.finished, is_active=True,
        ).count()

        # 같은 원가로 다시 동기화 → 변동 없음 → 새 버전 없음
        self.finished.refresh_from_db()
        _sync_product_cost_price(self.finished)

        self.assertEqual(
            StandardCost.objects.filter(
                product=self.finished, is_active=True,
            ).count(),
            initial_count,
        )
