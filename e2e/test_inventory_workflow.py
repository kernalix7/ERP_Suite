import pytest
from playwright.sync_api import Page, expect

from apps.inventory.models import Category, Product, Warehouse


@pytest.mark.django_db
class TestInventoryWorkflow:
    """재고 관리 워크플로우 E2E 테스트"""

    def test_product_list_loads(self, logged_in_page: Page, live_url):
        """제품 목록 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/inventory/products/')
        page.wait_for_load_state('networkidle')

        expect(page).to_have_title('제품 목록 - ERP Suite')

    def test_create_product(self, logged_in_page: Page, live_url):
        """제품 생성 워크플로우 테스트"""
        page = logged_in_page

        # 제품 등록 페이지로 이동
        page.goto(f'{live_url}/inventory/products/create/')
        page.wait_for_load_state('networkidle')

        # 폼 필드 채우기
        page.fill('input[name="code"]', 'TEST-PRD-001')
        page.fill('input[name="name"]', '테스트 완제품')
        page.select_option('select[name="product_type"]', 'FINISHED')
        page.fill('input[name="unit"]', 'EA')
        page.fill('input[name="unit_price"]', '50000')
        page.fill('input[name="cost_price"]', '30000')
        page.fill('input[name="safety_stock"]', '10')

        # 저장 버튼 클릭
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')

        # 제품 목록 페이지로 리다이렉트 확인
        assert '/inventory/products/' in page.url

        # 생성된 제품이 목록에 표시되는지 확인
        page_content = page.content()
        assert 'TEST-PRD-001' in page_content
        assert '테스트 완제품' in page_content

        # DB에서 제품 확인
        product = Product.objects.get(code='TEST-PRD-001')
        assert product.name == '테스트 완제품'
        assert product.product_type == 'FINISHED'
        assert product.unit_price == 50000
        assert product.cost_price == 30000
        assert product.safety_stock == 10

    def test_create_stock_movement(self, logged_in_page: Page, live_url):
        """입출고 등록 워크플로우 테스트"""
        page = logged_in_page

        # 사전 데이터 생성: 제품과 창고
        product = Product.objects.create(
            code='MV-PRD-001',
            name='입출고테스트 제품',
            product_type='FINISHED',
            unit='EA',
            unit_price=10000,
            cost_price=7000,
            current_stock=0,
        )
        warehouse = Warehouse.objects.create(
            code='WH-001',
            name='테스트 창고',
            location='서울시 강남구',
        )

        # 입출고 등록 페이지로 이동
        page.goto(f'{live_url}/inventory/movements/create/')
        page.wait_for_load_state('networkidle')

        # 폼 필드 채우기
        page.fill('input[name="movement_number"]', 'MV-2026-0001')
        page.select_option('select[name="movement_type"]', 'IN')
        page.select_option('select[name="product"]', str(product.pk))
        page.select_option('select[name="warehouse"]', str(warehouse.pk))
        page.fill('input[name="quantity"]', '100')
        page.fill('input[name="unit_price"]', '7000')
        page.fill('input[name="movement_date"]', '2026-03-16')
        page.fill('input[name="reference"]', '테스트 입고')

        # 저장 버튼 클릭
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')

        # 입출고 목록 페이지로 리다이렉트 확인
        assert '/inventory/movements/' in page.url

        # 생성된 입출고가 목록에 표시되는지 확인
        page_content = page.content()
        assert 'MV-2026-0001' in page_content

        # DB에서 재고 변경 확인
        product.refresh_from_db()
        assert product.current_stock == 100
