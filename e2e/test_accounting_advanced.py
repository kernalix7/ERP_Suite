import pytest
from playwright.sync_api import Page


@pytest.mark.django_db
class TestAccountingAdvancedWorkflow:
    """회계 고급 기능 E2E 테스트 (Phase 4-5)"""

    def test_bank_reconciliation_loads(self, logged_in_page: Page, live_url):
        """은행 대사 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/accounting/bank-reconciliation/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '은행' in page_content or '대사' in page_content or '잔액' in page_content

    def test_account_ledger_loads(self, logged_in_page: Page, live_url):
        """계정별 원장 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/accounting/ledger/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '원장' in page_content or '계정' in page_content

    def test_trial_balance_loads(self, logged_in_page: Page, live_url):
        """시산표 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/accounting/trial-balance/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '시산표' in page_content or '차변' in page_content or '대변' in page_content

    def test_budget_list_loads(self, logged_in_page: Page, live_url):
        """예산관리 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/accounting/budget/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '예산' in page_content

    def test_budget_create_page_loads(self, logged_in_page: Page, live_url):
        """예산 등록 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/accounting/budget/create/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '예산' in page_content
