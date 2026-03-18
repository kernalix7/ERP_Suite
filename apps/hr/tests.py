from datetime import date

from django.db import IntegrityError
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.hr.models import (
    Department, Position, EmployeeProfile, PersonnelAction,
)

User = get_user_model()


class DepartmentModelTest(TestCase):
    """부서 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='hruser', password='testpass123', role='manager',
        )
        self.dept = Department.objects.create(
            name='개발팀', code='DEV', created_by=self.user,
        )

    def test_department_creation(self):
        """부서 생성"""
        self.assertEqual(self.dept.name, '개발팀')
        self.assertEqual(self.dept.code, 'DEV')

    def test_department_str(self):
        """부서 문자열 표현"""
        self.assertEqual(str(self.dept), '개발팀 (DEV)')

    def test_department_unique_code(self):
        """부서코드 중복 불가"""
        with self.assertRaises(IntegrityError):
            Department.objects.create(
                name='다른개발팀', code='DEV', created_by=self.user,
            )

    def test_department_hierarchy(self):
        """부서 상하위 관계"""
        child = Department.objects.create(
            name='프론트엔드', code='DEV-FE',
            parent=self.dept, created_by=self.user,
        )
        self.assertEqual(child.parent, self.dept)
        self.assertIn(child, self.dept.children.all())

    def test_get_ancestors(self):
        """상위 부서 목록 반환"""
        child = Department.objects.create(
            name='프론트엔드', code='DEV-FE',
            parent=self.dept, created_by=self.user,
        )
        grandchild = Department.objects.create(
            name='리액트팀', code='DEV-FE-R',
            parent=child, created_by=self.user,
        )
        ancestors = grandchild.get_ancestors()
        self.assertEqual(len(ancestors), 2)
        self.assertEqual(ancestors[0], self.dept)
        self.assertEqual(ancestors[1], child)

    def test_get_descendants(self):
        """하위 부서 목록 반환"""
        child = Department.objects.create(
            name='백엔드', code='DEV-BE',
            parent=self.dept, created_by=self.user,
        )
        grandchild = Department.objects.create(
            name='API팀', code='DEV-BE-API',
            parent=child, created_by=self.user,
        )
        descendants = self.dept.get_descendants()
        self.assertEqual(len(descendants), 2)
        self.assertIn(child, descendants)
        self.assertIn(grandchild, descendants)

    def test_root_department_no_ancestors(self):
        """최상위 부서는 ancestors 없음"""
        ancestors = self.dept.get_ancestors()
        self.assertEqual(len(ancestors), 0)

    def test_department_manager(self):
        """부서장 설정"""
        self.dept.manager = self.user
        self.dept.save()
        self.dept.refresh_from_db()
        self.assertEqual(self.dept.manager, self.user)

    def test_department_soft_delete(self):
        """부서 soft delete"""
        self.dept.soft_delete()
        qs = Department.objects.filter(pk=self.dept.pk)
        self.assertFalse(qs.exists())
        qs_all = Department.all_objects.filter(pk=self.dept.pk)
        self.assertTrue(qs_all.exists())


class PositionModelTest(TestCase):
    """직급 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='posuser', password='testpass123', role='manager',
        )

    def test_position_creation(self):
        """직급 생성"""
        pos = Position.objects.create(
            name='사원', level=1, created_by=self.user,
        )
        self.assertEqual(pos.name, '사원')
        self.assertEqual(pos.level, 1)

    def test_position_str(self):
        """직급 문자열 표현"""
        pos = Position.objects.create(
            name='과장', level=3, created_by=self.user,
        )
        self.assertEqual(str(pos), '과장')

    def test_position_ordering(self):
        """직급은 레벨순 정렬"""
        Position.objects.create(name='부장', level=5, created_by=self.user)
        Position.objects.create(name='사원', level=1, created_by=self.user)
        Position.objects.create(name='대리', level=2, created_by=self.user)
        positions = list(Position.objects.all())
        self.assertEqual(positions[0].name, '사원')
        self.assertEqual(positions[1].name, '대리')
        self.assertEqual(positions[2].name, '부장')


class EmployeeProfileModelTest(TestCase):
    """직원 프로필 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='empuser', password='testpass123',
            role='staff', name='김직원',
        )
        self.dept = Department.objects.create(
            name='인사팀', code='HR',
        )
        self.position = Position.objects.create(
            name='대리', level=2,
        )
        self.profile = EmployeeProfile.objects.create(
            user=self.user,
            employee_number='EMP-001',
            department=self.dept,
            position=self.position,
            hire_date=date(2023, 1, 1),
        )

    def test_profile_creation(self):
        """직원 프로필 생성"""
        self.assertEqual(self.profile.employee_number, 'EMP-001')
        self.assertEqual(self.profile.department, self.dept)
        self.assertEqual(self.profile.position, self.position)

    def test_profile_str(self):
        """직원 프로필 문자열 표현"""
        self.assertEqual(str(self.profile), '김직원 (EMP-001)')

    def test_unique_employee_number(self):
        """사번 중복 불가"""
        other_user = User.objects.create_user(
            username='other', password='testpass123',
        )
        with self.assertRaises(IntegrityError):
            EmployeeProfile.objects.create(
                user=other_user,
                employee_number='EMP-001',
                hire_date=date.today(),
            )

    def test_years_of_service(self):
        """근속연수 계산"""
        yos = self.profile.years_of_service
        self.assertIsInstance(yos, float)
        self.assertGreater(yos, 0)

    def test_years_of_service_with_resignation(self):
        """퇴사자 근속연수 계산"""
        self.profile.resignation_date = date(2024, 1, 1)
        self.profile.save()
        # 2023-01-01 ~ 2024-01-01 = 약 1년
        yos = self.profile.years_of_service
        self.assertAlmostEqual(yos, 1.0, delta=0.1)

    def test_contract_type_choices(self):
        """계약유형 선택지"""
        choices = dict(EmployeeProfile.ContractType.choices)
        self.assertIn('FULL_TIME', choices)
        self.assertIn('CONTRACT', choices)
        self.assertIn('INTERN', choices)

    def test_status_choices(self):
        """상태 선택지"""
        choices = dict(EmployeeProfile.Status.choices)
        self.assertIn('ACTIVE', choices)
        self.assertIn('ON_LEAVE', choices)
        self.assertIn('RESIGNED', choices)

    def test_default_contract_type(self):
        """기본 계약유형은 정규직"""
        self.assertEqual(
            self.profile.contract_type,
            EmployeeProfile.ContractType.FULL_TIME,
        )

    def test_one_to_one_relationship(self):
        """User와 1:1 관계"""
        self.assertEqual(self.user.profile, self.profile)


class PersonnelActionModelTest(TestCase):
    """인사발령 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='actionuser', password='testpass123',
            role='staff', name='이발령',
        )
        self.dept1 = Department.objects.create(name='영업팀', code='SALES')
        self.dept2 = Department.objects.create(name='마케팅팀', code='MKT')
        self.pos1 = Position.objects.create(name='사원', level=1)
        self.pos2 = Position.objects.create(name='대리', level=2)
        self.profile = EmployeeProfile.objects.create(
            user=self.user,
            employee_number='PA-001',
            department=self.dept1,
            position=self.pos1,
            hire_date=date.today(),
        )

    def test_personnel_action_creation(self):
        """인사발령 생성"""
        action = PersonnelAction.objects.create(
            employee=self.profile,
            action_type=PersonnelAction.ActionType.TRANSFER,
            effective_date=date.today(),
            from_department=self.dept1,
            to_department=self.dept2,
            reason='조직 개편',
        )
        self.assertEqual(action.action_type, 'TRANSFER')
        self.assertEqual(action.from_department, self.dept1)
        self.assertEqual(action.to_department, self.dept2)

    def test_personnel_action_str(self):
        """인사발령 문자열 표현"""
        action = PersonnelAction.objects.create(
            employee=self.profile,
            action_type=PersonnelAction.ActionType.PROMOTION,
            effective_date=date(2026, 3, 1),
            from_position=self.pos1,
            to_position=self.pos2,
        )
        expected = '이발령 (PA-001) - 승진 (2026-03-01)'
        self.assertEqual(str(action), expected)

    def test_action_type_choices(self):
        """발령유형 선택지"""
        choices = dict(PersonnelAction.ActionType.choices)
        self.assertIn('HIRE', choices)
        self.assertIn('PROMOTION', choices)
        self.assertIn('TRANSFER', choices)
        self.assertIn('RESIGNATION', choices)

    def test_ordering(self):
        """인사발령은 최신 발령일순"""
        a1 = PersonnelAction.objects.create(
            employee=self.profile,
            action_type=PersonnelAction.ActionType.HIRE,
            effective_date=date(2026, 1, 1),
        )
        a2 = PersonnelAction.objects.create(
            employee=self.profile,
            action_type=PersonnelAction.ActionType.PROMOTION,
            effective_date=date(2026, 6, 1),
        )
        actions = list(PersonnelAction.objects.all())
        self.assertEqual(actions[0], a2)
        self.assertEqual(actions[1], a1)


class HRViewAccessTest(TestCase):
    """HR 뷰 접근 제어 테스트"""

    def setUp(self):
        self.client = Client()
        self.manager = User.objects.create_user(
            username='hr_manager', password='testpass123', role='manager',
        )
        self.staff = User.objects.create_user(
            username='hr_staff', password='testpass123', role='staff',
        )

    def test_org_chart_requires_login(self):
        """조직도 비로그인 접근 불가"""
        response = self.client.get(reverse('hr:org_chart'))
        self.assertEqual(response.status_code, 302)

    def test_org_chart_accessible_when_logged_in(self):
        """조직도 매니저 로그인 후 접근 가능"""
        self.client.force_login(
            User.objects.get(username='hr_manager'))
        response = self.client.get(reverse('hr:org_chart'))
        self.assertEqual(response.status_code, 200)

    def test_department_list_accessible(self):
        """부서 목록 매니저 접근 가능"""
        self.client.force_login(
            User.objects.get(username='hr_manager'))
        response = self.client.get(reverse('hr:department_list'))
        self.assertEqual(response.status_code, 200)
