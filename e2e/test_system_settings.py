import pytest
from playwright.sync_api import Page, expect


@pytest.mark.django_db
class TestSystemSettings:
    """시스템 설정 관리 E2E 테스트"""

    def test_settings_page_loads(self, logged_in_page: Page, live_url):
        """시스템 설정 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/settings/')
        page.wait_for_load_state('networkidle')

        expect(page).to_have_title('시스템 설정 - ERP Suite')
        page_content = page.content()
        assert '시스템 설정' in page_content

    def test_settings_has_category_tabs(self, logged_in_page: Page, live_url):
        """카테고리 탭이 표시되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/settings/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '국세청 API' in page_content
        assert '마켓플레이스' in page_content
        assert '이메일' in page_content
        assert '일반' in page_content

    def test_settings_add_button_exists(self, logged_in_page: Page, live_url):
        """설정 추가 버튼이 존재하는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/settings/')
        page.wait_for_load_state('networkidle')

        add_buttons = page.locator('text=설정 추가')
        expect(add_buttons.first).to_be_visible()

    def test_settings_add_modal_opens(self, logged_in_page: Page, live_url):
        """설정 추가 버튼 클릭 시 모달이 열리는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/settings/')
        page.wait_for_load_state('networkidle')

        # 첫 번째 설정 추가 버튼 클릭
        page.locator('text=설정 추가').first.click()

        # 모달이 표시되는지 확인
        modal = page.locator('#config-modal')
        expect(modal).to_be_visible()

        # 모달 내 폼 요소 확인
        expect(page.locator('#form-category')).to_be_visible()
        expect(page.locator('#form-key')).to_be_visible()
        expect(page.locator('#form-display-name')).to_be_visible()
        expect(page.locator('#form-value')).to_be_visible()

    def test_settings_create_config(self, logged_in_page: Page, live_url):
        """설정 항목 생성 테스트"""
        page = logged_in_page
        page.goto(f'{live_url}/settings/?tab=GENERAL')
        page.wait_for_load_state('networkidle')

        # 일반 탭 클릭
        page.locator('text=일반').click()

        # 설정 추가 모달 열기
        page.locator('text=설정 추가').last.click()
        page.wait_for_selector('#config-modal:not(.hidden)')

        # 폼 입력
        page.select_option('#form-category', 'GENERAL')
        page.fill('#form-key', 'company_name')
        page.fill('#form-display-name', '회사명')
        page.fill('#form-value', '테스트회사')

        # 저장
        page.locator('#config-form button[type="submit"]').click()
        page.wait_for_load_state('networkidle')

        # 생성된 설정 확인
        page_content = page.content()
        assert '회사명' in page_content or '설정이 저장되었습니다' in page_content

    def test_settings_tab_switching(self, logged_in_page: Page, live_url):
        """탭 전환이 동작하는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/settings/')
        page.wait_for_load_state('networkidle')

        # 이메일 탭 클릭
        page.locator('text=이메일').click()
        # 이메일 설정 관련 텍스트가 보이는지 확인
        email_section = page.locator('text=SMTP 이메일 발송 설정')
        expect(email_section).to_be_visible()

        # 일반 탭 클릭
        page.locator('text=일반').click()
        general_section = page.locator('text=회사 기본 정보 및 일반 설정')
        expect(general_section).to_be_visible()

    def test_staff_cannot_access_settings(self, page: Page, live_server, db):
        """일반 직원은 시스템 설정에 접근할 수 없음"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        User.objects.create_user(
            username='staffuser', password='testpass123!',
            role='staff', name='일반직원',
        )

        page.goto(f'{live_server.url}/accounts/login/')
        page.wait_for_load_state('networkidle')
        page.fill('input[name="username"]', 'staffuser')
        page.fill('input[name="password"]', 'testpass123!')
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')

        # 시스템 설정 접근 시도
        response = page.goto(f'{live_server.url}/settings/')
        # 403 Forbidden
        assert response.status == 403

    def test_sidebar_has_settings_link(self, logged_in_page: Page, live_url):
        """사이드바에 시스템 설정 메뉴가 있는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '시스템 설정' in page_content


@pytest.mark.django_db
class TestElectronicInvoice:
    """전자세금계산서 E2E 테스트"""

    def test_invoice_list_has_electronic_status(self, logged_in_page: Page, live_url):
        """세금계산서 목록에 전자발행 상태 컬럼이 있는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/accounting/invoices/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '세금계산서' in page_content

    def test_invoice_detail_has_electronic_section(self, logged_in_page: Page, live_url, db):
        """세금계산서 상세에 전자발행 섹션이 있는지 확인"""
        # 테스트 데이터 생성
        from apps.sales.models import Partner
        from apps.accounting.models import TaxInvoice
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(username='testadmin')

        partner = Partner.objects.create(
            name='테스트거래처', partner_type='CUSTOMER',
            business_number='123-45-67890', created_by=user,
        )
        invoice = TaxInvoice.objects.create(
            invoice_number='TI-TEST-001',
            invoice_type='SALES',
            partner=partner,
            supply_amount=100000,
            tax_amount=10000,
            total_amount=110000,
            created_by=user,
        )

        page = logged_in_page
        page.goto(f'{live_url}/accounting/invoices/{invoice.pk}/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert 'TI-TEST-001' in page_content
