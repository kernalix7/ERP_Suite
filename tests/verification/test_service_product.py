"""
서비스/무형 상품 통합 테스트 (SVC-001 ~ SVC-003)
SERVICE/INTANGIBLE 유형 상품의 is_stockable=False 가드가
모든 비즈니스 흐름에서 정상 동작하는지 검증
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TransactionTestCase

from apps.inventory.models import (
    Product, StockLot, StockMovement, Warehouse, WarehouseStock,
)


class ServiceProductStockGuardTest(TransactionTestCase):
    """SVC-001: 서비스/무형 상품 재고 가드 — 입출고 시 재고 불변, LOT 미생성"""

    def setUp(self):
        self.product = Product.all_objects.create(
            code='SVC-P01', name='웹디자인서비스',
            product_type='SERVICE', unit_price=50000, cost_price=30000,
        )
        self.warehouse = Warehouse.all_objects.create(
            code='SVC-WH01', name='테스트창고',
        )

    def test_stock_movement_in_skips_stock_update(self):
        """SERVICE 상품에 IN StockMovement 생성 → current_stock=0 유지"""
        StockMovement.all_objects.create(
            movement_number='SVC-IN01',
            movement_type='IN',
            product=self.product,
            warehouse=self.warehouse,
            quantity=100,
            unit_price=50000,
            movement_date=date.today(),
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 0,
                         "서비스 상품 IN 입고 시 current_stock이 0이 아님")

    def test_stock_movement_out_skips_stock_update(self):
        """OUT StockMovement → current_stock=0 유지"""
        StockMovement.all_objects.create(
            movement_number='SVC-OUT01',
            movement_type='OUT',
            product=self.product,
            warehouse=self.warehouse,
            quantity=50,
            movement_date=date.today(),
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 0,
                         "서비스 상품 OUT 출고 시 current_stock이 0이 아님")

    def test_lot_not_created_for_service(self):
        """IN movement → StockLot 미생성"""
        StockMovement.all_objects.create(
            movement_number='SVC-IN02',
            movement_type='IN',
            product=self.product,
            warehouse=self.warehouse,
            quantity=100,
            unit_price=50000,
            movement_date=date.today(),
        )
        self.assertEqual(
            StockLot.objects.filter(product=self.product).count(), 0,
            "서비스 상품에 StockLot이 생성됨",
        )

    def test_warehouse_stock_not_updated(self):
        """IN movement → WarehouseStock 미갱신"""
        StockMovement.all_objects.create(
            movement_number='SVC-IN03',
            movement_type='IN',
            product=self.product,
            warehouse=self.warehouse,
            quantity=100,
            movement_date=date.today(),
        )
        self.assertEqual(
            WarehouseStock.objects.filter(product=self.product).count(), 0,
            "서비스 상품에 WarehouseStock이 생성됨",
        )

    def test_cost_price_not_updated(self):
        """IN with unit_price → cost_price 미변경"""
        original_cost = self.product.cost_price
        StockMovement.all_objects.create(
            movement_number='SVC-IN04',
            movement_type='IN',
            product=self.product,
            warehouse=self.warehouse,
            quantity=50,
            unit_price=999999,
            movement_date=date.today(),
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.cost_price, original_cost,
                         "서비스 상품의 cost_price가 입고에 의해 변경됨")

    def test_soft_delete_skips_stock_restore(self):
        """StockMovement soft delete 시 재고 복원 스킵"""
        mv = StockMovement.all_objects.create(
            movement_number='SVC-SD01',
            movement_type='IN',
            product=self.product,
            warehouse=self.warehouse,
            quantity=100,
            movement_date=date.today(),
        )
        mv.is_active = False
        mv.save(update_fields=['is_active', 'updated_at'])
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 0,
                         "서비스 상품 soft delete 시 재고가 변경됨")

    def test_intangible_also_skips(self):
        """INTANGIBLE 유형도 동일하게 재고 미추적"""
        intangible = Product.all_objects.create(
            code='INT-P01', name='소프트웨어라이선스',
            product_type='INTANGIBLE', unit_price=1000000,
        )
        StockMovement.all_objects.create(
            movement_number='INT-IN01',
            movement_type='IN',
            product=intangible,
            warehouse=self.warehouse,
            quantity=200,
            unit_price=1000000,
            movement_date=date.today(),
        )
        intangible.refresh_from_db()
        self.assertEqual(intangible.current_stock, 0,
                         "무형상품 입고 시 current_stock이 0이 아님")

    def test_finished_product_still_tracks_stock(self):
        """비교: FINISHED 완제품은 정상적으로 재고 변동"""
        finished = Product.all_objects.create(
            code='FIN-CMP01', name='비교용완제품',
            product_type='FINISHED', current_stock=0,
        )
        StockMovement.all_objects.create(
            movement_number='FIN-IN01',
            movement_type='IN',
            product=finished,
            warehouse=self.warehouse,
            quantity=100,
            movement_date=date.today(),
        )
        finished.refresh_from_db()
        self.assertEqual(finished.current_stock, 100,
                         "완제품 입고 시 재고가 100이 아님")


class ServiceProductOrderFlowTest(TransactionTestCase):
    """SVC-002: 서비스 상품 주문 전체 흐름 (확정→출고→배송→입금, 재고 무관)"""

    def setUp(self):
        from apps.sales.models import Order, OrderItem, Partner

        self.product = Product.all_objects.create(
            code='SVC-P01', name='웹디자인서비스',
            product_type='SERVICE', unit_price=50000, cost_price=30000,
        )
        self.warehouse = Warehouse.all_objects.create(
            code='SVC-ORD-WH', name='서비스창고', is_default=True,
        )
        self.partner = Partner.all_objects.create(
            code='SVC-CUST01', name='서비스거래처',
            partner_type='CUSTOMER',
        )
        self.order = Order.all_objects.create(
            order_number='SVC-ORD-001',
            partner=self.partner,
            order_date=date.today(),
            delivery_date=date.today() + timedelta(days=30),
            status='DRAFT',
            total_amount=250000,
            tax_total=25000,
            grand_total=275000,
        )
        self.order_item = OrderItem.all_objects.create(
            order=self.order,
            product=self.product,
            quantity=5,
            unit_price=50000,
        )

    def test_confirm_skips_reserved_stock(self):
        """CONFIRMED → reserved_stock=0 유지, AR/TaxInvoice는 생성됨"""
        from apps.accounting.models import AccountReceivable, TaxInvoice

        self.order.status = 'CONFIRMED'
        self.order.save()

        self.product.refresh_from_db()
        self.assertEqual(self.product.reserved_stock, 0,
                         "서비스 상품 주문확정 시 reserved_stock이 0이 아님")

        # AR은 서비스 상품이라도 정상 생성
        ar_count = AccountReceivable.objects.filter(
            order=self.order, is_active=True,
        ).count()
        self.assertEqual(ar_count, 1, "서비스 상품 주문확정 시 AR이 생성되지 않음")

        # TaxInvoice도 정상 생성
        ti_count = TaxInvoice.objects.filter(
            order=self.order, is_active=True,
        ).count()
        self.assertEqual(ti_count, 1,
                         "서비스 상품 주문확정 시 TaxInvoice가 생성되지 않음")

    def test_shipment_skips_stock_movement(self):
        """ShipmentItem → StockMovement 미생성, shipped_quantity는 갱신"""
        from apps.sales.models import Shipment, ShipmentItem

        self.order.status = 'CONFIRMED'
        self.order.save()

        shipment = Shipment.all_objects.create(
            order=self.order,
            shipment_number='SVC-SH-001',
            shipped_date=date.today(),
        )
        ShipmentItem.all_objects.create(
            shipment=shipment,
            order_item=self.order_item,
            quantity=3,
        )

        # StockMovement OUT 미생성
        out_count = StockMovement.objects.filter(
            product=self.product,
            movement_type='OUT',
            is_active=True,
        ).count()
        self.assertEqual(out_count, 0,
                         "서비스 상품에 OUT StockMovement가 생성됨")

        # shipped_quantity는 정상 갱신
        self.order_item.refresh_from_db()
        self.assertEqual(self.order_item.shipped_quantity, 3,
                         "서비스 상품 부분출고 시 shipped_quantity 미갱신")

        # current_stock, reserved_stock 불변
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 0)
        self.assertEqual(self.product.reserved_stock, 0)

    def test_full_lifecycle_no_stock_change(self):
        """확정→출고→배송→입금 전체 흐름, current_stock=0 유지"""
        from apps.accounting.models import AccountReceivable

        # 1. 확정
        self.order.status = 'CONFIRMED'
        self.order.save()
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 0)
        self.assertEqual(self.product.reserved_stock, 0)

        # 2. 출고완료
        self.order.status = 'SHIPPED'
        self.order.save()
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 0)

        # 3. 배송완료
        self.order.status = 'DELIVERED'
        self.order.save()
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 0)

        # AR은 생성되어 있어야 함
        ar = AccountReceivable.objects.filter(
            order=self.order, is_active=True,
        ).first()
        self.assertIsNotNone(ar, "전체 흐름에서 AR이 생성되지 않음")

    def test_cancel_no_stock_restore(self):
        """취소 시 reserved_stock 복원 스킵 (원래 0)"""
        self.order.status = 'CONFIRMED'
        self.order.save()

        self.order.status = 'CANCELLED'
        self.order.save()

        self.product.refresh_from_db()
        self.assertEqual(self.product.reserved_stock, 0,
                         "서비스 상품 주문취소 시 reserved_stock이 0이 아님")
        self.assertEqual(self.product.current_stock, 0,
                         "서비스 상품 주문취소 시 current_stock이 0이 아님")


class ServiceProductPurchaseTest(TransactionTestCase):
    """SVC-003: 서비스 상품 발주→입고 시 재고 불변"""

    def setUp(self):
        from apps.purchase.models import (
            GoodsReceipt, PurchaseOrder, PurchaseOrderItem,
        )
        from apps.sales.models import Partner

        self.product = Product.all_objects.create(
            code='SVC-P01', name='웹디자인서비스',
            product_type='SERVICE', unit_price=50000, cost_price=30000,
        )
        self.warehouse = Warehouse.all_objects.create(
            code='SVC-PUR-WH', name='서비스입고창고',
        )
        self.partner = Partner.all_objects.create(
            code='SVC-SUP01', name='서비스공급처',
            partner_type='SUPPLIER',
        )
        self.po = PurchaseOrder.all_objects.create(
            po_number='SVC-PO-001',
            partner=self.partner,
            order_date=date.today(),
            expected_date=date.today() + timedelta(days=30),
            status='CONFIRMED',
            total_amount=500000,
            tax_total=50000,
            grand_total=550000,
        )
        self.po_item = PurchaseOrderItem.all_objects.create(
            purchase_order=self.po,
            product=self.product,
            quantity=10,
            unit_price=50000,
            amount=500000,
            tax_amount=50000,
        )
        self.gr = GoodsReceipt.all_objects.create(
            receipt_number='SVC-GR-001',
            purchase_order=self.po,
            warehouse=self.warehouse,
            receipt_date=date.today(),
        )

    def test_goods_receipt_skips_stock_in(self):
        """입고 → StockMovement 미생성, current_stock=0 유지"""
        from apps.purchase.models import GoodsReceiptItem

        GoodsReceiptItem.all_objects.create(
            goods_receipt=self.gr,
            po_item=self.po_item,
            received_quantity=10,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 0,
                         "서비스 상품 발주입고 시 current_stock이 0이 아님")

        in_count = StockMovement.objects.filter(
            product=self.product,
            movement_type='IN',
            is_active=True,
        ).count()
        self.assertEqual(in_count, 0,
                         "서비스 상품에 IN StockMovement가 생성됨")

    def test_po_status_still_updates(self):
        """입고 → PO status는 정상 전환 (PARTIAL_RECEIVED/RECEIVED)"""
        from apps.purchase.models import GoodsReceiptItem, PurchaseOrder

        # 부분 입고
        GoodsReceiptItem.all_objects.create(
            goods_receipt=self.gr,
            po_item=self.po_item,
            received_quantity=5,
        )
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, PurchaseOrder.Status.PARTIAL_RECEIVED,
                         "서비스 상품 부분입고 시 PO 상태가 PARTIAL_RECEIVED 아님")

        # 나머지 입고 (별도 GR)
        from apps.purchase.models import GoodsReceipt
        gr2 = GoodsReceipt.all_objects.create(
            receipt_number='SVC-GR-002',
            purchase_order=self.po,
            warehouse=self.warehouse,
            receipt_date=date.today(),
        )
        GoodsReceiptItem.all_objects.create(
            goods_receipt=gr2,
            po_item=self.po_item,
            received_quantity=5,
        )
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, PurchaseOrder.Status.RECEIVED,
                         "서비스 상품 전량입고 시 PO 상태가 RECEIVED 아님")

        # current_stock은 여전히 0
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 0)

    def test_ap_still_created(self):
        """전량 입고 → AP/TaxInvoice 자동생성 (매입채무는 서비스에도 필요)"""
        from apps.accounting.models import AccountPayable, TaxInvoice
        from apps.purchase.models import GoodsReceiptItem

        GoodsReceiptItem.all_objects.create(
            goods_receipt=self.gr,
            po_item=self.po_item,
            received_quantity=10,
        )

        # AP 자동생성 확인
        ap_count = AccountPayable.objects.filter(
            partner=self.partner,
            is_active=True,
            notes__contains=self.po.po_number,
        ).count()
        self.assertEqual(ap_count, 1,
                         "서비스 상품 전량입고 시 AP가 생성되지 않음")

        # 매입 세금계산서 자동생성 확인
        ti_count = TaxInvoice.objects.filter(
            partner=self.partner,
            invoice_type='PURCHASE',
            is_active=True,
            description__contains=self.po.po_number,
        ).count()
        self.assertEqual(ti_count, 1,
                         "서비스 상품 전량입고 시 매입 TaxInvoice가 생성되지 않음")

        # current_stock은 여전히 0
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 0)

    def test_receipt_soft_delete_skips_stock_restore(self):
        """입고항목 soft delete 시 재고 복원 스킵"""
        from apps.purchase.models import GoodsReceiptItem

        gri = GoodsReceiptItem.all_objects.create(
            goods_receipt=self.gr,
            po_item=self.po_item,
            received_quantity=5,
        )
        gri.is_active = False
        gri.save(update_fields=['is_active', 'updated_at'])
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 0,
                         "서비스 상품 입고 soft delete 시 재고가 변경됨")

    def test_cost_price_unchanged_on_receipt(self):
        """발주입고 시 cost_price 미변경"""
        from apps.purchase.models import GoodsReceiptItem

        original_cost = self.product.cost_price
        GoodsReceiptItem.all_objects.create(
            goods_receipt=self.gr,
            po_item=self.po_item,
            received_quantity=10,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.cost_price, original_cost,
                         "서비스 상품의 cost_price가 발주입고에 의해 변경됨")
