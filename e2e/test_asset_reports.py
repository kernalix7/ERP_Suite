import pytest
from playwright.sync_api import Page, expect


@pytest.mark.django_db
class TestAssetReports:
    """자산 리포트 E2E 테스트"""

    def test_asset_register_report_page(self, logged_in_page: Page, live_url):
        """자산대장 리포트 페이지 접근"""
        page = logged_in_page
        page.goto(f'{live_url}/asset/report/register/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '자산' in page_content

    def test_asset_register_excel_download(self, logged_in_page: Page, live_url):
        """자산대장 Excel 다운로드 엔드포인트가 응답하는지 확인"""
        page = logged_in_page
        response = page.goto(f'{live_url}/asset/report/register/excel/')

        # Excel 다운로드 또는 리다이렉트
        assert response.status in [200, 302]

    def test_asset_summary_page(self, logged_in_page: Page, live_url):
        """자산 요약 페이지 접근"""
        page = logged_in_page
        page.goto(f'{live_url}/asset/summary/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '자산' in page_content

    def test_depreciation_run_page(self, logged_in_page: Page, live_url):
        """감가상각 실행 페이지 접근"""
        page = logged_in_page
        page.goto(f'{live_url}/asset/depreciation-run/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '감가상각' in page_content or '자산' in page_content

    def test_asset_category_list_page(self, logged_in_page: Page, live_url):
        """자산 분류 목록 접근"""
        page = logged_in_page
        page.goto(f'{live_url}/asset/categories/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '분류' in page_content or '자산' in page_content


@pytest.mark.django_db
class TestDashboardAssetWidgets:
    """대시보드 자산 위젯 E2E 테스트"""

    def test_dashboard_has_asset_widgets(self, logged_in_page: Page):
        """대시보드에 자산 위젯 카드가 표시되는지 확인"""
        page = logged_in_page

        page_content = page.content()
        assert '자산 현황' in page_content
        assert '인증 만료 임박' in page_content
        assert '활성 리스 계약' in page_content
        assert '자산 취득원가' in page_content
