import pytest
from playwright.sync_api import Page, expect

from apps.accounting.models import TaxInvoice
from apps.sales.models import Partner


@pytest.mark.django_db
class TestAccountingWorkflow:
    """회계 관리 워크플로우 E2E 테스트"""

    def test_accounting_dashboard_loads(self, logged_in_page: Page, live_url):
        """회계 대시보드가 정상적으로 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/accounting/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '회계' in page_content or '재무' in page_content

    def test_create_tax_invoice(self, logged_in_page: Page, live_url):
        """세금계산서 발행 워크플로우 테스트"""
        page = logged_in_page

        # 사전 데이터 생성
        partner = Partner.objects.create(
            code='PTN-TI-001',
            name='세금계산서 테스트 거래처',
            partner_type='CUSTOMER',
            business_number='123-45-67890',
        )

        # 세금계산서 등록 페이지로 이동
        page.goto(f'{live_url}/accounting/tax-invoices/create/')
        page.wait_for_load_state('networkidle')

        # 폼 필드 채우기
        page.fill('input[name="invoice_number"]', 'TI-2026-0001')
        page.select_option('select[name="partner"]', str(partner.pk))
        page.fill('input[name="issue_date"]', '2026-03-16')
        page.select_option('select[name="invoice_type"]', 'SALES')
        page.fill('input[name="supply_amount"]', '1000000')
        page.fill('input[name="tax_amount"]', '100000')
        page.fill('input[name="total_amount"]', '1100000')

        # 저장 버튼 클릭
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')

        # 세금계산서 목록으로 리다이렉트 확인
        assert '/accounting/tax-invoices/' in page.url

        # DB에서 세금계산서 확인
        invoice = TaxInvoice.objects.get(invoice_number='TI-2026-0001')
        assert invoice.partner == partner
        assert invoice.supply_amount == 1000000
        assert invoice.tax_amount == 100000

    def test_voucher_list_loads(self, logged_in_page: Page, live_url):
        """전표 목록 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/accounting/vouchers/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '전표' in page_content

    def test_approval_list_loads(self, logged_in_page: Page, live_url):
        """결재 목록 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/accounting/approvals/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '결재' in page_content

    def test_monthly_pl_loads(self, logged_in_page: Page, live_url):
        """월별 손익 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/accounting/monthly-pl/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '손익' in page_content or '매출' in page_content
