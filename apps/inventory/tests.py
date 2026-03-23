from decimal import Decimal
from datetime import date, timedelta

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
