import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import Page


@pytest.fixture
def base_url():
    return 'http://localhost:8000'


@pytest.fixture
def admin_user(db):
    """관리자 테스트 사용자 생성"""
    User = get_user_model()
    user = User.objects.create_user(
        username='testadmin',
        password='testpass123!',
        role='admin',
        name='테스트관리자',
    )
    return user


@pytest.fixture
def logged_in_page(page: Page, admin_user, live_server):
    """로그인된 페이지 반환"""
    page.goto(f'{live_server.url}/accounts/login/')
    page.wait_for_load_state('networkidle')
    page.fill('input[name="username"]', 'testadmin')
    page.fill('input[name="password"]', 'testpass123!')
    page.click('button[type="submit"]')
    page.wait_for_url(f'{live_server.url}/')
    page.wait_for_load_state('networkidle')
    return page


@pytest.fixture
def live_url(live_server):
    """live_server URL 헬퍼"""
    return live_server.url
