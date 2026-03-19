import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import Page, expect

from apps.hr.models import Department, Position, EmployeeProfile


@pytest.mark.django_db
class TestHRWorkflow:
    """인사 관리 워크플로우 E2E 테스트"""

    def test_department_list_loads(self, logged_in_page: Page, live_url):
        """부서 목록 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/hr/departments/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '부서' in page_content

    def test_create_department(self, logged_in_page: Page, live_url):
        """부서 생성 워크플로우 테스트"""
        page = logged_in_page

        # 부서 등록 페이지로 이동
        page.goto(f'{live_url}/hr/departments/create/')
        page.wait_for_load_state('networkidle')

        # 폼 필드 채우기
        page.fill('input[name="code"]', 'DEPT-E2E-001')
        page.fill('input[name="name"]', 'E2E테스트팀')

        # 저장 버튼 클릭
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')

        # 부서 목록으로 리다이렉트 확인
        assert '/hr/departments/' in page.url

        # DB에서 부서 확인
        dept = Department.objects.get(code='DEPT-E2E-001')
        assert dept.name == 'E2E테스트팀'

    def test_create_employee(self, logged_in_page: Page, live_url, admin_user):
        """직원 등록 워크플로우 테스트"""
        page = logged_in_page

        # 사전 데이터 생성
        dept = Department.objects.create(code='DEPT-EMP-001', name='테스트부서')
        pos = Position.objects.create(name='사원', level=1)

        # 새 사용자 생성 (직원 프로필 연결용)
        User = get_user_model()
        new_user = User.objects.create_user(
            username='emp_test_user',
            password='testpass123!',
            name='테스트직원',
            role='staff',
        )

        # 직원 등록 페이지로 이동
        page.goto(f'{live_url}/hr/employees/create/')
        page.wait_for_load_state('networkidle')

        # 폼 필드 채우기
        page.fill('input[name="employee_number"]', 'EMP-E2E-001')
        page.select_option('select[name="user"]', str(new_user.pk))
        page.select_option('select[name="department"]', str(dept.pk))
        page.select_option('select[name="position"]', str(pos.pk))
        page.fill('input[name="hire_date"]', '2026-01-01')
        page.select_option('select[name="contract_type"]', 'FULL_TIME')
        page.select_option('select[name="status"]', 'ACTIVE')

        # 저장 버튼 클릭
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')

        # 직원 목록으로 리다이렉트 확인
        assert '/hr/employees/' in page.url

        # DB에서 직원 확인
        emp = EmployeeProfile.objects.get(employee_number='EMP-E2E-001')
        assert emp.user == new_user
        assert emp.department == dept

    def test_org_chart_loads(self, logged_in_page: Page, live_url):
        """조직도 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/hr/org-chart/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '조직도' in page_content
