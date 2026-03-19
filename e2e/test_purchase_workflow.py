import pytest
from playwright.sync_api import Page, expect

from apps.inventory.models import Product
from apps.purchase.models import PurchaseOrder, PurchaseOrderItem
from apps.sales.models import Partner


@pytest.mark.django_db
class TestPurchaseWorkflow:
    """구매 관리 워크플로우 E2E 테스트"""

    def test_po_list_loads(self, logged_in_page: Page, live_url):
        """발주 목록 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/purchase/orders/')
        page.wait_for_load_state('networkidle')

        expect(page).to_have_title('발주 목록 - ERP Suite')

    def test_create_purchase_order(self, logged_in_page: Page, live_url):
        """발주서 생성 워크플로우 테스트"""
        page = logged_in_page

        # 사전 데이터 생성
        partner = Partner.objects.create(
            code='PTN-PO-001',
            name='발주테스트 거래처',
            partner_type='SUPPLIER',
        )
        product = Product.objects.create(
            code='PO-PRD-001',
            name='발주테스트 원자재',
            product_type='RAW',
            unit='KG',
            unit_price=5000,
            cost_price=3000,
            current_stock=0,
        )

        # 발주서 등록 페이지로 이동
        page.goto(f'{live_url}/purchase/orders/create/')
        page.wait_for_load_state('networkidle')

        # 폼 필드 채우기
        page.fill('input[name="po_number"]', 'PO-2026-0001')
        page.select_option('select[name="partner"]', str(partner.pk))
        page.fill('input[name="order_date"]', '2026-03-16')
        page.fill('input[name="delivery_date"]', '2026-03-25')

        # 발주 항목 (인라인 폼셋) 채우기
        page.select_option('select[name="items-0-product"]', str(product.pk))
        page.fill('input[name="items-0-quantity"]', '100')
        page.fill('input[name="items-0-unit_price"]', '5000')

        # 저장 버튼 클릭
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')

        # 발주 목록으로 리다이렉트 확인
        assert '/purchase/orders/' in page.url

        # DB에서 발주서 확인
        po = PurchaseOrder.objects.get(po_number='PO-2026-0001')
        assert po.partner == partner
        assert po.status == 'DRAFT'

    def test_create_goods_receipt(self, logged_in_page: Page, live_url):
        """입고확인 등록 후 재고 증가 확인"""
        page = logged_in_page

        # 사전 데이터 생성
        partner = Partner.objects.create(
            code='PTN-RCV-001',
            name='입고테스트 거래처',
            partner_type='SUPPLIER',
        )
        product = Product.objects.create(
            code='RCV-PRD-001',
            name='입고테스트 원자재',
            product_type='RAW',
            unit='KG',
            unit_price=5000,
            cost_price=3000,
            current_stock=0,
        )
        po = PurchaseOrder.objects.create(
            po_number='PO-RCV-0001',
            partner=partner,
            order_date='2026-03-16',
            status='CONFIRMED',
        )
        po_item = PurchaseOrderItem.objects.create(
            purchase_order=po,
            product=product,
            quantity=100,
            unit_price=5000,
            amount=500000,
            tax_amount=50000,
        )

        # 입고확인 등록 페이지로 이동
        page.goto(f'{live_url}/purchase/receipts/create/')
        page.wait_for_load_state('networkidle')

        # 폼 필드 채우기
        page.fill('input[name="receipt_number"]', 'GR-2026-0001')
        page.select_option('select[name="purchase_order"]', str(po.pk))
        page.fill('input[name="receipt_date"]', '2026-03-18')

        # 입고 항목 채우기
        page.select_option('select[name="items-0-po_item"]', str(po_item.pk))
        page.fill('input[name="items-0-received_quantity"]', '100')

        # 저장 버튼 클릭
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')

        # 리다이렉트 확인
        assert '/purchase/receipts/' in page.url

        # 재고 변동 확인 (signal에 의해 자동 입고 처리)
        product.refresh_from_db()
        assert product.current_stock >= 100
