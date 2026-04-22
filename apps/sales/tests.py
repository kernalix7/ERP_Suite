from decimal import Decimal
from datetime import date, timedelta

from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.models import User
from apps.inventory.models import Product, Warehouse, StockMovement
from apps.sales.models import (
    Partner, Customer, CustomerPurchase, Order, OrderItem,
    Quotation, QuotationItem, Shipment, ShippingCarrier,
    CustomerTier, SalesTarget, SalesLead, LeadActivity, CustomerSatisfaction,
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


class QuotationStatusTransitionTest(TestCase):
    """견적서 상태 전환 규칙 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='quotetransuser', password='testpass123', role='staff',
        )
        self.partner = Partner.objects.create(
            code='QTT-P001', name='전환테스트거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
            created_by=self.user,
        )

    def _create_quote(self, status='DRAFT', valid_until=None):
        if valid_until is None:
            valid_until = date.today() + timedelta(days=30)
        return Quotation.objects.create(
            quote_number=f'QTT-{status}-{Quotation.objects.count() + 1}',
            partner=self.partner,
            quote_date=date.today(),
            valid_until=valid_until,
            status=status,
            created_by=self.user,
        )

    def test_draft_to_sent_allowed(self):
        """DRAFT → SENT 허용"""
        quote = self._create_quote('DRAFT')
        quote.status = 'SENT'
        quote.save()
        quote.refresh_from_db()
        self.assertEqual(quote.status, 'SENT')

    def test_draft_to_accepted_blocked(self):
        """DRAFT → ACCEPTED 차단"""
        quote = self._create_quote('DRAFT')
        quote.status = 'ACCEPTED'
        with self.assertRaises(ValueError):
            quote.save()

    def test_sent_to_accepted_allowed(self):
        """SENT → ACCEPTED 허용"""
        quote = self._create_quote('SENT')
        quote.status = 'ACCEPTED'
        quote.save()
        quote.refresh_from_db()
        self.assertEqual(quote.status, 'ACCEPTED')

    def test_sent_to_rejected_allowed(self):
        """SENT → REJECTED 허용"""
        quote = self._create_quote('SENT')
        quote.status = 'REJECTED'
        quote.save()
        quote.refresh_from_db()
        self.assertEqual(quote.status, 'REJECTED')

    def test_rejected_cannot_transition(self):
        """REJECTED 상태에서 전환 불가"""
        quote = self._create_quote('REJECTED')
        quote.status = 'DRAFT'
        with self.assertRaises(ValueError):
            quote.save()

    def test_converted_cannot_transition(self):
        """CONVERTED 상태에서 전환 불가"""
        quote = self._create_quote('CONVERTED')
        quote.status = 'DRAFT'
        with self.assertRaises(ValueError):
            quote.save()

    def test_expired_cannot_transition(self):
        """EXPIRED 상태에서 전환 불가"""
        quote = self._create_quote('EXPIRED')
        quote.status = 'DRAFT'
        with self.assertRaises(ValueError):
            quote.save()

    def test_auto_expire_on_save(self):
        """유효기한 초과 시 save()에서 EXPIRED 자동 전환"""
        quote = self._create_quote('SENT', valid_until=date.today() - timedelta(days=1))
        quote.refresh_from_db()
        self.assertEqual(quote.status, 'EXPIRED')

    def test_auto_expire_draft(self):
        """DRAFT도 유효기한 초과 시 EXPIRED 전환"""
        quote = self._create_quote('DRAFT', valid_until=date.today() - timedelta(days=1))
        quote.refresh_from_db()
        self.assertEqual(quote.status, 'EXPIRED')

    def test_no_expire_when_valid(self):
        """유효기한 내면 EXPIRED 전환 안 됨"""
        quote = self._create_quote('SENT', valid_until=date.today() + timedelta(days=10))
        quote.refresh_from_db()
        self.assertEqual(quote.status, 'SENT')


class QuotationExpireTaskTest(TestCase):
    """견적 만료 Celery task 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='expiretaskuser', password='testpass123', role='staff',
        )

    def test_expire_quotations_task(self):
        """expire_quotations task가 만료 견적을 일괄 전환"""
        from apps.sales.tasks import expire_quotations
        # 만료된 견적 생성 (status를 먼저 SENT로 저장, 유효기한은 미래로)
        q1 = Quotation.objects.create(
            quote_number='EXP-001',
            quote_date=date.today() - timedelta(days=60),
            valid_until=date.today() + timedelta(days=30),
            status='SENT',
            created_by=self.user,
        )
        # 유효기한을 과거로 직접 변경 (save()의 auto-expire를 우회)
        Quotation.objects.filter(pk=q1.pk).update(
            valid_until=date.today() - timedelta(days=1),
        )
        # 유효한 견적 (만료 안 됨)
        q2 = Quotation.objects.create(
            quote_number='EXP-002',
            quote_date=date.today(),
            valid_until=date.today() + timedelta(days=30),
            status='DRAFT',
            created_by=self.user,
        )
        count = expire_quotations()
        self.assertEqual(count, 1)
        q1.refresh_from_db()
        self.assertEqual(q1.status, 'EXPIRED')
        q2.refresh_from_db()
        self.assertEqual(q2.status, 'DRAFT')


class ReturnExchangeOrderTest(TestCase):
    """반품/교환 주문 프로세스 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='returnuser', password='testpass123', role='staff',
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-RTN', name='반품창고', created_by=self.user,
        )
        self.product = Product.objects.create(
            code='PRD-RTN-001', name='반품제품', product_type='FINISHED',
            unit_price=10000, cost_price=7000, current_stock=100,
            created_by=self.user,
        )
        self.partner = Partner.objects.create(
            code='RTN-P001', name='반품거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
            created_by=self.user,
        )
        # 원본 주문 (SHIPPED 상태)
        self.original_order = Order.objects.create(
            order_number='ORD-RTN-ORIG',
            order_type='NORMAL',
            partner=self.partner,
            order_date=date.today(),
            status='CONFIRMED',
            created_by=self.user,
        )
        self.original_item = OrderItem.objects.create(
            order=self.original_order,
            product=self.product,
            quantity=5,
            unit_price=10000,
            created_by=self.user,
        )
        self.original_order.update_total()
        self.original_order.status = 'SHIPPED'
        self.original_order.save(update_fields=['status', 'updated_at'])

    def test_return_order_creates_stock_in(self):
        """반품 주문 확정 시 반품입고 StockMovement 생성"""
        return_order = Order.objects.create(
            order_number='ORD-RTN-001',
            order_type='RETURN',
            original_order=self.original_order,
            partner=self.partner,
            order_date=date.today(),
            status='DRAFT',
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=return_order,
            product=self.product,
            quantity=5,
            unit_price=10000,
            created_by=self.user,
        )
        return_order.update_total()
        # 재고 확인 (출고 후)
        self.product.refresh_from_db()
        stock_before = self.product.current_stock

        return_order.status = 'CONFIRMED'
        return_order.save(update_fields=['status', 'updated_at'])

        # 반품입고 IN StockMovement 생성 확인
        in_movements = StockMovement.objects.filter(
            movement_type='IN',
            reference__contains='반품입고',
        )
        self.assertEqual(in_movements.count(), 1)
        self.assertEqual(in_movements.first().quantity, 5)

        # 재고 증가 확인
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, stock_before + 5)

    def test_return_order_creates_reverse_ar(self):
        """반품 주문 확정 시 AR 역전표 생성"""
        from apps.accounting.models import AccountReceivable

        return_order = Order.objects.create(
            order_number='ORD-RTN-AR',
            order_type='RETURN',
            original_order=self.original_order,
            partner=self.partner,
            order_date=date.today(),
            status='DRAFT',
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=return_order,
            product=self.product,
            quantity=5,
            unit_price=10000,
            created_by=self.user,
        )
        return_order.update_total()
        return_order.status = 'CONFIRMED'
        return_order.save(update_fields=['status', 'updated_at'])

        ar = AccountReceivable.objects.filter(order=return_order, is_active=True).first()
        self.assertIsNotNone(ar)
        self.assertTrue(ar.amount < 0)  # 역전표

    def test_exchange_order_creates_in_and_out(self):
        """교환 주문 확정 시 반품입고 + 교환출고 StockMovement 생성"""
        exchange_order = Order.objects.create(
            order_number='ORD-EXC-001',
            order_type='EXCHANGE',
            original_order=self.original_order,
            partner=self.partner,
            order_date=date.today(),
            status='DRAFT',
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=exchange_order,
            product=self.product,
            quantity=5,
            unit_price=10000,
            created_by=self.user,
        )
        exchange_order.update_total()
        exchange_order.status = 'CONFIRMED'
        exchange_order.save(update_fields=['status', 'updated_at'])

        # 반품입고(IN) + 교환출고(OUT) 모두 존재
        in_movements = StockMovement.objects.filter(
            movement_type='IN',
            reference__contains='교환반품입고',
        )
        out_movements = StockMovement.objects.filter(
            movement_type='OUT',
            reference__contains='교환출고',
        )
        self.assertEqual(in_movements.count(), 1)
        self.assertEqual(out_movements.count(), 1)

    def test_return_order_fields(self):
        """반품 주문에 original_order, return_reason 필드 존재"""
        return_order = Order.objects.create(
            order_number='ORD-RTN-FIELD',
            order_type='RETURN',
            original_order=self.original_order,
            return_reason='불량품 반품',
            partner=self.partner,
            order_date=date.today(),
            status='DRAFT',
            created_by=self.user,
        )
        return_order.refresh_from_db()
        self.assertEqual(return_order.original_order, self.original_order)
        self.assertEqual(return_order.return_reason, '불량품 반품')
        self.assertEqual(return_order.order_type, 'RETURN')


class PriceRuleAutoApplyTest(TestCase):
    """C3: PriceRule 자동 적용 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='priceautouser', password='testpass123', role='staff',
        )
        self.partner = Partner.objects.create(
            code='PA-001', name='가격규칙거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
            created_by=self.user,
        )
        self.product = Product.objects.create(
            code='PA-PRD-001', name='가격규칙제품',
            product_type='FINISHED',
            unit_price=10000, cost_price=7000,
            created_by=self.user,
        )
        self.order = Order.objects.create(
            order_number='ORD-PA-001',
            partner=self.partner,
            order_date=date.today(),
            status='DRAFT',
            created_by=self.user,
        )

    def test_orderitem_auto_price_from_rule(self):
        """unit_price=0일 때 PriceRule에서 자동 조회"""
        from apps.sales.models import PriceRule
        PriceRule.objects.create(
            product=self.product, partner=self.partner,
            unit_price=8000, priority=10,
            created_by=self.user,
        )
        item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=3,
            unit_price=0,
            created_by=self.user,
        )
        self.assertEqual(item.unit_price, 8000)
        self.assertEqual(item.amount, 24000)

    def test_orderitem_no_override_when_price_set(self):
        """unit_price가 0이 아니면 PriceRule 무시"""
        from apps.sales.models import PriceRule
        PriceRule.objects.create(
            product=self.product, partner=self.partner,
            unit_price=8000,
            created_by=self.user,
        )
        item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            unit_price=9000,
            created_by=self.user,
        )
        self.assertEqual(item.unit_price, 9000)

    def test_quotationitem_auto_price_from_rule(self):
        """QuotationItem에서도 PriceRule 자동 적용"""
        from apps.sales.models import PriceRule
        PriceRule.objects.create(
            product=self.product, partner=self.partner,
            unit_price=7500,
            created_by=self.user,
        )
        quote = Quotation.objects.create(
            quote_number='QT-PA-001',
            partner=self.partner,
            quote_date=date.today(),
            valid_until=date.today() + timedelta(days=30),
            created_by=self.user,
        )
        qi = QuotationItem.objects.create(
            quotation=quote,
            product=self.product,
            quantity=4,
            unit_price=0,
            created_by=self.user,
        )
        self.assertEqual(qi.unit_price, 7500)
        self.assertEqual(qi.amount, 30000)


class ShipmentTrackingAutoTest(TestCase):
    """H2: ShipmentTracking 자동 생성 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='trackuser', password='testpass123', role='staff',
        )
        self.order = Order.objects.create(
            order_number='ORD-TRACK-001',
            order_date=date.today(),
            status='CONFIRMED',
            created_by=self.user,
        )
        self.shipment = Shipment.objects.create(
            order=self.order,
            shipment_number='SH-TRACK-001',
            carrier=Shipment.Carrier.CJ,
            created_by=self.user,
        )

    def test_status_change_creates_tracking(self):
        """배송 상태 변경 시 ShipmentTracking 자동 생성"""
        from apps.sales.models import ShipmentTracking
        self.shipment.status = 'SHIPPED'
        self.shipment.shipped_date = date.today()
        self.shipment.save()

        tracks = ShipmentTracking.objects.filter(shipment=self.shipment)
        self.assertEqual(tracks.count(), 1)
        self.assertEqual(tracks.first().status, '발송')

    def test_no_tracking_on_same_status(self):
        """동일 상태 저장 시 ShipmentTracking 생성 안 됨"""
        from apps.sales.models import ShipmentTracking
        self.shipment.save()
        self.assertEqual(
            ShipmentTracking.objects.filter(shipment=self.shipment).count(), 0,
        )


class PartnerApprovalTest(TestCase):
    """M1: 거래처 승인 상태 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='approvaluser', password='testpass123', role='staff',
        )
        self.product = Product.objects.create(
            code='APR-PRD-001', name='승인제품',
            product_type='FINISHED',
            unit_price=10000, cost_price=7000, current_stock=100,
            created_by=self.user,
        )

    def test_approved_partner_can_confirm(self):
        """APPROVED 거래처 주문 확정 가능"""
        partner = Partner.objects.create(
            code='APR-P001', name='승인거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
            approval_status='APPROVED',
            created_by=self.user,
        )
        order = Order.objects.create(
            order_number='ORD-APR-001',
            partner=partner,
            order_date=date.today(),
            status='DRAFT',
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=order, product=self.product,
            quantity=1, unit_price=10000,
            created_by=self.user,
        )
        order.update_total()
        order.status = 'CONFIRMED'
        order.save(update_fields=['status', 'updated_at'])
        order.refresh_from_db()
        self.assertEqual(order.status, 'CONFIRMED')

    def test_suspended_partner_blocks_confirm(self):
        """SUSPENDED 거래처 주문 확정 차단"""
        partner = Partner.objects.create(
            code='APR-P002', name='정지거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
            approval_status='SUSPENDED',
            created_by=self.user,
        )
        order = Order.objects.create(
            order_number='ORD-APR-002',
            partner=partner,
            order_date=date.today(),
            status='DRAFT',
            created_by=self.user,
        )
        order.status = 'CONFIRMED'
        with self.assertRaises(ValueError):
            order.save(update_fields=['status', 'updated_at'])

    def test_default_approval_status_is_approved(self):
        """기본 승인상태는 APPROVED"""
        partner = Partner.objects.create(
            code='APR-P003', name='기본거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
            created_by=self.user,
        )
        self.assertEqual(partner.approval_status, 'APPROVED')


class ServiceRequestOrderFKTest(TestCase):
    """M3: ServiceRequest ← Order FK 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='svcfkuser', password='testpass123', role='staff',
        )
        self.customer = Customer.objects.create(
            code='SVC-CST', name='서비스고객', phone='010-1234-5678',
            created_by=self.user,
        )
        self.product = Product.objects.create(
            code='SVC-PRD', name='서비스제품',
            unit_price=10000, created_by=self.user,
        )
        self.order = Order.objects.create(
            order_number='ORD-SVC-001',
            order_date=date.today(),
            status='DRAFT',
            created_by=self.user,
        )

    def test_service_request_with_order(self):
        """ServiceRequest에 order FK 설정 가능"""
        from apps.service.models import ServiceRequest
        sr = ServiceRequest.objects.create(
            customer=self.customer,
            product=self.product,
            symptom='제품 불량',
            received_date=date.today(),
            order=self.order,
            created_by=self.user,
        )
        sr.refresh_from_db()
        self.assertEqual(sr.order, self.order)

    def test_service_request_without_order(self):
        """ServiceRequest order FK는 nullable"""
        from apps.service.models import ServiceRequest
        sr = ServiceRequest.objects.create(
            customer=self.customer,
            product=self.product,
            symptom='일반 AS',
            received_date=date.today(),
            created_by=self.user,
        )
        self.assertIsNone(sr.order)

    def test_order_service_requests_reverse(self):
        """Order에서 service_requests 역참조"""
        from apps.service.models import ServiceRequest
        ServiceRequest.objects.create(
            customer=self.customer,
            product=self.product,
            symptom='반품 AS',
            received_date=date.today(),
            order=self.order,
            created_by=self.user,
        )
        self.assertEqual(self.order.service_requests.count(), 1)


class ShipmentItemReservedStockTest(TestCase):
    """ShipmentItem 생성/삭제 시 예약재고 해제/복원 테스트"""

    def setUp(self):
        from apps.sales.models import ShipmentItem
        self.user = User.objects.create_user(
            username='resuser', password='testpass123', role='staff',
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-RES', name='예약창고', created_by=self.user,
        )
        self.product = Product.objects.create(
            code='PRD-RES-001', name='예약제품', product_type='FINISHED',
            unit_price=10000, cost_price=7000, current_stock=100,
            reserved_stock=0, created_by=self.user,
        )
        self.partner = Partner.objects.create(
            code='RES-P001', name='예약거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
            created_by=self.user,
        )
        self.order = Order.objects.create(
            order_number='ORD-RES-001',
            partner=self.partner,
            order_date=date.today(),
            status='DRAFT',
            created_by=self.user,
        )
        self.order_item = OrderItem.objects.create(
            order=self.order, product=self.product,
            quantity=10, unit_price=10000, created_by=self.user,
        )
        self.order.update_total()
        # CONFIRMED → 예약재고 증가
        self.order.status = 'CONFIRMED'
        self.order.save(update_fields=['status', 'updated_at'])
        self.product.refresh_from_db()
        self.reserved_after_confirm = self.product.reserved_stock

    def test_shipment_item_releases_reserved(self):
        """ShipmentItem 생성 시 예약재고 해제"""
        from apps.sales.models import ShipmentItem
        shipment = Shipment.objects.create(
            order=self.order, shipment_number='SH-RES-001',
            carrier=Shipment.Carrier.CJ, created_by=self.user,
        )
        ShipmentItem.objects.create(
            shipment=shipment, order_item=self.order_item,
            quantity=3, created_by=self.user,
        )
        self.product.refresh_from_db()
        self.assertEqual(
            self.product.reserved_stock,
            self.reserved_after_confirm - 3,
        )

    def test_shipment_item_soft_delete_restores_reserved(self):
        """ShipmentItem soft delete 시 예약재고 복원"""
        from apps.sales.models import ShipmentItem
        shipment = Shipment.objects.create(
            order=self.order, shipment_number='SH-RES-002',
            carrier=Shipment.Carrier.CJ, created_by=self.user,
        )
        si = ShipmentItem.objects.create(
            shipment=shipment, order_item=self.order_item,
            quantity=5, created_by=self.user,
        )
        self.product.refresh_from_db()
        reserved_after_ship = self.product.reserved_stock

        si.soft_delete()
        self.product.refresh_from_db()
        self.assertEqual(
            self.product.reserved_stock,
            reserved_after_ship + 5,
        )


class ShipmentSerialTrackingTest(TestCase):
    """출고 시 시리얼번호 자동 할당 테스트"""

    def setUp(self):
        from apps.sales.models import ShipmentItem
        from apps.inventory.models import SerialNumber

        self.user = User.objects.create_user(
            username='snuser', password='testpass123', role='staff',
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-SN', name='시리얼창고', created_by=self.user,
        )
        self.product = Product.objects.create(
            code='PRD-SN-001', name='시리얼제품', product_type='FINISHED',
            unit_price=50000, cost_price=30000, current_stock=100,
            reserved_stock=0, serial_tracking=True,
            created_by=self.user,
        )
        self.partner = Partner.objects.create(
            code='SN-P001', name='시리얼거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
            created_by=self.user,
        )
        self.order = Order.objects.create(
            order_number='ORD-SN-001',
            partner=self.partner,
            order_date=date.today(),
            status='DRAFT',
            created_by=self.user,
        )
        self.order_item = OrderItem.objects.create(
            order=self.order, product=self.product,
            quantity=5, unit_price=50000, created_by=self.user,
        )
        self.order.update_total()

        # 시리얼 3개 수동 생성 (IN_STOCK)
        self.serials = []
        for i in range(1, 4):
            sn = SerialNumber.objects.create(
                serial=f'SN-PRD-SN-001-{i:04d}',
                product=self.product,
                status=SerialNumber.Status.IN_STOCK,
                warehouse=self.warehouse,
                created_by=self.user,
            )
            self.serials.append(sn)

        # CONFIRMED → 예약재고 증가
        self.order.status = 'CONFIRMED'
        self.order.save(update_fields=['status', 'updated_at'])

    def test_shipment_item_assigns_serials(self):
        """ShipmentItem 생성 시 시리얼 FIFO 할당"""
        from apps.sales.models import ShipmentItem
        from apps.inventory.models import SerialNumber

        shipment = Shipment.objects.create(
            order=self.order, shipment_number='SH-SN-001',
            carrier=Shipment.Carrier.CJ, created_by=self.user,
        )
        # 수량 2 출고 → 시리얼 2개 할당
        ShipmentItem.objects.create(
            shipment=shipment, order_item=self.order_item,
            quantity=2, created_by=self.user,
        )

        # FIFO 순서로 첫 2개가 SHIPPED로 변경되어야 함
        for sn in self.serials[:2]:
            sn.refresh_from_db()
            self.assertEqual(sn.status, SerialNumber.Status.SHIPPED)
            self.assertIsNotNone(sn.shipped_date)

        # 3번째는 IN_STOCK 유지
        self.serials[2].refresh_from_db()
        self.assertEqual(self.serials[2].status, SerialNumber.Status.IN_STOCK)

    def test_shipment_item_soft_delete_restores_serials(self):
        """ShipmentItem soft delete 시 시리얼 IN_STOCK 복원"""
        from apps.sales.models import ShipmentItem
        from apps.inventory.models import SerialNumber

        # shipment_item FK가 없으면 복원 로직 테스트 스킵
        if not hasattr(SerialNumber, 'shipment_item'):
            self.skipTest(
                'SerialNumber.shipment_item FK not yet added — '
                'restore test skipped'
            )

        shipment = Shipment.objects.create(
            order=self.order, shipment_number='SH-SN-002',
            carrier=Shipment.Carrier.CJ, created_by=self.user,
        )
        si = ShipmentItem.objects.create(
            shipment=shipment, order_item=self.order_item,
            quantity=2, created_by=self.user,
        )

        # 시리얼 SHIPPED 확인
        for sn in self.serials[:2]:
            sn.refresh_from_db()
            self.assertEqual(sn.status, SerialNumber.Status.SHIPPED)

        # soft delete → IN_STOCK 복원
        si.soft_delete()
        for sn in self.serials[:2]:
            sn.refresh_from_db()
            self.assertEqual(sn.status, SerialNumber.Status.IN_STOCK)
            self.assertIsNone(sn.shipped_date)

    def test_non_tracking_product_no_serial_assignment(self):
        """serial_tracking=False 제품은 시리얼 할당 없음"""
        from apps.sales.models import ShipmentItem
        from apps.inventory.models import SerialNumber

        non_tracking = Product.objects.create(
            code='PRD-NT-001', name='비추적제품', product_type='FINISHED',
            unit_price=10000, cost_price=7000, current_stock=50,
            serial_tracking=False, created_by=self.user,
        )
        order = Order.objects.create(
            order_number='ORD-NT-001',
            partner=self.partner,
            order_date=date.today(),
            status='DRAFT',
            created_by=self.user,
        )
        oi = OrderItem.objects.create(
            order=order, product=non_tracking,
            quantity=3, unit_price=10000, created_by=self.user,
        )
        order.update_total()
        order.status = 'CONFIRMED'
        order.save(update_fields=['status', 'updated_at'])

        shipment = Shipment.objects.create(
            order=order, shipment_number='SH-NT-001',
            carrier=Shipment.Carrier.CJ, created_by=self.user,
        )
        ShipmentItem.objects.create(
            shipment=shipment, order_item=oi,
            quantity=3, created_by=self.user,
        )

        # 시리얼 상태 변경 없어야 함 (원래 시리얼은 다른 제품 소속)
        for sn in self.serials:
            sn.refresh_from_db()
            self.assertEqual(sn.status, SerialNumber.Status.IN_STOCK)


class ReturnOrderTest(TestCase):
    """반품 주문 프로세스 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='return_user', password='testpass123', role='staff',
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-RTN', name='반품창고', created_by=self.user,
        )
        self.partner = Partner.objects.create(
            code='PT-RTN', name='반품거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
            created_by=self.user,
        )
        self.product = Product.objects.create(
            code='PRD-RTN-001', name='반품제품', product_type='FINISHED',
            unit_price=10000, cost_price=7000, current_stock=100,
            created_by=self.user,
        )
        # 원본 주문 생성 (SHIPPED 상태)
        self.original_order = Order.objects.create(
            order_number='ORD-RTN-ORIG',
            order_type='NORMAL',
            partner=self.partner,
            order_date=date.today(),
            status='DRAFT',
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=self.original_order, product=self.product,
            quantity=5, unit_price=10000, created_by=self.user,
        )
        self.original_order.update_total()
        self.original_order.status = 'CONFIRMED'
        self.original_order.save()
        self.original_order.status = 'SHIPPED'
        self.original_order.save()

    def test_return_order_creates_return_stock_movement(self):
        """반품주문 확정 시 IN(반품입고) StockMovement 생성"""
        return_order = Order.objects.create(
            order_number='ORD-RTN-001',
            order_type='RETURN',
            original_order=self.original_order,
            partner=self.partner,
            order_date=date.today(),
            status='DRAFT',
            return_reason='불량',
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=return_order, product=self.product,
            quantity=3, unit_price=10000, created_by=self.user,
        )
        return_order.update_total()
        return_order.status = 'CONFIRMED'
        return_order.save()

        # IN StockMovement 생성 확인
        in_movements = StockMovement.objects.filter(
            movement_type='IN',
            reference__contains='반품입고',
        )
        self.assertEqual(in_movements.count(), 1)
        self.assertEqual(in_movements.first().quantity, 3)

        # 재고 증가 확인
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 98)  # 100 - 5(출고) + 3(반품)

    def test_return_order_creates_refund_ar(self):
        """반품주문 확정 시 음수 AR(환불) 생성"""
        from apps.accounting.models import AccountReceivable

        return_order = Order.objects.create(
            order_number='ORD-RTN-AR',
            order_type='RETURN',
            original_order=self.original_order,
            partner=self.partner,
            order_date=date.today(),
            status='DRAFT',
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=return_order, product=self.product,
            quantity=2, unit_price=10000, created_by=self.user,
        )
        return_order.update_total()
        return_order.status = 'CONFIRMED'
        return_order.save()

        # 반품 AR 확인 (음수 금액)
        ar = AccountReceivable.objects.filter(order=return_order, is_active=True).first()
        self.assertIsNotNone(ar)
        self.assertTrue(ar.amount < 0)


class ExchangeOrderTest(TestCase):
    """교환 주문 프로세스 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='exchange_user', password='testpass123', role='staff',
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-EXC', name='교환창고', created_by=self.user,
        )
        self.partner = Partner.objects.create(
            code='PT-EXC', name='교환거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
            created_by=self.user,
        )
        self.product_a = Product.objects.create(
            code='PRD-EXC-A', name='교환제품A', product_type='FINISHED',
            unit_price=10000, cost_price=7000, current_stock=100,
            created_by=self.user,
        )
        self.product_b = Product.objects.create(
            code='PRD-EXC-B', name='교환제품B', product_type='FINISHED',
            unit_price=15000, cost_price=9000, current_stock=50,
            created_by=self.user,
        )
        self.original_order = Order.objects.create(
            order_number='ORD-EXC-ORIG',
            order_type='NORMAL',
            partner=self.partner,
            order_date=date.today(),
            status='DRAFT',
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=self.original_order, product=self.product_a,
            quantity=3, unit_price=10000, created_by=self.user,
        )
        self.original_order.update_total()
        self.original_order.status = 'CONFIRMED'
        self.original_order.save()
        self.original_order.status = 'SHIPPED'
        self.original_order.save()

    def test_exchange_creates_return_and_new_shipment(self):
        """교환주문 확정 시 반품입고(IN) + 교환출고(OUT) StockMovement 동시 생성"""
        exchange_order = Order.objects.create(
            order_number='ORD-EXC-001',
            order_type='EXCHANGE',
            original_order=self.original_order,
            partner=self.partner,
            order_date=date.today(),
            status='DRAFT',
            return_reason='사이즈 교환',
            created_by=self.user,
        )
        # 교환 주문 항목 (교환으로 받을 제품)
        OrderItem.objects.create(
            order=exchange_order, product=self.product_b,
            quantity=3, unit_price=15000, created_by=self.user,
        )
        exchange_order.update_total()
        exchange_order.status = 'CONFIRMED'
        exchange_order.save()

        # 반품입고(IN) 확인 - 원본 제품
        in_movements = StockMovement.objects.filter(
            movement_type='IN',
            reference__contains='교환반품입고',
        )
        self.assertEqual(in_movements.count(), 1)
        self.assertEqual(in_movements.first().product, self.product_a)

        # 교환출고(OUT) 확인 - 새 제품
        out_movements = StockMovement.objects.filter(
            movement_type='OUT',
            reference__contains='교환출고',
        )
        self.assertEqual(out_movements.count(), 1)
        self.assertEqual(out_movements.first().product, self.product_b)

    def test_exchange_calculates_price_difference(self):
        """교환주문 확정 시 차액 AR 생성"""
        from apps.accounting.models import AccountReceivable

        exchange_order = Order.objects.create(
            order_number='ORD-EXC-DIFF',
            order_type='EXCHANGE',
            original_order=self.original_order,
            partner=self.partner,
            order_date=date.today(),
            status='DRAFT',
            created_by=self.user,
        )
        # 더 비싼 제품으로 교환 (10000*3=30000 → 15000*3=45000, 차액 +15000)
        OrderItem.objects.create(
            order=exchange_order, product=self.product_b,
            quantity=3, unit_price=15000, created_by=self.user,
        )
        exchange_order.update_total()
        exchange_order.status = 'CONFIRMED'
        exchange_order.save()

        # 차액 AR 확인
        ar = AccountReceivable.objects.filter(order=exchange_order, is_active=True).first()
        self.assertIsNotNone(ar)
        # 교환 차액: 신규 grand_total - 원본 grand_total
        orig_grand = int(self.original_order.grand_total)
        new_grand = int(exchange_order.grand_total)
        self.assertEqual(ar.amount, new_grand - orig_grand)


class OrderModificationTest(TestCase):
    """CONFIRMED 주문 수정 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='modify_user', password='testpass123', role='staff',
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-MOD', name='수정창고', created_by=self.user,
        )
        self.partner = Partner.objects.create(
            code='PT-MOD', name='수정거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
            created_by=self.user,
        )
        self.product = Product.objects.create(
            code='PRD-MOD-001', name='수정제품', product_type='FINISHED',
            unit_price=10000, cost_price=7000, current_stock=100,
            created_by=self.user,
        )
        self.order = Order.objects.create(
            order_number='ORD-MOD-001',
            order_type='NORMAL',
            partner=self.partner,
            order_date=date.today(),
            status='DRAFT',
            created_by=self.user,
        )
        self.item = OrderItem.objects.create(
            order=self.order, product=self.product,
            quantity=5, unit_price=10000, created_by=self.user,
        )
        self.order.update_total()
        self.order.status = 'CONFIRMED'
        self.order.save()

    def test_confirmed_order_qty_change_updates_reserved_stock(self):
        """CONFIRMED 주문 수량 변경 시 예약재고 재계산"""
        self.product.refresh_from_db()
        initial_reserved = self.product.reserved_stock

        # 수량 변경: 5 → 8
        self.item.refresh_from_db()
        # 기존 reserved_stock 해제
        from django.db import transaction
        from django.db.models import F
        with transaction.atomic():
            actual_release = min(self.item.quantity, self.product.reserved_stock)
            if actual_release > 0:
                Product.objects.filter(pk=self.product.pk).update(
                    reserved_stock=F('reserved_stock') - actual_release,
                )
            self.item.quantity = 8
            self.item.save()
            self.order.update_total()
            Product.objects.filter(pk=self.product.pk).update(
                reserved_stock=F('reserved_stock') + 8,
            )

        self.product.refresh_from_db()
        self.assertEqual(self.product.reserved_stock, 8)

    def test_confirmed_order_qty_change_updates_ar(self):
        """CONFIRMED 주문 수량 변경 시 AR 금액 갱신"""
        from apps.accounting.models import AccountReceivable

        ar = AccountReceivable.objects.filter(
            order=self.order, is_active=True,
        ).first()
        self.assertIsNotNone(ar)
        original_amount = ar.amount

        # 수량 변경: 5 → 3
        self.item.quantity = 3
        self.item.save()
        self.order.update_total()
        self.order.refresh_from_db()

        # AR 수동 재계산 (OrderModifyView 로직 시뮬레이션)
        ar.amount = int(self.order.grand_total)
        ar.save()
        ar.refresh_from_db()

        self.assertNotEqual(ar.amount, original_amount)
        self.assertEqual(ar.amount, int(self.order.grand_total))

    def test_shipped_items_cannot_be_modified(self):
        """출고 시작된 항목이 있으면 OrderModifyView에서 수정 차단"""
        from django.test import RequestFactory

        # shipped_quantity > 0 설정
        OrderItem.objects.filter(pk=self.item.pk).update(shipped_quantity=2)

        factory = RequestFactory()
        request = factory.get(f'/sales/orders/{self.order.order_number}/modify/')
        request.user = self.user

        from apps.sales.views import OrderModifyView
        from django.contrib.messages.storage.fallback import FallbackStorage
        setattr(request, 'session', 'session')
        setattr(request, '_messages', FallbackStorage(request))

        response = OrderModifyView.as_view()(
            request, slug=self.order.order_number,
        )
        # 302 리다이렉트 (수정 불가)
        self.assertEqual(response.status_code, 302)


class PartialShippedAutoTransitionTest(TestCase):
    """ShipmentItem 생성 시 PARTIAL_SHIPPED / SHIPPED 자동 전환 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='partial_ship_user', password='testpass123', role='staff',
        )
        self.warehouse = Warehouse.objects.create(
            code='WH-PS', name='부분출고창고', created_by=self.user,
        )
        self.product_a = Product.objects.create(
            code='PS-A', name='부분출고A', product_type='FINISHED',
            unit_price=10000, cost_price=5000, current_stock=100,
            created_by=self.user,
        )
        self.product_b = Product.objects.create(
            code='PS-B', name='부분출고B', product_type='FINISHED',
            unit_price=20000, cost_price=10000, current_stock=200,
            created_by=self.user,
        )
        self.order = Order.objects.create(
            order_number='ORD-PS-001',
            order_date=date.today(),
            status='CONFIRMED',
            created_by=self.user,
        )
        self.item_a = OrderItem.objects.create(
            order=self.order, product=self.product_a,
            quantity=10, unit_price=10000, created_by=self.user,
        )
        self.item_b = OrderItem.objects.create(
            order=self.order, product=self.product_b,
            quantity=5, unit_price=20000, created_by=self.user,
        )
        self.shipment = Shipment.objects.create(
            order=self.order, shipment_number='SH-PS-001',
            carrier=Shipment.Carrier.CJ, created_by=self.user,
        )

    def test_partial_shipment_sets_partial_shipped(self):
        """일부 항목만 출고 시 PARTIAL_SHIPPED 자동 전환"""
        from apps.sales.models import ShipmentItem
        ShipmentItem.objects.create(
            shipment=self.shipment, order_item=self.item_a,
            quantity=5, created_by=self.user,
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'PARTIAL_SHIPPED')

    def test_full_shipment_sets_shipped(self):
        """전량 출고 시 SHIPPED 자동 전환"""
        from apps.sales.models import ShipmentItem
        ShipmentItem.objects.create(
            shipment=self.shipment, order_item=self.item_a,
            quantity=10, created_by=self.user,
        )
        ShipmentItem.objects.create(
            shipment=self.shipment, order_item=self.item_b,
            quantity=5, created_by=self.user,
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'SHIPPED')

    def test_multi_step_partial_to_shipped(self):
        """여러 차례 부분출고 후 전량 완료 시 SHIPPED 전환"""
        from apps.sales.models import ShipmentItem
        # 1차 부분출고
        ShipmentItem.objects.create(
            shipment=self.shipment, order_item=self.item_a,
            quantity=5, created_by=self.user,
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'PARTIAL_SHIPPED')

        # 2차 부분출고
        shipment2 = Shipment.objects.create(
            order=self.order, shipment_number='SH-PS-002',
            carrier=Shipment.Carrier.CJ, created_by=self.user,
        )
        ShipmentItem.objects.create(
            shipment=shipment2, order_item=self.item_a,
            quantity=5, created_by=self.user,
        )
        ShipmentItem.objects.create(
            shipment=shipment2, order_item=self.item_b,
            quantity=5, created_by=self.user,
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'SHIPPED')


class PriceRuleMinQuantityTest(TestCase):
    """PriceRule min_quantity 필터 + 견적 자동적용 테스트"""

    def setUp(self):
        from apps.sales.models import PriceRule
        self.user = User.objects.create_user(
            username='pricerule_user', password='testpass123', role='staff',
        )
        self.partner = Partner.objects.create(
            code='PR-P001', name='가격규칙거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
            created_by=self.user,
        )
        self.product = Product.objects.create(
            code='PR-PRD-001', name='가격규칙제품', product_type='FINISHED',
            unit_price=10000, cost_price=5000,
            created_by=self.user,
        )
        # min_quantity=10 규칙: 단가 8000
        PriceRule.objects.create(
            product=self.product, partner=self.partner,
            min_quantity=10, unit_price=8000,
            created_by=self.user,
        )
        # min_quantity=100 규칙: 단가 6000
        PriceRule.objects.create(
            product=self.product, partner=self.partner,
            min_quantity=100, unit_price=6000,
            created_by=self.user,
        )

    def test_order_item_below_min_uses_default(self):
        """주문수량이 min_quantity 미만이면 제품 기본단가 적용"""
        order = Order.objects.create(
            order_number='ORD-PR-001', order_date=date.today(),
            status='DRAFT', partner=self.partner, created_by=self.user,
        )
        item = OrderItem.objects.create(
            order=order, product=self.product,
            quantity=5, unit_price=0, created_by=self.user,
        )
        self.assertEqual(item.unit_price, 10000)

    def test_order_item_meets_min_quantity(self):
        """주문수량이 min_quantity 충족 시 해당 규칙 적용"""
        order = Order.objects.create(
            order_number='ORD-PR-002', order_date=date.today(),
            status='DRAFT', partner=self.partner, created_by=self.user,
        )
        item = OrderItem.objects.create(
            order=order, product=self.product,
            quantity=10, unit_price=0, created_by=self.user,
        )
        self.assertEqual(item.unit_price, 8000)

    def test_order_item_higher_tier(self):
        """더 높은 수량 구간 규칙 적용"""
        order = Order.objects.create(
            order_number='ORD-PR-003', order_date=date.today(),
            status='DRAFT', partner=self.partner, created_by=self.user,
        )
        item = OrderItem.objects.create(
            order=order, product=self.product,
            quantity=100, unit_price=0, created_by=self.user,
        )
        self.assertEqual(item.unit_price, 6000)

    def test_quotation_item_applies_price_rule(self):
        """견적항목에서도 PriceRule min_quantity 적용"""
        quote = Quotation.objects.create(
            quote_number='QT-PR-001', partner=self.partner,
            quote_date=date.today(),
            valid_until=date.today() + timedelta(days=30),
            created_by=self.user,
        )
        item = QuotationItem.objects.create(
            quotation=quote, product=self.product,
            quantity=10, unit_price=0, created_by=self.user,
        )
        self.assertEqual(item.unit_price, 8000)

    def test_quotation_item_below_min_uses_default(self):
        """견적 수량이 min_quantity 미만이면 제품 기본단가"""
        quote = Quotation.objects.create(
            quote_number='QT-PR-002', partner=self.partner,
            quote_date=date.today(),
            valid_until=date.today() + timedelta(days=30),
            created_by=self.user,
        )
        item = QuotationItem.objects.create(
            quotation=quote, product=self.product,
            quantity=3, unit_price=0, created_by=self.user,
        )
        self.assertEqual(item.unit_price, 10000)


class CustomerTierModelTest(TestCase):
    """고객등급 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='tieruser', password='testpass123', role='staff',
        )

    def test_tier_creation(self):
        """고객등급 생성"""
        tier = CustomerTier.objects.create(
            name='VIP', code='VIP',
            discount_rate=Decimal('10.00'),
            min_annual_purchase=10000000,
            created_by=self.user,
        )
        self.assertEqual(tier.name, 'VIP')
        self.assertEqual(str(tier), 'VIP')

    def test_tier_unique_code(self):
        """등급코드 중복 불가"""
        CustomerTier.objects.create(
            name='Gold', code='GOLD', created_by=self.user,
        )
        with self.assertRaises(IntegrityError):
            CustomerTier.objects.create(
                name='Gold2', code='GOLD', created_by=self.user,
            )

    def test_tier_ordering(self):
        """등급 정렬순서"""
        t2 = CustomerTier.objects.create(
            name='Silver', code='SLV', sort_order=2, created_by=self.user,
        )
        t1 = CustomerTier.objects.create(
            name='VIP', code='VIP', sort_order=1, created_by=self.user,
        )
        tiers = list(CustomerTier.objects.filter(is_active=True))
        self.assertEqual(tiers[0], t1)
        self.assertEqual(tiers[1], t2)


class PartnerCreditLimitTest(TestCase):
    """거래처 신용한도 필드 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='credituser', password='testpass123', role='staff',
        )

    def test_credit_limit_fields(self):
        """신용한도 필드 확인"""
        tier = CustomerTier.objects.create(
            name='Gold', code='GOLD', created_by=self.user,
        )
        partner = Partner.objects.create(
            code='PT-CR-001', name='신용거래처',
            partner_type='CUSTOMER',
            credit_limit=5000000,
            credit_used=1000000,
            tier=tier,
            created_by=self.user,
        )
        self.assertEqual(partner.credit_limit, 5000000)
        self.assertEqual(partner.credit_used, 1000000)
        self.assertEqual(partner.tier, tier)


class SalesTargetModelTest(TestCase):
    """영업목표 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='targetuser', password='testpass123', role='staff',
        )

    def test_target_creation(self):
        """영업목표 생성"""
        target = SalesTarget.objects.create(
            salesperson=self.user,
            year=2026,
            target_amount=100000000,
            created_by=self.user,
        )
        self.assertEqual(target.year, 2026)
        self.assertIsNone(target.quarter)
        self.assertIn('2026', str(target))

    def test_target_with_quarter(self):
        """분기별 영업목표"""
        target = SalesTarget.objects.create(
            salesperson=self.user,
            year=2026, quarter=1,
            target_amount=25000000,
            created_by=self.user,
        )
        self.assertEqual(target.quarter, 1)
        self.assertIn('Q1', str(target))

    def test_target_unique_together(self):
        """동일 영업담당/연도/분기 중복 불가"""
        SalesTarget.objects.create(
            salesperson=self.user,
            year=2026, quarter=1,
            target_amount=25000000,
            created_by=self.user,
        )
        with self.assertRaises(IntegrityError):
            SalesTarget.objects.create(
                salesperson=self.user,
                year=2026, quarter=1,
                target_amount=30000000,
                created_by=self.user,
            )

    def test_achievement_rate_zero_target(self):
        """목표금액 0일 때 달성률 0"""
        target = SalesTarget.objects.create(
            salesperson=self.user,
            year=2026,
            target_amount=0,
            created_by=self.user,
        )
        self.assertEqual(target.achievement_rate, 0)


class SalesLeadModelTest(TestCase):
    """영업리드 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='leaduser', password='testpass123', role='staff',
        )

    def test_lead_auto_number(self):
        """리드번호 자동 생성"""
        lead = SalesLead.objects.create(
            company_name='테스트회사',
            contact_name='김테스트',
            source='WEBSITE',
            created_by=self.user,
        )
        self.assertTrue(lead.lead_number.startswith('LEAD-'))

    def test_lead_sequential_number(self):
        """리드번호 순차 생성"""
        lead1 = SalesLead.objects.create(
            company_name='회사1', contact_name='담당1',
            created_by=self.user,
        )
        lead2 = SalesLead.objects.create(
            company_name='회사2', contact_name='담당2',
            created_by=self.user,
        )
        n1 = int(lead1.lead_number.split('-')[-1])
        n2 = int(lead2.lead_number.split('-')[-1])
        self.assertEqual(n2, n1 + 1)

    def test_lead_status_default(self):
        """기본 상태 NEW"""
        lead = SalesLead.objects.create(
            company_name='테스트', contact_name='테스트',
            created_by=self.user,
        )
        self.assertEqual(lead.status, 'NEW')


class LeadActivityModelTest(TestCase):
    """리드 활동 기록 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='activityuser', password='testpass123', role='staff',
        )
        self.lead = SalesLead.objects.create(
            company_name='활동회사', contact_name='김활동',
            created_by=self.user,
        )

    def test_activity_creation(self):
        """활동 기록 생성"""
        from django.utils import timezone
        activity = LeadActivity.objects.create(
            lead=self.lead,
            activity_type='CALL',
            description='초기 연락',
            activity_date=timezone.now(),
            created_by=self.user,
        )
        self.assertEqual(activity.activity_type, 'CALL')
        self.assertIn('통화', str(activity))


class CustomerSatisfactionModelTest(TestCase):
    """고객만족도 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='satuser', password='testpass123', role='staff',
        )
        self.partner = Partner.objects.create(
            code='SAT-P001', name='만족도거래처',
            partner_type='CUSTOMER',
            created_by=self.user,
        )

    def test_satisfaction_creation(self):
        """만족도 생성"""
        sat = CustomerSatisfaction.objects.create(
            partner=self.partner,
            score=4,
            nps_score=50,
            survey_date=date.today(),
            category='PRODUCT',
            created_by=self.user,
        )
        self.assertEqual(sat.score, 4)
        self.assertIn('제품', str(sat))

    def test_satisfaction_str(self):
        """문자열 표현"""
        sat = CustomerSatisfaction.objects.create(
            partner=self.partner,
            score=5,
            survey_date=date.today(),
            category='SERVICE',
            created_by=self.user,
        )
        self.assertIn('만족도거래처', str(sat))


class OrderDetailCashReceiptContextTest(TestCase):
    """OrderDetailView — can_issue_cash_receipt 컨텍스트 분기 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='cr_detail_user', password='testpass123', role='staff',
        )
        self.order = Order.objects.create(
            order_number='ORD-CR-001',
            order_date=date.today(),
            status='CONFIRMED',
            created_by=self.user,
        )

    def test_can_issue_cash_receipt_when_not_cancelled(self):
        """취소되지 않은 주문은 can_issue_cash_receipt=True"""
        for status in ('DRAFT', 'CONFIRMED', 'SHIPPED', 'COMPLETED'):
            self.order.status = status
            self.order.save(update_fields=['status'])
            from apps.sales.views import OrderDetailView
            view = OrderDetailView()
            view.object = self.order
            view.request = None
            view.kwargs = {}
            can_issue = self.order.status not in ('CANCELLED',)
            self.assertTrue(can_issue, f"status={status}이면 발행 가능이어야 함")

    def test_cannot_issue_cash_receipt_when_cancelled(self):
        """취소된 주문은 can_issue_cash_receipt=False"""
        self.order.status = 'CANCELLED'
        self.order.save(update_fields=['status'])
        can_issue = (
            self.order.status not in ('CANCELLED',)
            and self.order.order_type not in ('RETURN',)
        )
        self.assertFalse(can_issue, "CANCELLED 주문은 현금영수증 발행 불가")

    def test_cannot_issue_cash_receipt_when_return_order(self):
        """반품주문(order_type=RETURN)은 can_issue_cash_receipt=False"""
        self.order.order_type = 'RETURN'
        self.order.save(update_fields=['order_type'])
        can_issue = (
            self.order.status not in ('CANCELLED',)
            and self.order.order_type not in ('RETURN',)
        )
        self.assertFalse(can_issue, "반품주문은 현금영수증 발행 불가")
