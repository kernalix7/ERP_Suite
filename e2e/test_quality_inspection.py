import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import Page

from apps.inventory.models import Product
from apps.production.models import QualityInspection


@pytest.mark.django_db
class TestQualityInspectionWorkflow:
    """품질검수 워크플로우 E2E 테스트"""

    def test_qc_list_loads(self, logged_in_page: Page, live_url):
        """품질검수 목록 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/production/qc/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '품질' in page_content or '검수' in page_content

    def test_create_quality_inspection(self, logged_in_page: Page, live_url):
        """품질검수 등록 워크플로우 테스트"""
        page = logged_in_page

        product = Product.objects.create(
            code='QC-PRD-001', name='품질검수 테스트 제품',
            product_type='FINISHED', unit='EA',
            unit_price=50000, cost_price=30000, current_stock=100,
        )

        page.goto(f'{live_url}/production/qc/create/')
        page.wait_for_load_state('networkidle')

        # 폼 필드 채우기
        page.select_option('select[name="inspection_type"]', 'INCOMING')
        page.select_option('select[name="product"]', str(product.pk))
        page.fill('input[name="inspected_quantity"]', '100')
        page.fill('input[name="pass_quantity"]', '95')
        page.fill('input[name="fail_quantity"]', '5')
        page.fill('input[name="inspection_date"]', '2026-03-23')
        page.select_option('select[name="result"]', 'PASS')

        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')

        # 목록 페이지로 리다이렉트 확인
        assert '/production/qc/' in page.url

        # DB에서 품질검수 확인
        qc = QualityInspection.objects.first()
        assert qc is not None
        assert qc.inspected_quantity == 100
        assert qc.pass_quantity == 95
        assert qc.fail_quantity == 5

    def test_qc_detail_shows_pass_rate(self, logged_in_page: Page, live_url):
        """품질검수 상세 페이지에서 합격률 표시 확인"""
        page = logged_in_page

        product = Product.objects.create(
            code='QC-PRD-002', name='합격률 테스트 제품',
            product_type='FINISHED', unit='EA',
            unit_price=10000, cost_price=5000, current_stock=0,
        )
        User = get_user_model()
        admin = User.objects.get(username='testadmin')
        qc = QualityInspection.objects.create(
            inspection_type='PRODUCTION',
            product=product,
            inspected_quantity=200,
            pass_quantity=180,
            fail_quantity=20,
            inspection_date='2026-03-23',
            result='PASS',
            created_by=admin,
        )

        page.goto(f'{live_url}/production/qc/{qc.pk}/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        # 합격률 90% 표시 확인
        assert '90' in page_content
