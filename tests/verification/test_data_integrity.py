"""
데이터 무결성 검증 테스트 (INT-001 ~ INT-010)
재고 정합성, 금액 계산, 복식부기 균형, BOM 소요량 등 데이터 무결성 자동화 테스트
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import TestCase

User = get_user_model()


class INT001_StockConsistencyTest(TestCase):
    """INT-001: 재고 정합성 - 입출고 합계 = 현재고"""

    def setUp(self):
        from apps.inventory.models import Product, Warehouse
        self.product = Product.all_objects.create(
            code='INT001-P1', name='재고테스트제품',
            product_type='FINISHED', current_stock=0,
        )
        self.warehouse = Warehouse.all_objects.create(
            code='INT001-WH', name='테스트창고',
        )

    def test_입고시_재고증가(self):
        """입고(IN) 시 current_stock이 증가"""
        from apps.inventory.models import StockMovement
        StockMovement.all_objects.create(
            movement_number='INT001-MV01',
            movement_type='IN',
            product=self.product,
            warehouse=self.warehouse,
            quantity=100,
            movement_date=date.today(),
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 100,
                         "입고 후 재고가 100이 아님")

    def test_출고시_재고감소(self):
        """출고(OUT) 시 current_stock이 감소"""
        from apps.inventory.models import StockMovement
        # 먼저 입고
        StockMovement.all_objects.create(
            movement_number='INT001-MV02',
            movement_type='IN',
            product=self.product,
            warehouse=self.warehouse,
            quantity=50,
            movement_date=date.today(),
        )
        # 출고
        StockMovement.all_objects.create(
            movement_number='INT001-MV03',
            movement_type='OUT',
            product=self.product,
            warehouse=self.warehouse,
            quantity=30,
            movement_date=date.today(),
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 20,
                         "입고50 - 출고30 = 재고20이 아님")

    def test_다중입출고_합산_정합성(self):
        """여러 입출고 후 현재고가 합산 결과와 일치"""
        from apps.inventory.models import StockMovement
        movements = [
            ('INT001-M1', 'IN', 200),
            ('INT001-M2', 'IN', 150),
            ('INT001-M3', 'OUT', 80),
            ('INT001-M4', 'ADJ_PLUS', 30),
            ('INT001-M5', 'ADJ_MINUS', 20),
            ('INT001-M6', 'PROD_IN', 50),
            ('INT001-M7', 'PROD_OUT', 40),
            ('INT001-M8', 'RETURN', 10),
        ]
        for num, mtype, qty in movements:
            StockMovement.all_objects.create(
                movement_number=num,
                movement_type=mtype,
                product=self.product,
                warehouse=self.warehouse,
                quantity=qty,
                movement_date=date.today(),
            )
        # 예상: (200+150+30+50+10) - (80+20+40) = 440 - 140 = 300
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 300,
                         f"예상 재고 300 != 실제 재고 {self.product.current_stock}")

    def test_생산입고_PROD_IN_반영(self):
        """PROD_IN 유형 입출고가 재고에 정확히 반영"""
        from apps.inventory.models import StockMovement
        StockMovement.all_objects.create(
            movement_number='INT001-PI1',
            movement_type='PROD_IN',
            product=self.product,
            warehouse=self.warehouse,
            quantity=75,
            movement_date=date.today(),
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 75)


class INT002_OrderAmountCalculationTest(TestCase):
    """INT-002: 주문 금액 계산 - 수량x단가 = 공급가액, VAT 10%"""

    def setUp(self):
        from apps.inventory.models import Product
        from apps.sales.models import Partner, Order
        self.product = Product.all_objects.create(
            code='INT002-P1', name='금액테스트', unit_price=10000,
        )
        self.partner = Partner.all_objects.create(
            code='INT002-PT', name='테스트거래처',
        )
        self.order = Order.all_objects.create(
            order_number='INT002-ORD01',
            partner=self.partner,
            order_date=date.today(),
            status='DRAFT',
        )

    def test_주문항목_금액자동계산(self):
        """OrderItem 저장 시 amount와 tax_amount가 자동 계산"""
        from apps.sales.models import OrderItem
        item = OrderItem.all_objects.create(
            order=self.order,
            product=self.product,
            quantity=5,
            unit_price=Decimal('10000'),
        )
        self.assertEqual(item.amount, Decimal('50000'),
                         "공급가액 = 5 x 10000 = 50000이 아님")
        self.assertEqual(item.tax_amount, Decimal('5000'),
                         "부가세 = 50000 x 0.1 = 5000이 아님")
        self.assertEqual(item.total_with_tax, Decimal('55000'),
                         "합계(세포함) = 55000이 아님")

    def test_주문합계_항목합계_일치(self):
        """Order.update_total() 후 주문 합계와 항목 합계가 일치"""
        from apps.sales.models import OrderItem
        OrderItem.all_objects.create(
            order=self.order, product=self.product,
            quantity=3, unit_price=Decimal('20000'),
        )
        product2 = self._create_product('INT002-P2', '제품2', 15000)
        OrderItem.all_objects.create(
            order=self.order, product=product2,
            quantity=2, unit_price=Decimal('15000'),
        )

        self.order.update_total()
        # 항목1: 60000 + 6000 = 66000
        # 항목2: 30000 + 3000 = 33000
        self.assertEqual(self.order.total_amount, Decimal('90000'))
        self.assertEqual(self.order.tax_total, Decimal('9000'))
        self.assertEqual(self.order.grand_total, Decimal('99000'))

    def test_VAT_10퍼센트_정확도(self):
        """부가세가 정확히 10%로 계산 (절삭 확인)"""
        from apps.sales.models import OrderItem
        item = OrderItem.all_objects.create(
            order=self.order, product=self.product,
            quantity=1, unit_price=Decimal('33333'),
        )
        # 33333 * 0.1 = 3333.3 -> int() = 3333
        self.assertEqual(item.tax_amount, Decimal('3333'))

    def _create_product(self, code, name, price):
        from apps.inventory.models import Product
        return Product.all_objects.create(
            code=code, name=name, unit_price=price,
        )


class INT003_DoubleEntryBalanceTest(TestCase):
    """INT-003: 복식부기 균형 - 차변 합 = 대변 합"""

    def setUp(self):
        from apps.accounting.models import AccountCode, Voucher
        self.account_cash = AccountCode.all_objects.create(
            code='INT003-101', name='현금', account_type='ASSET',
        )
        self.account_revenue = AccountCode.all_objects.create(
            code='INT003-401', name='매출', account_type='REVENUE',
        )
        self.voucher = Voucher.all_objects.create(
            voucher_number='INT003-V01',
            voucher_type='RECEIPT',
            voucher_date=date.today(),
            description='복식부기 테스트',
        )

    def test_균형전표_is_balanced_True(self):
        """차변=대변인 전표에서 is_balanced=True"""
        from apps.accounting.models import VoucherLine
        VoucherLine.all_objects.create(
            voucher=self.voucher,
            account=self.account_cash,
            debit=Decimal('100000'), credit=Decimal('0'),
        )
        VoucherLine.all_objects.create(
            voucher=self.voucher,
            account=self.account_revenue,
            debit=Decimal('0'), credit=Decimal('100000'),
        )
        self.assertTrue(self.voucher.is_balanced,
                        "차변=대변인데 is_balanced=False")

    def test_불균형전표_is_balanced_False(self):
        """차변!=대변인 전표에서 is_balanced=False"""
        from apps.accounting.models import VoucherLine
        VoucherLine.all_objects.create(
            voucher=self.voucher,
            account=self.account_cash,
            debit=Decimal('100000'), credit=Decimal('0'),
        )
        VoucherLine.all_objects.create(
            voucher=self.voucher,
            account=self.account_revenue,
            debit=Decimal('0'), credit=Decimal('50000'),
        )
        self.assertFalse(self.voucher.is_balanced,
                         "차변!=대변인데 is_balanced=True")

    def test_전표_차대변합계(self):
        """total_debit, total_credit 프로퍼티 정확도"""
        from apps.accounting.models import VoucherLine
        VoucherLine.all_objects.create(
            voucher=self.voucher,
            account=self.account_cash,
            debit=Decimal('50000'), credit=Decimal('0'),
        )
        VoucherLine.all_objects.create(
            voucher=self.voucher,
            account=self.account_cash,
            debit=Decimal('30000'), credit=Decimal('0'),
        )
        VoucherLine.all_objects.create(
            voucher=self.voucher,
            account=self.account_revenue,
            debit=Decimal('0'), credit=Decimal('80000'),
        )
        self.assertEqual(self.voucher.total_debit, Decimal('80000'))
        self.assertEqual(self.voucher.total_credit, Decimal('80000'))


class INT004_BOMEffectiveQuantityTest(TestCase):
    """INT-004: BOM 소요량 계산 - 손실률 반영"""

    def setUp(self):
        from apps.inventory.models import Product
        from apps.production.models import BOM
        self.finished = Product.all_objects.create(
            code='INT004-FIN', name='완제품', product_type='FINISHED',
            cost_price=50000,
        )
        self.raw = Product.all_objects.create(
            code='INT004-RAW', name='원자재', product_type='RAW',
            cost_price=5000,
        )
        self.bom = BOM.all_objects.create(
            product=self.finished, version='1.0',
        )

    def test_손실률_0퍼센트(self):
        """손실률 0%일 때 effective_quantity == quantity"""
        from apps.production.models import BOMItem
        item = BOMItem.all_objects.create(
            bom=self.bom, material=self.raw,
            quantity=Decimal('10.000'), loss_rate=Decimal('0.00'),
        )
        self.assertEqual(item.effective_quantity, Decimal('10.000'))

    def test_손실률_10퍼센트(self):
        """손실률 10%일 때 effective_quantity = quantity x 1.1"""
        from apps.production.models import BOMItem
        item = BOMItem.all_objects.create(
            bom=self.bom, material=self.raw,
            quantity=Decimal('10.000'), loss_rate=Decimal('10.00'),
        )
        expected = Decimal('10.000') * Decimal('1.10')
        self.assertEqual(item.effective_quantity, expected,
                         f"손실률 10% 반영 실패: 예상 {expected}, 실제 {item.effective_quantity}")

    def test_손실률_5_5퍼센트(self):
        """손실률 5.5%에서 소수점 정확도"""
        from apps.production.models import BOMItem
        item = BOMItem.all_objects.create(
            bom=self.bom, material=self.raw,
            quantity=Decimal('20.000'), loss_rate=Decimal('5.50'),
        )
        expected = Decimal('20.000') * (1 + Decimal('5.50') / 100)
        self.assertEqual(item.effective_quantity, expected)

    def test_material_cost_계산(self):
        """material_cost = effective_quantity x cost_price"""
        from apps.production.models import BOMItem
        item = BOMItem.all_objects.create(
            bom=self.bom, material=self.raw,
            quantity=Decimal('10.000'), loss_rate=Decimal('10.00'),
        )
        # effective_quantity = 11.0, cost_price = 5000
        # material_cost = int(11.0 * 5000) = 55000
        self.assertEqual(item.material_cost, 55000)


class INT005_ProductionAutoStockTest(TestCase):
    """INT-005: 생산 자동 재고 반영 - PROD_IN + PROD_OUT"""

    def setUp(self):
        from apps.inventory.models import Product, Warehouse
        from apps.production.models import BOM, BOMItem, ProductionPlan, WorkOrder

        self.warehouse = Warehouse.all_objects.create(
            code='INT005-WH', name='생산창고',
        )
        self.finished = Product.all_objects.create(
            code='INT005-FIN', name='완제품', product_type='FINISHED',
            cost_price=50000, current_stock=0,
        )
        self.raw = Product.all_objects.create(
            code='INT005-RAW', name='원자재', product_type='RAW',
            cost_price=5000, current_stock=1000,
        )
        self.bom = BOM.all_objects.create(
            product=self.finished, version='1.0',
        )
        BOMItem.all_objects.create(
            bom=self.bom, material=self.raw,
            quantity=Decimal('2.000'), loss_rate=Decimal('0.00'),
        )
        self.plan = ProductionPlan.all_objects.create(
            plan_number='INT005-PL01',
            product=self.finished,
            bom=self.bom,
            planned_quantity=10,
            planned_start=date.today(),
            planned_end=date.today(),
            status='IN_PROGRESS',
        )
        self.workorder = WorkOrder.all_objects.create(
            order_number='INT005-WO01',
            production_plan=self.plan,
            quantity=10,
            status='IN_PROGRESS',
        )

    def test_생산실적_완제품_입고(self):
        """생산실적 등록 시 완제품 PROD_IN 자동 생성"""
        from apps.inventory.models import StockMovement
        from apps.production.models import ProductionRecord

        before_count = StockMovement.all_objects.filter(
            movement_type='PROD_IN', product=self.finished,
        ).count()

        ProductionRecord.all_objects.create(
            work_order=self.workorder,
            good_quantity=5,
            defect_quantity=0,
            record_date=date.today(),
        )

        after_count = StockMovement.all_objects.filter(
            movement_type='PROD_IN', product=self.finished,
        ).count()
        self.assertEqual(after_count, before_count + 1,
                         "생산실적 등록 후 PROD_IN 전표 미생성")

        self.finished.refresh_from_db()
        self.assertEqual(self.finished.current_stock, 5,
                         "완제품 재고가 5 증가하지 않음")

    def test_생산실적_원자재_출고(self):
        """생산실적 등록 시 BOM 기반 원자재 PROD_OUT 자동 생성"""
        from apps.inventory.models import StockMovement
        from apps.production.models import ProductionRecord

        ProductionRecord.all_objects.create(
            work_order=self.workorder,
            good_quantity=5,
            defect_quantity=0,
            record_date=date.today(),
        )

        # 원자재 BOM: 2 x 5 = 10 출고
        prod_outs = StockMovement.all_objects.filter(
            movement_type='PROD_OUT', product=self.raw,
        )
        self.assertEqual(prod_outs.count(), 1,
                         "원자재 PROD_OUT 전표 미생성")

        self.raw.refresh_from_db()
        self.assertEqual(self.raw.current_stock, 990,
                         "원자재 재고가 10 감소하지 않음 (1000 - 10 = 990)")


class INT006_ShipmentAutoStockTest(TestCase):
    """INT-006: 출하 자동 재고 반영 - SHIPPED -> OUT"""

    def setUp(self):
        from apps.inventory.models import Product, Warehouse
        from apps.sales.models import Partner, Order, OrderItem

        self.warehouse = Warehouse.all_objects.create(
            code='INT006-WH', name='출하창고',
        )
        self.product = Product.all_objects.create(
            code='INT006-P1', name='출하제품', current_stock=100,
            unit_price=10000,
        )
        self.partner = Partner.all_objects.create(
            code='INT006-PT', name='출하거래처',
        )
        self.order = Order.all_objects.create(
            order_number='INT006-ORD01',
            partner=self.partner,
            order_date=date.today(),
            status='CONFIRMED',
        )
        OrderItem.all_objects.create(
            order=self.order,
            product=self.product,
            quantity=20,
            unit_price=Decimal('10000'),
        )

    def test_SHIPPED_상태변경시_OUT전표_자동생성(self):
        """주문 상태를 SHIPPED로 변경 시 OUT 전표 자동 생성"""
        from apps.inventory.models import StockMovement

        before_count = StockMovement.all_objects.filter(
            movement_type='OUT', product=self.product,
        ).count()

        self.order.status = 'SHIPPED'
        self.order.save()

        after_count = StockMovement.all_objects.filter(
            movement_type='OUT', product=self.product,
        ).count()
        self.assertEqual(after_count, before_count + 1,
                         "SHIPPED 변경 후 OUT 전표 미생성")

    def test_SHIPPED시_재고감소(self):
        """주문 출고완료 시 해당 수량만큼 재고 감소"""
        self.order.status = 'SHIPPED'
        self.order.save()

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 80,
                         f"예상 재고 80 != 실제 {self.product.current_stock}")


class INT007_AccountReceivableTest(TestCase):
    """INT-007: 미수금 정합성 - 청구액 = 입금액 + 잔액"""

    def setUp(self):
        from apps.sales.models import Partner
        from apps.accounting.models import AccountReceivable
        self.partner = Partner.all_objects.create(
            code='INT007-PT', name='미수금거래처',
        )
        self.ar = AccountReceivable.all_objects.create(
            partner=self.partner,
            amount=Decimal('1000000'),
            paid_amount=Decimal('300000'),
            due_date=date.today(),
            status='PARTIAL',
        )

    def test_잔액계산_정확도(self):
        """remaining_amount = amount - paid_amount"""
        self.assertEqual(
            self.ar.remaining_amount, Decimal('700000'),
            "잔액 = 1000000 - 300000 = 700000이 아님",
        )

    def test_전액입금시_잔액0(self):
        """전액 입금 시 잔액 = 0"""
        self.ar.paid_amount = Decimal('1000000')
        self.ar.save()
        self.assertEqual(self.ar.remaining_amount, Decimal('0'))

    def test_미입금시_잔액_전액(self):
        """미입금 시 잔액 = 청구액"""
        from apps.accounting.models import AccountReceivable
        ar_new = AccountReceivable.all_objects.create(
            partner=self.partner,
            amount=Decimal('500000'),
            paid_amount=Decimal('0'),
            due_date=date.today(),
            status='PENDING',
        )
        self.assertEqual(ar_new.remaining_amount, Decimal('500000'))


class INT008_SoftDeleteTest(TestCase):
    """INT-008: 소프트 삭제 정합성 - ActiveManager 필터링"""

    def test_soft_delete후_기본쿼리_제외(self):
        """soft_delete() 후 objects.all()에서 제외"""
        from apps.inventory.models import Product
        product = Product.all_objects.create(
            code='INT008-P1', name='삭제테스트',
        )
        self.assertEqual(Product.objects.filter(code='INT008-P1').count(), 1)

        product.soft_delete()

        self.assertEqual(
            Product.objects.filter(code='INT008-P1').count(), 0,
            "soft_delete 후 기본 쿼리에서 제외되지 않음",
        )

    def test_soft_delete후_all_objects_조회가능(self):
        """soft_delete() 후 all_objects로는 조회 가능"""
        from apps.inventory.models import Product
        product = Product.all_objects.create(
            code='INT008-P2', name='삭제테스트2',
        )
        product.soft_delete()

        self.assertEqual(
            Product.all_objects.filter(code='INT008-P2').count(), 1,
            "soft_delete 후 all_objects에서도 조회 불가",
        )

    def test_soft_delete시_is_active_False(self):
        """soft_delete 호출 시 is_active=False로 변경"""
        from apps.inventory.models import Product
        product = Product.all_objects.create(
            code='INT008-P3', name='삭제테스트3',
        )
        product.soft_delete()
        product.refresh_from_db()
        self.assertFalse(product.is_active)


class INT009_UniqueConstraintTest(TestCase):
    """INT-009: unique 제약조건 검증"""

    def test_Product_code_중복방지(self):
        """Product.code unique 제약조건 검증"""
        from apps.inventory.models import Product
        Product.all_objects.create(code='INT009-UNQ', name='유니크테스트')
        with self.assertRaises(IntegrityError):
            Product.all_objects.create(code='INT009-UNQ', name='중복시도')

    def test_Order_order_number_중복방지(self):
        """Order.order_number unique 제약조건 검증"""
        from apps.sales.models import Order
        Order.all_objects.create(
            order_number='INT009-ORD', order_date=date.today(),
        )
        with self.assertRaises(IntegrityError):
            Order.all_objects.create(
                order_number='INT009-ORD', order_date=date.today(),
            )

    def test_Voucher_voucher_number_중복방지(self):
        """Voucher.voucher_number unique 제약조건 검증"""
        from apps.accounting.models import Voucher
        Voucher.all_objects.create(
            voucher_number='INT009-V01',
            voucher_type='RECEIPT',
            voucher_date=date.today(),
            description='유니크 테스트',
        )
        with self.assertRaises(IntegrityError):
            Voucher.all_objects.create(
                voucher_number='INT009-V01',
                voucher_type='PAYMENT',
                voucher_date=date.today(),
                description='중복 시도',
            )

    def test_Warehouse_code_중복방지(self):
        """Warehouse.code unique 제약조건 검증"""
        from apps.inventory.models import Warehouse
        Warehouse.all_objects.create(code='INT009-WH', name='창고1')
        with self.assertRaises(IntegrityError):
            Warehouse.all_objects.create(code='INT009-WH', name='창고2')


class INT010_FKReferentialIntegrityTest(TestCase):
    """INT-010: FK 참조 무결성 - PROTECT 동작 검증"""

    def test_StockMovement_참조_Product_삭제불가(self):
        """StockMovement가 참조하는 Product는 삭제 불가 (PROTECT)"""
        from apps.inventory.models import Product, Warehouse, StockMovement
        product = Product.all_objects.create(
            code='INT010-P1', name='참조테스트',
        )
        warehouse = Warehouse.all_objects.create(
            code='INT010-WH', name='참조창고',
        )
        StockMovement.all_objects.create(
            movement_number='INT010-MV01',
            movement_type='IN',
            product=product,
            warehouse=warehouse,
            quantity=10,
            movement_date=date.today(),
        )
        with self.assertRaises(ProtectedError):
            product.delete()

    def test_OrderItem_참조_Product_삭제불가(self):
        """OrderItem이 참조하는 Product는 삭제 불가 (PROTECT)"""
        from apps.inventory.models import Product
        from apps.sales.models import Order, OrderItem
        product = Product.all_objects.create(
            code='INT010-P2', name='주문참조테스트',
        )
        order = Order.all_objects.create(
            order_number='INT010-ORD01', order_date=date.today(),
        )
        OrderItem.all_objects.create(
            order=order, product=product,
            quantity=1, unit_price=Decimal('10000'),
        )
        with self.assertRaises(ProtectedError):
            product.delete()

    def test_VoucherLine_참조_AccountCode_삭제불가(self):
        """VoucherLine이 참조하는 AccountCode는 삭제 불가 (PROTECT)"""
        from apps.accounting.models import AccountCode, Voucher, VoucherLine
        account = AccountCode.all_objects.create(
            code='INT010-ACC', name='참조계정', account_type='ASSET',
        )
        voucher = Voucher.all_objects.create(
            voucher_number='INT010-V01',
            voucher_type='RECEIPT',
            voucher_date=date.today(),
            description='FK 테스트',
        )
        VoucherLine.all_objects.create(
            voucher=voucher, account=account,
            debit=Decimal('10000'), credit=Decimal('0'),
        )
        with self.assertRaises(ProtectedError):
            account.delete()

    def test_StockMovement_참조_Warehouse_삭제불가(self):
        """StockMovement가 참조하는 Warehouse는 삭제 불가 (PROTECT)"""
        from apps.inventory.models import Product, Warehouse, StockMovement
        product = Product.all_objects.create(
            code='INT010-P3', name='창고참조테스트',
        )
        warehouse = Warehouse.all_objects.create(
            code='INT010-WH2', name='참조창고2',
        )
        StockMovement.all_objects.create(
            movement_number='INT010-MV02',
            movement_type='IN',
            product=product,
            warehouse=warehouse,
            quantity=5,
            movement_date=date.today(),
        )
        with self.assertRaises(ProtectedError):
            warehouse.delete()
