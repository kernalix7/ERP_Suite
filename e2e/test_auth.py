import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import Page, expect


@pytest.mark.django_db
class TestAuth:
    """인증 관련 E2E 테스트"""

    def test_login_page_loads(self, page: Page, live_server):
        """로그인 페이지가 정상적으로 로드되는지 확인"""
        page.goto(f'{live_server.url}/accounts/login/')
        page.wait_for_load_state('networkidle')

        # 페이지 제목 확인
        expect(page).to_have_title('로그인 - ERP Suite')

        # 로그인 폼 요소 확인
        expect(page.locator('input[name="username"]')).to_be_visible()
        expect(page.locator('input[name="password"]')).to_be_visible()
        expect(page.locator('button[type="submit"]')).to_be_visible()
        expect(page.locator('button[type="submit"]')).to_contain_text('로그인')

        # ERP Suite 텍스트 확인
        expect(page.locator('h1')).to_contain_text('ERP Suite')

    def test_login_success(self, page: Page, admin_user, live_server):
        """올바른 자격증명으로 로그인 성공 테스트"""
        page.goto(f'{live_server.url}/accounts/login/')
        page.wait_for_load_state('networkidle')

        page.fill('input[name="username"]', 'testadmin')
        page.fill('input[name="password"]', 'testpass123!')
        page.click('button[type="submit"]')

        # 대시보드로 리다이렉트 확인
        page.wait_for_url(f'{live_server.url}/')
        page.wait_for_load_state('networkidle')

        # 대시보드 페이지 로드 확인
        expect(page).to_have_title('대시보드 - ERP Suite')

    def test_login_wrong_password(self, page: Page, admin_user, live_server):
        """잘못된 비밀번호로 로그인 실패 테스트"""
        page.goto(f'{live_server.url}/accounts/login/')
        page.wait_for_load_state('networkidle')

        page.fill('input[name="username"]', 'testadmin')
        page.fill('input[name="password"]', 'wrongpassword')
        page.click('button[type="submit"]')

        page.wait_for_load_state('networkidle')

        # 로그인 페이지에 머물러야 함
        assert '/accounts/login/' in page.url

        # 에러 메시지 표시 확인
        error_area = page.locator('.bg-red-50')
        expect(error_area).to_be_visible()

    def test_redirect_to_login_when_not_authenticated(self, page: Page, live_server):
        """비인증 상태에서 보호된 페이지 접근 시 로그인 페이지로 리다이렉트 확인"""
        # 대시보드 접근 시도
        page.goto(f'{live_server.url}/')
        page.wait_for_load_state('networkidle')

        # 로그인 페이지로 리다이렉트 확인
        assert '/accounts/login/' in page.url

        # 재고 페이지 접근 시도
        page.goto(f'{live_server.url}/inventory/products/')
        page.wait_for_load_state('networkidle')
        assert '/accounts/login/' in page.url

        # 주문 페이지 접근 시도
        page.goto(f'{live_server.url}/sales/orders/')
        page.wait_for_load_state('networkidle')
        assert '/accounts/login/' in page.url
