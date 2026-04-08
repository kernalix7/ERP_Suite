import pytest
from playwright.sync_api import Page, expect


@pytest.mark.django_db
class TestAssetManagement:
    """자산 관리 E2E 테스트"""

    def test_asset_list_loads(self, logged_in_page: Page, live_url):
        """자산 목록 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/asset/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '고정자산' in page_content or '자산' in page_content

    def test_asset_create_page_loads(self, logged_in_page: Page, live_url):
        """자산 등록 페이지가 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/asset/create/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '자산' in page_content
        # 필수 폼 필드 확인
        expect(page.locator('input[name="asset_number"]')).to_be_visible()
        expect(page.locator('input[name="name"]')).to_be_visible()

    def test_asset_summary_page(self, logged_in_page: Page, live_url):
        """자산 요약 페이지 접근 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/asset/summary/')
        page.wait_for_load_state('networkidle')

        assert page.url.endswith('/asset/summary/') or page.url.endswith('/asset/summary')


@pytest.mark.django_db
class TestCertificationCRUD:
    """인증 관리 E2E 테스트"""

    def test_certification_list_loads(self, logged_in_page: Page, live_url):
        """인증 목록 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/asset/certifications/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '인증' in page_content

    def test_certification_create_page_loads(self, logged_in_page: Page, live_url):
        """인증 등록 페이지가 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/asset/certifications/create/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '인증' in page_content
        expect(page.locator('input[name="cert_name"]')).to_be_visible()

    def test_certification_create_submit(self, logged_in_page: Page, live_url, db):
        """인증 등록 폼 제출 테스트"""
        from apps.asset.models import AssetCategory, FixedAsset
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(username='testadmin')

        category = AssetCategory.objects.create(
            name='테스트분류', code='TC01', created_by=user,
        )
        asset = FixedAsset.objects.create(
            asset_number='FA-TEST-001', name='테스트자산',
            category=category, acquisition_date='2025-01-01',
            acquisition_cost=1000000, useful_life_years=5,
            created_by=user,
        )

        page = logged_in_page
        page.goto(f'{live_url}/asset/certifications/create/')
        page.wait_for_load_state('networkidle')

        page.fill('input[name="cert_name"]', 'KC인증 테스트')
        page.select_option('select[name="cert_type"]', 'KC')
        page.fill('input[name="issue_date"]', '2025-01-15')
        page.fill('input[name="expiry_date"]', '2027-01-15')

        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')

        # 등록 후 리다이렉트 확인
        assert '/asset/certifications/' in page.url


@pytest.mark.django_db
class TestLeaseContract:
    """리스 계약 E2E 테스트"""

    def test_lease_list_loads(self, logged_in_page: Page, live_url):
        """리스 계약 목록 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/asset/leases/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '리스' in page_content

    def test_lease_create_page_loads(self, logged_in_page: Page, live_url):
        """리스 계약 등록 페이지가 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/asset/leases/create/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '리스' in page_content

    def test_lease_detail_page(self, logged_in_page: Page, live_url, db):
        """리스 계약 상세 페이지 확인"""
        from apps.asset.models import AssetCategory, FixedAsset, LeaseContract
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(username='testadmin')

        category = AssetCategory.objects.create(
            name='리스분류', code='LC01', created_by=user,
        )
        asset = FixedAsset.objects.create(
            asset_number='FA-LEASE-001', name='리스자산',
            category=category, acquisition_date='2025-01-01',
            acquisition_cost=5000000, useful_life_years=5,
            created_by=user,
        )
        lease = LeaseContract.objects.create(
            asset=asset, lease_type='OPERATING',
            start_date='2025-01-01', end_date='2027-12-31',
            monthly_payment=500000, created_by=user,
        )

        page = logged_in_page
        page.goto(f'{live_url}/asset/leases/{lease.pk}/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '리스' in page_content


@pytest.mark.django_db
class TestAssetAudit:
    """자산 실사 E2E 테스트"""

    def test_audit_list_loads(self, logged_in_page: Page, live_url):
        """자산 실사 목록 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/asset/audits/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '실사' in page_content

    def test_audit_create_page_loads(self, logged_in_page: Page, live_url):
        """자산 실사 등록 페이지가 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/asset/audits/create/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '실사' in page_content


@pytest.mark.django_db
class TestAssetTransfer:
    """자산 이관 E2E 테스트"""

    def test_transfer_from_asset_detail(self, logged_in_page: Page, live_url, db):
        """자산 상세에서 이관 페이지로 이동 확인"""
        from apps.asset.models import AssetCategory, FixedAsset
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(username='testadmin')

        category = AssetCategory.objects.create(
            name='이관분류', code='TF01', created_by=user,
        )
        asset = FixedAsset.objects.create(
            asset_number='FA-TF-001', name='이관테스트자산',
            category=category, acquisition_date='2025-01-01',
            acquisition_cost=2000000, useful_life_years=5,
            created_by=user,
        )

        page = logged_in_page
        page.goto(f'{live_url}/asset/{asset.asset_number}/transfer/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '이관' in page_content


@pytest.mark.django_db
class TestAssetRegisterReport:
    """자산 대장 리포트 E2E 테스트"""

    def test_register_report_loads(self, logged_in_page: Page, live_url):
        """자산대장 리포트 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/asset/report/register/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '자산' in page_content
