from decimal import Decimal
from datetime import date, timedelta

from django.test import TestCase

from apps.accounts.models import User
from apps.inventory.models import Product, Warehouse, StockMovement
from apps.sales.models import Partner, Customer, Order, OrderItem


class OrderItemCalculationTest(TestCase):
    """주문항목 자동 계산 테스트 — OrderItem.save() 시 부가세 10% 자동 계산 검증"""

    def setUp(self):
        """테스트에 필요한 사용자, 제품, 주문 생성"""
        self.user = User.objects.create_user(
            username='sales_user', password='testpass123', role='staff',
        )
        self.product = Product.objects.create(
            code='PRD-SALE-001',
            name='판매제품',
            product_type='FINISHED',
            unit_price=10000,
            cost_price=7000,
            current_stock=100,
            created_by=self.user,
        )
        self.order = Order.objects.create(
            order_number='ORD-001',
            order_date=date.today(),
            status='DRAFT',
            created_by=self.user,
        )

    def test_order_item_auto_calculates_tax(self):
        """OrderItem 저장 시 공급가액, 부가세, 세포함 합계가 자동 계산되는지 확인"""
        item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=5,
            unit_price=10000,
            created_by=self.user,
        )
        # amount = 5 * 10000 = 50000
        self.assertEqual(item.amount, 50000)
        # tax_amount = int(50000 * 0.1) = 5000
        self.assertEqual(item.tax_amount, 5000)
        # total_with_tax = 50000 + 5000 = 55000
        self.assertEqual(item.total_with_tax, 55000)

    def test_order_update_total(self):
        """Order.update_total()이 모든 항목의 합계를 정확히 계산하는지 확인"""
        OrderItem.objects.create(
            order=self.order, product=self.product,
            quantity=2, unit_price=10000, created_by=self.user,
        )
        product_2 = Product.objects.create(
            code='PRD-SALE-002', name='판매제품2', product_type='FINISHED',
            unit_price=20000, cost_price=15000, created_by=self.user,
        )
        OrderItem.objects.create(
            order=self.order, product=product_2,
            quantity=3, unit_price=20000, created_by=self.user,
        )

        self.order.update_total()
        self.order.refresh_from_db()

        # item1: amount=20000, tax=2000
        # item2: amount=60000, tax=6000
        self.assertEqual(self.order.total_amount, 80000)
        self.assertEqual(self.order.tax_total, 8000)
        self.assertEqual(self.order.grand_total, 88000)


class OrderShipSignalTest(TestCase):
    """주문 출고 시그널 테스트 — 주문 상태가 SHIPPED로 변경될 때 재고 자동 출고 검증"""

    def setUp(self):
        """테스트에 필요한 사용자, 창고, 제품, 주문, 주문항목 생성"""
        self.user = User.objects.create_user(
            username='ship_user', password='testpass123', role='staff',
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-SHIP', name='출고창고', created_by=self.user,
        )
        self.product_a = Product.objects.create(
            code='PRD-SHIP-A', name='출고제품A', product_type='FINISHED',
            unit_price=10000, cost_price=7000, current_stock=100,
            created_by=self.user,
        )
        self.product_b = Product.objects.create(
            code='PRD-SHIP-B', name='출고제품B', product_type='FINISHED',
            unit_price=20000, cost_price=12000, current_stock=200,
            created_by=self.user,
        )
        self.order = Order.objects.create(
            order_number='ORD-SHIP-001',
            order_date=date.today(),
            status='CONFIRMED',
            created_by=self.user,
        )
        self.item_a = OrderItem.objects.create(
            order=self.order, product=self.product_a,
            quantity=5, unit_price=10000, created_by=self.user,
        )
        self.item_b = OrderItem.objects.create(
            order=self.order, product=self.product_b,
            quantity=3, unit_price=20000, created_by=self.user,
        )

    def test_shipped_creates_stock_out(self):
        """주문 상태를 SHIPPED로 변경하면 각 주문항목별 OUT 전표가 생성되는지 확인"""
        self.order.status = 'SHIPPED'
        self.order.save()

        out_movements = StockMovement.objects.filter(movement_type='OUT')
        self.assertEqual(out_movements.count(), 2)

        mv_a = out_movements.get(product=self.product_a)
        self.assertEqual(mv_a.quantity, 5)

        mv_b = out_movements.get(product=self.product_b)
        self.assertEqual(mv_b.quantity, 3)

        # 재고 감소 확인
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.current_stock, 95)

        self.product_b.refresh_from_db()
        self.assertEqual(self.product_b.current_stock, 197)

    def test_no_stock_out_when_status_unchanged(self):
        """상태가 변경되지 않으면 출고 전표가 생성되지 않는지 확인"""
        # CONFIRMED → CONFIRMED (변경 없음)
        self.order.status = 'CONFIRMED'
        self.order.save()

        out_movements = StockMovement.objects.filter(movement_type='OUT')
        self.assertEqual(out_movements.count(), 0)

    def test_no_stock_out_on_new_order(self):
        """새 주문 생성 시에는 SHIPPED 상태여도 출고 전표가 생성되지 않는지 확인"""
        new_order = Order.objects.create(
            order_number='ORD-SHIP-NEW',
            order_date=date.today(),
            status='SHIPPED',
            created_by=self.user,
        )
        out_movements = StockMovement.objects.filter(
            movement_type='OUT',
            reference__contains=new_order.order_number,
        )
        self.assertEqual(out_movements.count(), 0)

    def test_no_duplicate_stock_out_on_save_again(self):
        """이미 SHIPPED인 주문을 다시 저장해도 중복 출고가 생기지 않는지 확인"""
        self.order.status = 'SHIPPED'
        self.order.save()

        initial_count = StockMovement.objects.filter(movement_type='OUT').count()

        # 같은 주문을 다시 저장 (SHIPPED → SHIPPED)
        self.order.save()
        after_count = StockMovement.objects.filter(movement_type='OUT').count()

        self.assertEqual(initial_count, after_count)

    def test_shipped_from_draft(self):
        """DRAFT 상태에서 바로 SHIPPED로 변경해도 출고 전표가 생성되는지 확인"""
        draft_order = Order.objects.create(
            order_number='ORD-SHIP-DRAFT',
            order_date=date.today(),
            status='DRAFT',
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=draft_order, product=self.product_a,
            quantity=2, unit_price=10000, created_by=self.user,
        )

        draft_order.status = 'SHIPPED'
        draft_order.save()

        out_movements = StockMovement.objects.filter(
            movement_type='OUT',
            reference__contains=draft_order.order_number,
        )
        self.assertEqual(out_movements.count(), 1)
        self.assertEqual(out_movements.first().quantity, 2)


class CustomerWarrantyTest(TestCase):
    """고객 보증기간 테스트 — Customer.is_warranty_valid 프로퍼티 검증"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='warranty_user', password='testpass123',
        )

    def test_customer_warranty_valid(self):
        """보증만료일이 오늘 이후이면 is_warranty_valid가 True인지 확인"""
        customer = Customer.objects.create(
            name='유효고객',
            phone='010-1234-5678',
            warranty_end=date.today() + timedelta(days=30),
            created_by=self.user,
        )
        self.assertTrue(customer.is_warranty_valid)

    def test_customer_warranty_expired(self):
        """보증만료일이 오늘 이전이면 is_warranty_valid가 False인지 확인"""
        customer = Customer.objects.create(
            name='만료고객',
            phone='010-9876-5432',
            warranty_end=date.today() - timedelta(days=1),
            created_by=self.user,
        )
        self.assertFalse(customer.is_warranty_valid)

    def test_customer_warranty_today(self):
        """보증만료일이 오늘이면 is_warranty_valid가 True인지 확인 (경계값)"""
        customer = Customer.objects.create(
            name='오늘만료고객',
            phone='010-0000-0000',
            warranty_end=date.today(),
            created_by=self.user,
        )
        self.assertTrue(customer.is_warranty_valid)

    def test_customer_warranty_null(self):
        """보증만료일이 없으면 is_warranty_valid가 False인지 확인"""
        customer = Customer.objects.create(
            name='보증없는고객',
            phone='010-1111-1111',
            created_by=self.user,
        )
        self.assertFalse(customer.is_warranty_valid)
