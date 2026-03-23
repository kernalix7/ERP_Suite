import pytest
from playwright.sync_api import Page

from apps.inventory.models import Warehouse


@pytest.mark.django_db
class TestStockCountWorkflow:
    """재고실사 워크플로우 E2E 테스트"""

    def test_stock_count_list_loads(self, logged_in_page: Page, live_url):
        """재고실사 목록 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/inventory/stock-count/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '재고실사' in page_content or '실사' in page_content

    def test_stock_count_create_page_loads(self, logged_in_page: Page, live_url):
        """재고실사 생성 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page

        Warehouse.objects.create(code='WH-SC-001', name='실사테스트 창고')

        page.goto(f'{live_url}/inventory/stock-count/create/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '창고' in page_content or '실사' in page_content
