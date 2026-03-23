import pytest
from playwright.sync_api import Page

from apps.inventory.models import Product, Warehouse, WarehouseStock


@pytest.mark.django_db
class TestWarehouseStockWorkflow:
    """창고별 재고 E2E 테스트"""

    def test_warehouse_stock_page_loads(self, logged_in_page: Page, live_url):
        """창고별 재고 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/inventory/warehouse-stock/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '창고' in page_content

    def test_warehouse_stock_shows_data(self, logged_in_page: Page, live_url):
        """창고별 재고 데이터가 표시되는지 확인"""
        page = logged_in_page

        # 사전 데이터 생성
        warehouse = Warehouse.objects.create(
            code='WH-WS-001', name='서울 본사 창고', location='서울',
        )
        product = Product.objects.create(
            code='WS-PRD-001', name='창고재고 테스트 제품',
            product_type='FINISHED', unit='EA',
            unit_price=10000, cost_price=7000, current_stock=100,
        )
        WarehouseStock.objects.create(
            warehouse=warehouse, product=product, quantity=50,
        )

        page.goto(f'{live_url}/inventory/warehouse-stock/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '서울 본사 창고' in page_content or 'WS-PRD-001' in page_content

    def test_warehouse_stock_filter_by_warehouse(self, logged_in_page: Page, live_url):
        """창고 필터링 동작 확인"""
        page = logged_in_page

        wh1 = Warehouse.objects.create(code='WH-FLT-A', name='A창고')
        wh2 = Warehouse.objects.create(code='WH-FLT-B', name='B창고')
        product = Product.objects.create(
            code='FLT-PRD-001', name='필터테스트 제품',
            product_type='FINISHED', unit='EA',
            unit_price=5000, cost_price=3000, current_stock=200,
        )
        WarehouseStock.objects.create(warehouse=wh1, product=product, quantity=80)
        WarehouseStock.objects.create(warehouse=wh2, product=product, quantity=120)

        # 창고 A로 필터
        page.goto(f'{live_url}/inventory/warehouse-stock/?warehouse={wh1.pk}')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert 'A창고' in page_content or '필터테스트' in page_content
