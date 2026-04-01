from decimal import Decimal
from datetime import date, timedelta

from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.models import User
from apps.inventory.models import Product, Warehouse, StockMovement
from apps.sales.models import (
    Partner, Customer, CustomerPurchase, Order, OrderItem,
    Quotation, QuotationItem, Shipment, ShippingCarrier,
)
from apps.sales.commission import CommissionRate, CommissionRecord


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

        out_qs = StockMovement.objects.filter(movement_type='OUT')
        initial_count = out_qs.count()

        # 같은 주문을 다시 저장 (SHIPPED → SHIPPED)
        self.order.save()
        after_count = out_qs.count()

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


class CustomerPurchaseWarrantyTest(TestCase):
    """고객 구매내역 보증기간 테스트 — CustomerPurchase.is_warranty_valid 프로퍼티 검증"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='warranty_user', password='testpass123',
        )
        self.customer = Customer.objects.create(
            code='CUST-TEST', name='테스트고객', phone='010-1234-5678',
            created_by=self.user,
        )
        self.product = Product.objects.create(
            code='TEST-001', name='테스트제품',
            unit_price=10000, created_by=self.user,
        )

    def test_purchase_warranty_valid(self):
        """보증만료일이 오늘 이후이면 is_warranty_valid가 True인지 확인"""
        purchase = CustomerPurchase.objects.create(
            customer=self.customer, product=self.product,
            warranty_end=date.today() + timedelta(days=30),
            created_by=self.user,
        )
        self.assertTrue(purchase.is_warranty_valid)

    def test_purchase_warranty_expired(self):
        """보증만료일이 오늘 이전이면 is_warranty_valid가 False인지 확인"""
        purchase = CustomerPurchase.objects.create(
            customer=self.customer, product=self.product,
            warranty_end=date.today() - timedelta(days=1),
            created_by=self.user,
        )
        self.assertFalse(purchase.is_warranty_valid)

    def test_purchase_warranty_today(self):
        """보증만료일이 오늘이면 is_warranty_valid가 True인지 확인 (경계값)"""
        purchase = CustomerPurchase.objects.create(
            customer=self.customer, product=self.product,
            warranty_end=date.today(),
            created_by=self.user,
        )
        self.assertTrue(purchase.is_warranty_valid)

    def test_purchase_warranty_null(self):
        """보증만료일이 없으면 is_warranty_valid가 False인지 확인"""
        purchase = CustomerPurchase.objects.create(
            customer=self.customer, product=self.product,
            created_by=self.user,
        )
        self.assertFalse(purchase.is_warranty_valid)


class PartnerModelTest(TestCase):
    """거래처 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='partneruser', password='testpass123',
            role='staff',
        )

    def test_partner_creation(self):
        """거래처 생성"""
        partner = Partner.objects.create(
            code='PT-001', name='테스트거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
            created_by=self.user,
        )
        self.assertEqual(partner.code, 'PT-001')
        self.assertEqual(partner.name, '테스트거래처')

    def test_partner_str(self):
        """거래처 문자열 표현"""
        partner = Partner.objects.create(
            code='PT-STR', name='문자열거래처',
            partner_type=Partner.PartnerType.SUPPLIER,
            created_by=self.user,
        )
        self.assertEqual(str(partner), '문자열거래처')

    def test_partner_unique_code(self):
        """거래처코드 중복 불가"""
        Partner.objects.create(
            code='PT-DUP', name='거래처1',
            partner_type=Partner.PartnerType.CUSTOMER,
            created_by=self.user,
        )
        with self.assertRaises(IntegrityError):
            Partner.objects.create(
                code='PT-DUP', name='거래처2',
                partner_type=Partner.PartnerType.SUPPLIER,
                created_by=self.user,
            )

    def test_partner_type_choices(self):
        """거래처 유형 선택지"""
        choices = dict(Partner.PartnerType.choices)
        self.assertIn('CUSTOMER', choices)
        self.assertIn('SUPPLIER', choices)
        self.assertIn('BOTH', choices)

    def test_partner_soft_delete(self):
        """거래처 soft delete"""
        partner = Partner.objects.create(
            code='PT-SD', name='삭제거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
            created_by=self.user,
        )
        partner.soft_delete()
        self.assertFalse(
            Partner.objects.filter(pk=partner.pk).exists()
        )
        self.assertTrue(
            Partner.all_objects.filter(pk=partner.pk).exists()
        )


class QuotationModelTest(TestCase):
    """견적서 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='quoteuser', password='testpass123',
            role='staff',
        )
        self.partner = Partner.objects.create(
            code='QT-P001', name='견적거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
            created_by=self.user,
        )
        self.product = Product.objects.create(
            code='QT-PRD-001', name='견적제품',
            product_type='FINISHED',
            unit_price=10000, cost_price=7000,
            created_by=self.user,
        )

    def test_quotation_creation(self):
        """견적서 생성"""
        quote = Quotation.objects.create(
            quote_number='QT-001',
            partner=self.partner,
            quote_date=date.today(),
            valid_until=date.today() + timedelta(days=30),
            created_by=self.user,
        )
        self.assertEqual(quote.status, 'DRAFT')
        self.assertEqual(str(quote), 'QT-001')

    def test_quotation_unique_number(self):
        """견적번호 중복 불가"""
        Quotation.objects.create(
            quote_number='QT-DUP',
            quote_date=date.today(),
            valid_until=date.today() + timedelta(days=30),
            created_by=self.user,
        )
        with self.assertRaises(IntegrityError):
            Quotation.objects.create(
                quote_number='QT-DUP',
                quote_date=date.today(),
                valid_until=date.today() + timedelta(days=30),
                created_by=self.user,
            )

    def test_quotation_item_auto_calc(self):
        """견적항목 저장 시 금액 자동 계산"""
        quote = Quotation.objects.create(
            quote_number='QT-CALC-001',
            partner=self.partner,
            quote_date=date.today(),
            valid_until=date.today() + timedelta(days=30),
            created_by=self.user,
        )
        item = QuotationItem.objects.create(
            quotation=quote,
            product=self.product,
            quantity=10,
            unit_price=Decimal('10000'),
            created_by=self.user,
        )
        # amount = 10 * 10000 = 100000
        self.assertEqual(item.amount, Decimal('100000'))
        # tax = int(100000 * 0.1) = 10000
        self.assertEqual(item.tax_amount, Decimal('10000'))

    def test_quotation_update_total(self):
        """견적서 합계 갱신"""
        quote = Quotation.objects.create(
            quote_number='QT-TOTAL-001',
            partner=self.partner,
            quote_date=date.today(),
            valid_until=date.today() + timedelta(days=30),
            created_by=self.user,
        )
        QuotationItem.objects.create(
            quotation=quote, product=self.product,
            quantity=5, unit_price=Decimal('10000'),
            created_by=self.user,
        )
        quote.update_total()
        quote.refresh_from_db()
        self.assertEqual(quote.total_amount, Decimal('50000'))
        self.assertEqual(quote.tax_total, Decimal('5000'))
        self.assertEqual(quote.grand_total, Decimal('55000'))

    def test_quotation_status_choices(self):
        """견적서 상태 선택지"""
        choices = dict(Quotation.Status.choices)
        self.assertIn('DRAFT', choices)
        self.assertIn('SENT', choices)
        self.assertIn('ACCEPTED', choices)
        self.assertIn('CONVERTED', choices)
        self.assertIn('EXPIRED', choices)

    def test_quotation_status_transition(self):
        """견적서 상태 전환"""
        quote = Quotation.objects.create(
            quote_number='QT-TRANS-001',
            quote_date=date.today(),
            valid_until=date.today() + timedelta(days=30),
            created_by=self.user,
        )
        self.assertEqual(quote.status, 'DRAFT')
        quote.status = Quotation.Status.SENT
        quote.save()
        quote.refresh_from_db()
        self.assertEqual(quote.status, 'SENT')

        quote.status = Quotation.Status.ACCEPTED
        quote.save()
        quote.refresh_from_db()
        self.assertEqual(quote.status, 'ACCEPTED')


class ShipmentModelTest(TestCase):
    """배송 추적 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='shipuser', password='testpass123',
            role='staff',
        )
        self.order = Order.objects.create(
            order_number='ORD-SHIP-T001',
            order_date=date.today(),
            status='CONFIRMED',
            created_by=self.user,
        )

    def test_shipment_creation(self):
        """배송 생성"""
        shipment = Shipment.objects.create(
            order=self.order,
            shipment_number='SH-001',
            carrier=Shipment.Carrier.CJ,
            tracking_number='1234567890',
            created_by=self.user,
        )
        self.assertEqual(shipment.status, 'PREPARING')
        self.assertEqual(shipment.carrier, 'CJ')

    def test_shipment_str(self):
        """배송 문자열 표현"""
        shipment = Shipment.objects.create(
            order=self.order,
            shipment_number='SH-STR-001',
            carrier=Shipment.Carrier.HANJIN,
            status=Shipment.Status.SHIPPED,
            created_by=self.user,
        )
        result = str(shipment)
        self.assertIn('SH-STR-001', result)
        self.assertIn('발송', result)

    def test_shipment_tracking_url(self):
        """택배사별 조회 URL 생성"""
        shipment = Shipment.objects.create(
            order=self.order,
            shipment_number='SH-URL-001',
            carrier=Shipment.Carrier.CJ,
            tracking_number='9999999',
            created_by=self.user,
        )
        url = shipment.tracking_url
        self.assertIn('9999999', url)
        self.assertIn('cjlogistics', url)

    def test_shipment_tracking_url_hanjin(self):
        """한진택배 조회 URL"""
        shipment = Shipment.objects.create(
            order=self.order,
            shipment_number='SH-HJ-001',
            carrier=Shipment.Carrier.HANJIN,
            tracking_number='1111111',
            created_by=self.user,
        )
        self.assertIn('hanjin', shipment.tracking_url)

    def test_shipment_tracking_url_etc(self):
        """기타 택배사는 빈 URL"""
        shipment = Shipment.objects.create(
            order=self.order,
            shipment_number='SH-ETC-001',
            carrier=Shipment.Carrier.ETC,
            tracking_number='0000000',
            created_by=self.user,
        )
        self.assertEqual(shipment.tracking_url, '')

    def test_shipment_unique_number(self):
        """배송번호 중복 불가"""
        Shipment.objects.create(
            order=self.order,
            shipment_number='SH-DUP-001',
            carrier=Shipment.Carrier.CJ,
            created_by=self.user,
        )
        with self.assertRaises(IntegrityError):
            Shipment.objects.create(
                order=self.order,
                shipment_number='SH-DUP-001',
                carrier=Shipment.Carrier.LOTTE,
                created_by=self.user,
            )

    def test_shipment_status_transition(self):
        """배송 상태 전환"""
        shipment = Shipment.objects.create(
            order=self.order,
            shipment_number='SH-TRANS-001',
            carrier=Shipment.Carrier.CJ,
            created_by=self.user,
        )
        self.assertEqual(shipment.status, 'PREPARING')
        shipment.status = Shipment.Status.SHIPPED
        shipment.shipped_date = date.today()
        shipment.save()
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, 'SHIPPED')

        shipment.status = Shipment.Status.DELIVERED
        shipment.delivered_date = date.today()
        shipment.save()
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, 'DELIVERED')


class CommissionModelTest(TestCase):
    """수수료 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='commuser', password='testpass123',
            role='staff',
        )
        self.partner = Partner.objects.create(
            code='CM-P001', name='수수료거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
            created_by=self.user,
        )
        self.product = Product.objects.create(
            code='CM-PRD-001', name='수수료제품',
            product_type='FINISHED',
            unit_price=10000, cost_price=7000,
            created_by=self.user,
        )

    def test_commission_rate_creation(self):
        """수수료율 생성"""
        rate = CommissionRate.objects.create(
            partner=self.partner,
            product=self.product,
            rate=Decimal('5.00'),
            created_by=self.user,
        )
        self.assertEqual(rate.rate, Decimal('5.00'))

    def test_commission_rate_str_with_product(self):
        """제품 지정 수수료율 문자열"""
        rate = CommissionRate.objects.create(
            partner=self.partner,
            product=self.product,
            rate=Decimal('3.500'),
            created_by=self.user,
        )
        result = str(rate)
        self.assertIn('수수료거래처', result)
        self.assertIn('기본 수수료', result)
        self.assertIn('3.500', result)

    def test_commission_rate_str_without_product(self):
        """제품 미지정 수수료율 문자열"""
        rate = CommissionRate.objects.create(
            partner=self.partner,
            rate=Decimal('2.00'),
            created_by=self.user,
        )
        result = str(rate)
        self.assertIn('수수료거래처', result)
        self.assertIn('2.00', result)

    def test_commission_rate_multiple_per_partner(self):
        """거래처별 수수료 항목 여러개 가능"""
        CommissionRate.objects.create(
            partner=self.partner,
            product=self.product,
            name='판매수수료',
            rate=Decimal('5.000'),
            created_by=self.user,
        )
        rate2 = CommissionRate.objects.create(
            partner=self.partner,
            product=self.product,
            name='결제수수료',
            rate=Decimal('3.000'),
            created_by=self.user,
        )
        self.assertEqual(
            CommissionRate.objects.filter(partner=self.partner).count(), 2,
        )

    def test_commission_record_creation(self):
        """수수료 내역 생성"""
        record = CommissionRecord.objects.create(
            partner=self.partner,
            order_amount=Decimal('1000000'),
            commission_rate=Decimal('5.00'),
            commission_amount=Decimal('50000'),
            created_by=self.user,
        )
        self.assertEqual(record.status, 'PENDING')
        self.assertEqual(
            record.commission_amount, Decimal('50000')
        )

    def test_commission_record_str(self):
        """수수료 내역 문자열 표현"""
        record = CommissionRecord.objects.create(
            partner=self.partner,
            order_amount=Decimal('500000'),
            commission_rate=Decimal('3.00'),
            commission_amount=Decimal('15000'),
            created_by=self.user,
        )
        result = str(record)
        self.assertIn('수수료거래처', result)
        self.assertIn('15000', result)

    def test_commission_record_settlement(self):
        """수수료 정산 처리"""
        record = CommissionRecord.objects.create(
            partner=self.partner,
            order_amount=Decimal('1000000'),
            commission_rate=Decimal('5.00'),
            commission_amount=Decimal('50000'),
            created_by=self.user,
        )
        record.status = CommissionRecord.Status.SETTLED
        record.settled_date = date.today()
        record.save()
        record.refresh_from_db()
        self.assertEqual(record.status, 'SETTLED')
        self.assertEqual(record.settled_date, date.today())


class ShippingCarrierTest(TestCase):
    """택배사 모델 테스트"""

    def test_carrier_creation(self):
        """ShippingCarrier 생성 가능"""
        carrier = ShippingCarrier.objects.create(
            code='CJ',
            name='CJ대한통운',
            tracking_url_template='https://trace.cjlogistics.com/next/tracking.html?wblNo={tracking_number}',
            is_default=False,
        )
        self.assertEqual(carrier.code, 'CJ')
        self.assertEqual(carrier.name, 'CJ대한통운')
        self.assertFalse(carrier.is_default)
        self.assertEqual(str(carrier), 'CJ대한통운')

    def test_default_carrier_unique(self):
        """is_default=True인 택배사가 하나만 존재하도록"""
        cj = ShippingCarrier.objects.create(
            code='CJ', name='CJ대한통운', is_default=True,
        )
        # 두 번째 기본택배사 생성 시 기존 기본택배사가 해제됨
        hanjin = ShippingCarrier.objects.create(
            code='HANJIN', name='한진택배', is_default=True,
        )
        cj.refresh_from_db()
        self.assertFalse(cj.is_default)
        self.assertTrue(hanjin.is_default)
        # 기본택배사는 하나만 존재
        self.assertEqual(
            ShippingCarrier.objects.filter(is_default=True).count(), 1,
        )


class PartnerBankSyncTest(TestCase):
    """거래처 계좌 → 회계 BankAccount 연동 테스트"""

    def test_partner_bank_creates_account(self):
        """거래처 계좌정보 입력 시 BankAccount(BUSINESS) 자동 생성"""
        from apps.accounting.models import BankAccount
        partner = Partner.objects.create(
            code='BP-001', name='테스트거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
            bank_name='기업은행', bank_account='100-200-300',
            bank_holder='테스트거래처 대표',
        )
        acct = BankAccount.objects.filter(partner=partner).first()
        self.assertIsNotNone(acct)
        self.assertEqual(acct.account_type, 'BUSINESS')
        self.assertEqual(acct.bank, '기업은행')
        self.assertEqual(acct.account_number, '100-200-300')
        self.assertEqual(acct.owner, '테스트거래처 대표')
        self.assertIn('거래계좌', acct.name)

    def test_partner_bank_update_syncs(self):
        """거래처 계좌정보 변경 시 BankAccount도 갱신"""
        from apps.accounting.models import BankAccount
        partner = Partner.objects.create(
            code='BP-002', name='갱신거래처',
            partner_type=Partner.PartnerType.SUPPLIER,
            bank_name='국민은행', bank_account='111-222-333',
            bank_holder='원래 대표',
        )
        partner.bank_name = '하나은행'
        partner.bank_account = '999-888-777'
        partner.bank_holder = '새 대표'
        partner.save()
        acct = BankAccount.objects.get(partner=partner)
        self.assertEqual(acct.bank, '하나은행')
        self.assertEqual(acct.account_number, '999-888-777')
        self.assertEqual(acct.owner, '새 대표')

    def test_partner_no_bank_skips(self):
        """계좌정보 미입력 시 BankAccount 생성 안 됨"""
        from apps.accounting.models import BankAccount
        partner = Partner.objects.create(
            code='BP-003', name='계좌없는거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
        )
        self.assertFalse(BankAccount.objects.filter(partner=partner).exists())

    def test_partner_no_holder_uses_name(self):
        """예금주 미입력 시 거래처명이 owner로 설정"""
        from apps.accounting.models import BankAccount
        partner = Partner.objects.create(
            code='BP-004', name='예금주없는거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
            bank_name='신한은행', bank_account='444-555-666',
        )
        acct = BankAccount.objects.get(partner=partner)
        self.assertEqual(acct.owner, '예금주없는거래처')

    def test_partner_bank_no_duplicate(self):
        """동일 거래처 반복 저장해도 BankAccount 1개만 유지"""
        from apps.accounting.models import BankAccount
        partner = Partner.objects.create(
            code='BP-005', name='중복테스트',
            partner_type=Partner.PartnerType.CUSTOMER,
            bank_name='우리은행', bank_account='777-888-999',
        )
        partner.save()
        partner.save()
        self.assertEqual(BankAccount.objects.filter(partner=partner).count(), 1)


class PriceRuleTest(TestCase):
    """가격규칙 모델 + 가격조회 로직 테스트"""

    def setUp(self):
        from apps.inventory.models import Category
        self.cat = Category.objects.create(name='테스트')
        self.product = Product.objects.create(
            code='PR-001', name='테스트제품', unit_price=10000, cost_price=5000,
            category=self.cat,
        )
        self.partner = Partner.objects.create(
            code='PRT-001', name='테스트거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
        )
        self.customer = Customer.objects.create(
            code='CST-001', name='테스트고객', phone='010-1234-5678',
        )

    def test_no_rule_returns_default_price(self):
        """규칙 없으면 제품 기본 판매단가"""
        from apps.sales.pricing import get_applicable_price
        result = get_applicable_price(self.product)
        self.assertEqual(result['unit_price'], 10000)
        self.assertEqual(result['source'], 'default')

    def test_fixed_price_rule(self):
        """고정단가 규칙 적용"""
        from apps.sales.pricing import get_applicable_price
        from apps.sales.models import PriceRule
        PriceRule.objects.create(
            product=self.product, partner=self.partner,
            unit_price=8000,
        )
        result = get_applicable_price(self.product, partner=self.partner)
        self.assertEqual(result['unit_price'], 8000)
        self.assertEqual(result['source'], 'fixed')

    def test_discount_rate_rule(self):
        """할인율 규칙 적용"""
        from apps.sales.pricing import get_applicable_price
        from apps.sales.models import PriceRule
        PriceRule.objects.create(
            product=self.product, partner=self.partner,
            discount_rate=10,
        )
        result = get_applicable_price(self.product, partner=self.partner)
        self.assertEqual(result['unit_price'], 9000)  # 10000 * 0.9
        self.assertEqual(result['discount_rate'], 10.0)
        self.assertEqual(result['source'], 'discount')

    def test_quantity_tier_rule(self):
        """수량 구간별 할인"""
        from apps.sales.pricing import get_applicable_price
        from apps.sales.models import PriceRule
        PriceRule.objects.create(
            product=self.product, min_quantity=100,
            discount_rate=5,
        )
        PriceRule.objects.create(
            product=self.product, min_quantity=500,
            discount_rate=10,
        )
        # 50개 → 규칙 없음
        result = get_applicable_price(self.product, quantity=50)
        self.assertEqual(result['unit_price'], 10000)
        # 100개 → 5% 할인
        result = get_applicable_price(self.product, quantity=100)
        self.assertEqual(result['unit_price'], 9500)
        # 500개 → 10% 할인 (더 큰 구간 우선)
        result = get_applicable_price(self.product, quantity=500)
        self.assertEqual(result['unit_price'], 9000)

    def test_partner_specific_overrides_general(self):
        """거래처별 규칙이 일반 규칙보다 우선"""
        from apps.sales.pricing import get_applicable_price
        from apps.sales.models import PriceRule
        PriceRule.objects.create(
            product=self.product, min_quantity=1,
            discount_rate=5,
        )
        PriceRule.objects.create(
            product=self.product, partner=self.partner,
            min_quantity=1, unit_price=7000,
        )
        result = get_applicable_price(self.product, partner=self.partner)
        self.assertEqual(result['unit_price'], 7000)

    def test_priority_ordering(self):
        """우선순위 높은 규칙이 먼저 적용"""
        from apps.sales.pricing import get_applicable_price
        from apps.sales.models import PriceRule
        PriceRule.objects.create(
            product=self.product, partner=self.partner,
            unit_price=8000, priority=1,
        )
        PriceRule.objects.create(
            product=self.product, partner=self.partner,
            unit_price=7000, priority=10,
        )
        result = get_applicable_price(self.product, partner=self.partner)
        self.assertEqual(result['unit_price'], 7000)

    def test_valid_date_filter(self):
        """유효기간 외 규칙은 무시"""
        from datetime import date
        from apps.sales.pricing import get_applicable_price
        from apps.sales.models import PriceRule
        PriceRule.objects.create(
            product=self.product, partner=self.partner,
            unit_price=5000,
            valid_from=date(2020, 1, 1), valid_to=date(2020, 12, 31),
        )
        result = get_applicable_price(self.product, partner=self.partner)
        self.assertEqual(result['unit_price'], 10000)  # 만료된 규칙 무시

    def test_customer_specific_rule(self):
        """고객별 규칙 적용"""
        from apps.sales.pricing import get_applicable_price
        from apps.sales.models import PriceRule
        PriceRule.objects.create(
            product=self.product, customer=self.customer,
            discount_rate=15,
        )
        result = get_applicable_price(self.product, customer=self.customer)
        self.assertEqual(result['unit_price'], 8500)  # 10000 * 0.85

    def test_inactive_rule_ignored(self):
        """비활성 규칙은 무시"""
        from apps.sales.pricing import get_applicable_price
        from apps.sales.models import PriceRule
        PriceRule.objects.create(
            product=self.product, partner=self.partner,
            unit_price=1000, is_active=False,
        )
        result = get_applicable_price(self.product, partner=self.partner)
        self.assertEqual(result['unit_price'], 10000)

    def test_model_str(self):
        """PriceRule __str__ 확인"""
        from apps.sales.models import PriceRule
        rule = PriceRule.objects.create(
            product=self.product, partner=self.partner,
            min_quantity=10, unit_price=9000,
        )
        self.assertIn('Q>=10', str(rule))
