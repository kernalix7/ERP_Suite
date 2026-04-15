from decimal import Decimal

from django.test import TestCase

from apps.inventory.models import Product, StockMovement, Warehouse
from apps.wms.models import BinLocation, PickOrder, PickOrderItem, PutAwayTask, WarehouseZone, WavePlan


class WarehouseZoneTest(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name='본사창고', code='WH01')

    def test_zone_creation(self):
        zone = WarehouseZone.objects.create(
            warehouse=self.warehouse,
            name='입고구역',
            code='Z-RCV-01',
            zone_type='RECEIVING',
        )
        self.assertEqual(zone.name, '입고구역')
        self.assertEqual(zone.zone_type, 'RECEIVING')
        self.assertEqual(str(zone), '[Z-RCV-01] 입고구역')


class BinLocationTest(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name='본사창고', code='WH01')
        self.zone = WarehouseZone.objects.create(
            warehouse=self.warehouse, name='보관구역', code='Z-STR-01',
        )

    def test_bin_creation(self):
        bin_loc = BinLocation.objects.create(
            zone=self.zone, code='A-01-01', row='A', column='01', level='01',
        )
        self.assertEqual(bin_loc.code, 'A-01-01')
        self.assertFalse(bin_loc.is_occupied)
        self.assertEqual(str(bin_loc), 'Z-STR-01-A-01-01')


class PickOrderTest(TestCase):
    def test_auto_number(self):
        pick = PickOrder.objects.create()
        self.assertTrue(pick.pick_number.startswith('PK-'))

    def test_default_status(self):
        pick = PickOrder.objects.create()
        self.assertEqual(pick.status, 'PENDING')


class PutAwayTaskTest(TestCase):
    def setUp(self):
        self.product = Product.objects.create(name='테스트품목', code='TST-001')

    def test_putaway_creation(self):
        task = PutAwayTask.objects.create(
            product=self.product, quantity=100,
        )
        self.assertEqual(task.status, 'PENDING')
        self.assertEqual(task.quantity, 100)


class WavePlanTest(TestCase):
    def test_auto_number(self):
        wave = WavePlan.objects.create(name='오전 웨이브')
        self.assertTrue(wave.wave_number.startswith('WV-'))

    def test_default_status(self):
        wave = WavePlan.objects.create(name='테스트')
        self.assertEqual(wave.status, 'DRAFT')


# ── Signal Tests ────────────────────────────────────────────────


class PutAwayTaskSignalTest(TestCase):
    """PutAwayTask 완료 시그널 테스트"""

    def setUp(self):
        self.warehouse = Warehouse.objects.create(
            name='본사창고', code='WH-SIG-01', is_default=True,
        )
        self.zone = WarehouseZone.objects.create(
            warehouse=self.warehouse, name='보관구역', code='Z-SIG-01',
        )
        self.bin_loc = BinLocation.objects.create(
            zone=self.zone, code='B-SIG-01',
        )
        self.product = Product.objects.create(
            name='시그널테스트품목', code='SIG-001',
            current_stock=Decimal('0'),
        )

    def test_putaway_completed_creates_stock_movement(self):
        """입고적치 완료 시 IN StockMovement 생성"""
        task = PutAwayTask.objects.create(
            product=self.product,
            quantity=Decimal('50.000'),
            actual_bin=self.bin_loc,
            status='PENDING',
        )
        # 상태 변경 → COMPLETED
        task.status = 'COMPLETED'
        task.save()

        sm = StockMovement.objects.filter(
            product=self.product,
            movement_type='IN',
            reference__startswith='입고적치',
        ).first()
        self.assertIsNotNone(sm)
        self.assertEqual(sm.quantity, Decimal('50.000'))
        self.assertEqual(sm.warehouse, self.warehouse)

        # Product.current_stock 갱신 확인
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal('50.000'))

    def test_putaway_completed_marks_bin_occupied(self):
        """입고적치 완료 시 bin is_occupied=True"""
        task = PutAwayTask.objects.create(
            product=self.product,
            quantity=Decimal('10.000'),
            actual_bin=self.bin_loc,
            status='PENDING',
        )
        task.status = 'COMPLETED'
        task.save()

        self.bin_loc.refresh_from_db()
        self.assertTrue(self.bin_loc.is_occupied)

    def test_putaway_non_completed_no_movement(self):
        """COMPLETED가 아닌 상태 변경 시 재고이동 미생성"""
        task = PutAwayTask.objects.create(
            product=self.product,
            quantity=Decimal('10.000'),
            status='PENDING',
        )
        task.status = 'IN_PROGRESS'
        task.save()

        count = StockMovement.objects.filter(
            product=self.product,
            reference__startswith='입고적치',
        ).count()
        self.assertEqual(count, 0)


class PickOrderSignalTest(TestCase):
    """PickOrder 완료 시그널 테스트"""

    def setUp(self):
        self.warehouse = Warehouse.objects.create(
            name='본사창고', code='WH-PK-01', is_default=True,
        )
        self.zone = WarehouseZone.objects.create(
            warehouse=self.warehouse, name='피킹구역', code='Z-PK-01',
        )
        self.bin_loc = BinLocation.objects.create(
            zone=self.zone, code='B-PK-01',
        )
        self.product = Product.objects.create(
            name='피킹테스트품목', code='PK-001',
            current_stock=Decimal('100.000'),
        )

    def test_pickorder_packed_creates_out_movement(self):
        """피킹오더 PACKED 시 OUT StockMovement 생성"""
        pick = PickOrder.objects.create(status='PICKING')
        PickOrderItem.objects.create(
            pick_order=pick,
            product=self.product,
            bin_location=self.bin_loc,
            quantity=Decimal('20.000'),
            picked_qty=Decimal('20.000'),
        )

        pick.status = 'PACKED'
        pick.save()

        sm = StockMovement.objects.filter(
            product=self.product,
            movement_type='OUT',
            reference__startswith='피킹오더',
        ).first()
        self.assertIsNotNone(sm)
        self.assertEqual(sm.quantity, Decimal('20.000'))

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal('80.000'))

    def test_pickorder_pending_no_movement(self):
        """PENDING 상태에서는 재고이동 미생성"""
        pick = PickOrder.objects.create(status='PENDING')
        PickOrderItem.objects.create(
            pick_order=pick,
            product=self.product,
            bin_location=self.bin_loc,
            quantity=Decimal('10.000'),
        )

        count = StockMovement.objects.filter(
            product=self.product,
            reference__startswith='피킹오더',
        ).count()
        self.assertEqual(count, 0)

    def test_pickorder_uses_picked_qty(self):
        """picked_qty가 있으면 해당 수량으로 출고"""
        pick = PickOrder.objects.create(status='PICKING')
        PickOrderItem.objects.create(
            pick_order=pick,
            product=self.product,
            bin_location=self.bin_loc,
            quantity=Decimal('20.000'),
            picked_qty=Decimal('15.000'),
        )

        pick.status = 'PACKED'
        pick.save()

        sm = StockMovement.objects.filter(
            product=self.product,
            movement_type='OUT',
            reference__startswith='피킹오더',
        ).first()
        self.assertIsNotNone(sm)
        self.assertEqual(sm.quantity, Decimal('15.000'))


class WavePlanSignalTest(TestCase):
    """WavePlan 확정 시그널 테스트"""

    def test_waveplan_released_sets_picking_status(self):
        """웨이브 RELEASED 시 PENDING 피킹오더가 PICKING으로 전환"""
        pick1 = PickOrder.objects.create(status='PENDING')
        pick2 = PickOrder.objects.create(status='PENDING')
        pick3 = PickOrder.objects.create(status='CANCELLED')

        wave = WavePlan.objects.create(name='테스트 웨이브', status='DRAFT')
        wave.pick_orders.add(pick1, pick2, pick3)

        wave.status = 'RELEASED'
        wave.save()

        pick1.refresh_from_db()
        pick2.refresh_from_db()
        pick3.refresh_from_db()

        self.assertEqual(pick1.status, 'PICKING')
        self.assertEqual(pick2.status, 'PICKING')
        # CANCELLED는 변경 안 됨
        self.assertEqual(pick3.status, 'CANCELLED')

    def test_waveplan_draft_no_change(self):
        """DRAFT 상태에서는 피킹오더 변경 없음"""
        pick = PickOrder.objects.create(status='PENDING')
        wave = WavePlan.objects.create(name='테스트', status='DRAFT')
        wave.pick_orders.add(pick)

        wave.save()  # DRAFT 재저장

        pick.refresh_from_db()
        self.assertEqual(pick.status, 'PENDING')
