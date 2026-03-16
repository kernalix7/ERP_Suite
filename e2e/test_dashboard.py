import pytest
from playwright.sync_api import Page, expect


@pytest.mark.django_db
class TestDashboard:
    """대시보드 E2E 테스트"""

    def test_dashboard_loads(self, logged_in_page: Page, live_url):
        """대시보드 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page

        expect(page).to_have_title('대시보드 - ERP Suite')
        assert page.url == f'{live_url}/'

    def test_dashboard_shows_kpi_cards(self, logged_in_page: Page):
        """대시보드에 KPI 카드가 표시되는지 확인"""
        page = logged_in_page

        # 4개의 KPI 카드 확인 (금일 주문, 재고부족, 진행중 생산, 미처리 AS)
        kpi_cards = page.locator('.bg-white.shadow-sm.rounded-xl.p-5')
        expect(kpi_cards.first).to_be_visible()

        # 각 KPI 카드 텍스트 확인
        page_content = page.content()
        assert '금일 주문' in page_content
        assert '재고부족' in page_content
        assert '진행중 생산' in page_content
        assert '미처리 AS' in page_content

    def test_dashboard_has_charts(self, logged_in_page: Page):
        """대시보드에 차트 데이터 스크립트가 존재하는지 확인"""
        page = logged_in_page

        # Chart.js 데이터 스크립트 태그 확인
        expect(page.locator('#chart-revenue-labels')).to_be_attached()
        expect(page.locator('#chart-revenue-data')).to_be_attached()
        expect(page.locator('#chart-production-labels')).to_be_attached()
