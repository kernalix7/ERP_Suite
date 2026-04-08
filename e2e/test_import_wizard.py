import pytest
from playwright.sync_api import Page, expect


@pytest.mark.django_db
class TestMarketplaceImportWizard:
    """마켓플레이스 Import Wizard E2E 테스트"""

    def test_wizard_fetch_page_loads(self, logged_in_page: Page, live_url):
        """Wizard 주문 가져오기 페이지가 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/marketplace/wizard/fetch/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        # 위저드 시작 페이지 또는 마켓플레이스 관련 콘텐츠 확인
        assert '마켓플레이스' in page_content or '주문' in page_content or '가져오기' in page_content

    def test_marketplace_sync_page_loads(self, logged_in_page: Page, live_url):
        """마켓플레이스 동기화 페이지가 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/marketplace/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '마켓플레이스' in page_content or '동기화' in page_content


@pytest.mark.django_db
class TestExcelImport:
    """Excel 일괄 가져오기 E2E 테스트"""

    def test_product_import_page_loads(self, logged_in_page: Page, live_url):
        """제품 가져오기 페이지가 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/inventory/products/import/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '가져오기' in page_content or 'import' in page_content.lower()

    def test_import_page_has_file_upload(self, logged_in_page: Page, live_url):
        """가져오기 페이지에 파일 업로드 필드가 있는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/inventory/products/import/')
        page.wait_for_load_state('networkidle')

        file_input = page.locator('input[type="file"]')
        expect(file_input).to_be_attached()
