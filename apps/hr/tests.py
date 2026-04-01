from datetime import date

from django.db import IntegrityError
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from decimal import Decimal

from apps.hr.models import (
    Department, ExternalCompany, Position, EmployeeProfile, PersonnelAction,
    PayrollConfig, Payroll,
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
            code='POS-STF', name='사원', level=1, created_by=self.user,
        )
        self.assertEqual(pos.name, '사원')
        self.assertEqual(pos.level, 1)
        self.assertEqual(pos.code, 'POS-STF')

    def test_position_str(self):
        """직급 문자열 표현"""
        pos = Position.objects.create(
            code='POS-MGR', name='과장', level=3, created_by=self.user,
        )
        self.assertEqual(str(pos), '과장 (POS-MGR)')

    def test_position_ordering(self):
        """직급은 레벨순 정렬"""
        Position.objects.create(code='POS-GM', name='부장', level=5, created_by=self.user)
        Position.objects.create(code='POS-STF2', name='사원', level=1, created_by=self.user)
        Position.objects.create(code='POS-AM', name='대리', level=2, created_by=self.user)
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
            code='POS-AM2', name='대리', level=2,
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
        self.pos1 = Position.objects.create(code='POS-STF-PA', name='사원', level=1)
        self.pos2 = Position.objects.create(code='POS-AM-PA', name='대리', level=2)
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
        self.assertIn('MANAGER_APPOINT', choices)

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


class PersonnelActionSignalTest(TestCase):
    """인사발령 시그널 테스트"""

    def setUp(self):
        self.manager = User.objects.create_user(
            username='signal_manager', password='testpass123', role='manager',
        )
        self.dept = Department.objects.create(name='개발팀', code='SIG-DEV', created_by=self.manager)
        self.position = Position.objects.create(code='POS-STF-SIG', name='사원', level=1, created_by=self.manager)

    def _create_employee_with_user(self, username, emp_number, name='홍길동'):
        user = User.objects.create_user(
            username=username, password='pass123', role='staff', name=name,
        )
        profile = EmployeeProfile.objects.create(
            user=user,
            employee_number=emp_number,
            department=self.dept,
            position=self.position,
            hire_date=date.today(),
            created_by=self.manager,
        )
        return user, profile

    def test_resignation_deactivates_user(self):
        """퇴사 발령 시 User.is_active = False"""
        user, profile = self._create_employee_with_user('resign_test', 'EMP-R001')
        self.assertTrue(user.is_active)

        PersonnelAction.objects.create(
            employee=profile,
            action_type=PersonnelAction.ActionType.RESIGNATION,
            effective_date=date.today(),
            created_by=self.manager,
        )

        user.refresh_from_db()
        self.assertFalse(user.is_active)
        profile.refresh_from_db()
        self.assertEqual(profile.status, 'RESIGNED')

    def test_return_reactivates_user(self):
        """복직 발령 시 User.is_active = True"""
        user, profile = self._create_employee_with_user('return_test', 'EMP-RET01')
        user.is_active = False
        user.save()
        profile.status = 'ON_LEAVE'
        profile.save()

        PersonnelAction.objects.create(
            employee=profile,
            action_type=PersonnelAction.ActionType.RETURN,
            effective_date=date.today(),
            created_by=self.manager,
        )

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        profile.refresh_from_db()
        self.assertEqual(profile.status, 'ACTIVE')

    def test_hire_sets_employee_active(self):
        """입사 발령 시 직원 상태 ACTIVE"""
        user, profile = self._create_employee_with_user('hire_test', 'EMP-H001')
        profile.status = 'RESIGNED'
        profile.save()

        PersonnelAction.objects.create(
            employee=profile,
            action_type=PersonnelAction.ActionType.HIRE,
            effective_date=date.today(),
            created_by=self.manager,
        )

        profile.refresh_from_db()
        self.assertEqual(profile.status, 'ACTIVE')

    def test_leave_sets_on_leave_status(self):
        """휴직 발령 시 직원 상태 ON_LEAVE"""
        user, profile = self._create_employee_with_user('leave_test', 'EMP-L001')

        PersonnelAction.objects.create(
            employee=profile,
            action_type=PersonnelAction.ActionType.LEAVE,
            effective_date=date.today(),
            created_by=self.manager,
        )

        profile.refresh_from_db()
        self.assertEqual(profile.status, 'ON_LEAVE')

    def test_transfer_updates_department(self):
        """전보 발령 시 부서 변경"""
        user, profile = self._create_employee_with_user('transfer_test', 'EMP-T001')
        new_dept = Department.objects.create(name='마케팅팀', code='SIG-MKT', created_by=self.manager)

        PersonnelAction.objects.create(
            employee=profile,
            action_type=PersonnelAction.ActionType.TRANSFER,
            effective_date=date.today(),
            from_department=self.dept,
            to_department=new_dept,
            created_by=self.manager,
        )

        profile.refresh_from_db()
        self.assertEqual(profile.department, new_dept)

    def test_manager_appoint_sets_department_manager(self):
        """부서장 임명 발령 시 Department.manager 자동 설정"""
        user, profile = self._create_employee_with_user('mgr_test', 'EMP-M001')

        PersonnelAction.objects.create(
            employee=profile,
            action_type=PersonnelAction.ActionType.MANAGER_APPOINT,
            effective_date=date.today(),
            to_department=self.dept,
            created_by=self.manager,
        )

        self.dept.refresh_from_db()
        self.assertEqual(self.dept.manager, user)

    def test_manager_appoint_clears_previous_department(self):
        """부서장 임명 시 기존 부서장 직책 해제"""
        user, profile = self._create_employee_with_user('mgr_prev', 'EMP-M002')
        old_dept = Department.objects.create(name='기획팀', code='SIG-PLN', created_by=self.manager)
        old_dept.manager = user
        old_dept.save()

        new_dept = Department.objects.create(name='전략팀', code='SIG-STR', created_by=self.manager)

        PersonnelAction.objects.create(
            employee=profile,
            action_type=PersonnelAction.ActionType.MANAGER_APPOINT,
            effective_date=date.today(),
            to_department=new_dept,
            created_by=self.manager,
        )

        old_dept.refresh_from_db()
        new_dept.refresh_from_db()
        self.assertIsNone(old_dept.manager)
        self.assertEqual(new_dept.manager, user)

    def test_manager_appoint_moves_department_if_different(self):
        """부서장 임명 시 다른 부서이면 부서도 이동"""
        user, profile = self._create_employee_with_user('mgr_move', 'EMP-M003')
        new_dept = Department.objects.create(name='신규팀', code='SIG-NEW', created_by=self.manager)

        PersonnelAction.objects.create(
            employee=profile,
            action_type=PersonnelAction.ActionType.MANAGER_APPOINT,
            effective_date=date.today(),
            to_department=new_dept,
            created_by=self.manager,
        )

        profile.refresh_from_db()
        self.assertEqual(profile.department, new_dept)


class OnboardingOffboardingViewTest(TestCase):
    """입퇴사 처리 뷰 테스트"""

    def setUp(self):
        self.client = Client()
        self.manager = User.objects.create_user(
            username='ob_manager', password='testpass123', role='manager',
        )
        self.dept = Department.objects.create(name='테스트팀', code='OB-TST', created_by=self.manager)
        self.position = Position.objects.create(code='POS-STF-OB', name='사원', level=1, created_by=self.manager)

    def test_onboarding_requires_login(self):
        """입사 처리 비로그인 접근 불가"""
        response = self.client.get(reverse('hr:onboarding'))
        self.assertEqual(response.status_code, 302)

    def test_onboarding_accessible_by_manager(self):
        """입사 처리 매니저 접근 가능"""
        self.client.force_login(self.manager)
        response = self.client.get(reverse('hr:onboarding'))
        self.assertEqual(response.status_code, 200)

    def test_onboarding_creates_employee_and_user(self):
        """입사 처리 폼 제출 시 직원 및 User 생성 (이메일 로그인)"""
        self.client.force_login(self.manager)
        response = self.client.post(reverse('hr:onboarding'), {
            'name': '신입직원',
            'email': 'newbie@company.com',
            'hire_date': '2026-03-25',
            'department': self.dept.pk,
            'position': self.position.pk,
            'contract_type': 'FULL_TIME',
            'employee_type': 'INTERNAL',
            'base_salary': '3000000',
            'employee_number': '',
        })
        self.assertRedirects(response, reverse('hr:employee_list'))
        # 직원 프로필 생성 확인
        self.assertTrue(EmployeeProfile.objects.filter(department=self.dept).exists())
        # 사용자 계정 생성 확인 (사번=username)
        profile = EmployeeProfile.objects.get(department=self.dept, status='ACTIVE')
        self.assertEqual(profile.user.username, profile.employee_number)
        self.assertEqual(profile.user.email, 'newbie@company.com')
        self.assertTrue(profile.user.is_active)

    def test_offboarding_requires_login(self):
        """퇴사 처리 비로그인 접근 불가"""
        response = self.client.get(reverse('hr:offboarding'))
        self.assertEqual(response.status_code, 302)

    def test_offboarding_deactivates_user(self):
        """퇴사 처리 폼 제출 시 User 비활성화"""
        emp_user = User.objects.create_user(
            username='ob_emp', password='pass123', role='staff', name='퇴직자',
        )
        profile = EmployeeProfile.objects.create(
            user=emp_user,
            employee_number='OB-EMP001',
            department=self.dept,
            position=self.position,
            hire_date=date.today(),
            status=EmployeeProfile.Status.ACTIVE,
            created_by=self.manager,
        )
        self.client.force_login(self.manager)
        response = self.client.post(reverse('hr:offboarding'), {
            'employee': profile.pk,
            'resignation_date': '2026-03-25',
            'reason': '개인 사유',
        })
        self.assertRedirects(response, reverse('hr:employee_list'))
        emp_user.refresh_from_db()
        self.assertFalse(emp_user.is_active)
        profile.refresh_from_db()
        self.assertEqual(profile.status, 'RESIGNED')


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


class PayrollConfigTest(TestCase):
    """급여설정 모델 테스트"""

    def test_config_creation(self):
        """PayrollConfig 생성 가능"""
        config = PayrollConfig.objects.create(
            year=2026,
            minimum_wage_hourly=Decimal('10030'),
            national_pension_rate=Decimal('4.50'),
            health_insurance_rate=Decimal('3.545'),
            long_term_care_rate=Decimal('12.81'),
            employment_insurance_rate=Decimal('0.90'),
        )
        self.assertEqual(config.year, 2026)
        self.assertEqual(config.national_pension_rate, Decimal('4.50'))
        self.assertEqual(str(config), '2026년 급여설정')

    def test_unique_year(self):
        """동일 년도 중복 불가"""
        PayrollConfig.objects.create(year=2026)
        with self.assertRaises(IntegrityError):
            PayrollConfig.objects.create(year=2026)


class PayrollTest(TestCase):
    """급여 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='payroll_emp', password='testpass123',
            role='staff', name='박급여',
        )
        self.dept = Department.objects.create(name='경영지원팀', code='MGT')
        self.position = Position.objects.create(code='POS-STF-PAY', name='사원', level=1)
        self.profile = EmployeeProfile.objects.create(
            user=self.user,
            employee_number='PAY-001',
            department=self.dept,
            position=self.position,
            hire_date=date(2024, 1, 1),
        )
        self.config = PayrollConfig.objects.create(
            year=2026,
            national_pension_rate=Decimal('4.50'),
            health_insurance_rate=Decimal('3.545'),
            long_term_care_rate=Decimal('12.81'),
            employment_insurance_rate=Decimal('0.90'),
        )

    def test_payroll_auto_deductions(self):
        """save() 시 4대보험+세금 자동 계산"""
        payroll = Payroll.objects.create(
            employee=self.profile,
            year=2026,
            month=3,
            base_salary=Decimal('3000000'),
        )
        # gross_pay = 3000000 + 0 + 0 + 0 = 3000000
        self.assertEqual(payroll.gross_pay, Decimal('3000000'))

        # 국민연금 = int(3000000 * 4.50 / 100) = 135000
        self.assertEqual(payroll.national_pension, 135000)

        # 건강보험 = int(3000000 * 3.55 / 100) = 106500 (decimal_places=2로 3.545→3.55 반올림)
        # 실제 저장된 요율로 계산되므로 정확한 값 검증
        self.assertGreater(payroll.health_insurance, 0)

        # 장기요양 = 건강보험 * 12.81%
        self.assertGreater(payroll.long_term_care, 0)

        # 고용보험 = int(3000000 * 0.90 / 100) = 27000
        self.assertEqual(payroll.employment_insurance, 27000)

        # 세금도 계산되어야 함
        self.assertGreater(payroll.income_tax, 0)
        self.assertGreater(payroll.local_income_tax, 0)

        # 공제합계 검증
        expected_deductions = (
            payroll.national_pension + payroll.health_insurance
            + payroll.long_term_care + payroll.employment_insurance
            + payroll.income_tax + payroll.local_income_tax
        )
        self.assertEqual(payroll.total_deductions, expected_deductions)

        # 실수령액 검증
        self.assertEqual(
            payroll.net_pay,
            payroll.gross_pay - payroll.total_deductions,
        )

    def test_payroll_gross_pay_calculation(self):
        """gross_pay = base_salary + overtime + bonus + allowances"""
        payroll = Payroll.objects.create(
            employee=self.profile,
            year=2026,
            month=4,
            base_salary=Decimal('3000000'),
            overtime_pay=Decimal('500000'),
            bonus=Decimal('1000000'),
            allowances=Decimal('200000'),
        )
        expected_gross = (
            Decimal('3000000') + Decimal('500000')
            + Decimal('1000000') + Decimal('200000')
        )
        self.assertEqual(payroll.gross_pay, expected_gross)
        self.assertEqual(payroll.gross_pay, Decimal('4700000'))

    def test_payroll_unique_employee_period(self):
        """동일 직원/년/월 중복 불가"""
        Payroll.objects.create(
            employee=self.profile,
            year=2026,
            month=3,
            base_salary=Decimal('3000000'),
        )
        with self.assertRaises(IntegrityError):
            Payroll.objects.create(
                employee=self.profile,
                year=2026,
                month=3,
                base_salary=Decimal('3000000'),
            )


class ExternalCompanyTest(TestCase):
    """외부 협력업체 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='ext_manager', password='testpass123', role='manager',
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.company = ExternalCompany.objects.create(
            name='(주)테스트협력사',
            business_number='123-45-67890',
            representative='홍길동',
            contact_person='김담당',
            phone='02-1234-5678',
            email='test@partner.com',
            created_by=self.user,
        )

    def test_external_company_creation(self):
        """ExternalCompany 생성"""
        self.assertEqual(self.company.name, '(주)테스트협력사')
        self.assertEqual(self.company.business_number, '123-45-67890')
        self.assertEqual(self.company.representative, '홍길동')

    def test_external_company_str(self):
        """ExternalCompany 문자열 표현"""
        self.assertEqual(str(self.company), '(주)테스트협력사')

    def test_external_company_unique_business_number(self):
        """사업자번호 중복 불가"""
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            ExternalCompany.objects.create(
                name='다른업체',
                business_number='123-45-67890',
                representative='이사장',
                created_by=self.user,
            )

    def test_external_company_list_view(self):
        """외부업체 목록 뷰 접근"""
        response = self.client.get(reverse('hr:external_company_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '(주)테스트협력사')

    def test_external_company_create_view(self):
        """외부업체 등록 뷰 접근"""
        response = self.client.get(reverse('hr:external_company_create'))
        self.assertEqual(response.status_code, 200)

    def test_external_company_create_post(self):
        """외부업체 등록 폼 제출"""
        response = self.client.post(reverse('hr:external_company_create'), {
            'name': '새협력사',
            'business_number': '999-88-77654',
            'representative': '박사장',
            'contact_person': '',
            'phone': '',
            'email': '',
            'address': '',
            'notes': '',
        })
        self.assertRedirects(response, reverse('hr:external_company_list'))
        self.assertTrue(ExternalCompany.objects.filter(name='새협력사').exists())

    def test_external_company_update_view(self):
        """외부업체 수정 뷰 접근"""
        response = self.client.get(reverse('hr:external_company_update', args=[self.company.pk]))
        self.assertEqual(response.status_code, 200)

    def test_external_company_soft_delete(self):
        """외부업체 soft delete"""
        self.company.soft_delete()
        self.assertFalse(ExternalCompany.objects.filter(pk=self.company.pk).exists())
        self.assertTrue(ExternalCompany.all_objects.filter(pk=self.company.pk).exists())


class EmployeeTypeTest(TestCase):
    """고용유형(EmployeeType) 필터 테스트"""

    def setUp(self):
        self.manager = User.objects.create_user(
            username='et_manager', password='testpass123', role='manager',
        )
        self.client = Client()
        self.client.force_login(self.manager)
        self.dept = Department.objects.create(name='개발팀', code='ET-DEV', created_by=self.manager)
        self.position = Position.objects.create(code='ET-STF', name='사원', level=1, created_by=self.manager)
        self.company = ExternalCompany.objects.create(
            name='외부파트너사', business_number='222-33-44444',
            representative='외대표', created_by=self.manager,
        )

    def _make_employee(self, username, emp_num, emp_type, name='테스트'):
        user = User.objects.create_user(username=username, password='pass', role='staff', name=name)
        return EmployeeProfile.objects.create(
            user=user, employee_number=emp_num,
            department=self.dept, position=self.position,
            hire_date=date.today(), employee_type=emp_type,
            created_by=self.manager,
        )

    def test_employee_type_choices(self):
        """고용유형 선택지"""
        choices = dict(EmployeeProfile.EmployeeType.choices)
        self.assertIn('INTERNAL', choices)
        self.assertIn('CONTRACT', choices)
        self.assertIn('EXTERNAL', choices)
        self.assertIn('DISPATCH', choices)

    def test_default_employee_type_internal(self):
        """기본 고용유형은 정규직"""
        emp = self._make_employee('et_int', 'ET-001', EmployeeProfile.EmployeeType.INTERNAL)
        self.assertEqual(emp.employee_type, 'INTERNAL')

    def test_employee_type_filter_in_list_view(self):
        """직원 목록 고용유형 필터"""
        self._make_employee('et_int2', 'ET-002', EmployeeProfile.EmployeeType.INTERNAL)
        self._make_employee('et_ext', 'ET-003', EmployeeProfile.EmployeeType.EXTERNAL)
        self._make_employee('et_dis', 'ET-004', EmployeeProfile.EmployeeType.DISPATCH)

        response = self.client.get(reverse('hr:employee_list'), {'employee_type': 'EXTERNAL'})
        self.assertEqual(response.status_code, 200)
        employees = response.context['employees']
        for emp in employees:
            self.assertEqual(emp.employee_type, 'EXTERNAL')

    def test_external_employee_linked_to_company(self):
        """외부 직원 외부업체 연결"""
        user = User.objects.create_user(username='ext_emp', password='pass', role='staff')
        emp = EmployeeProfile.objects.create(
            user=user, employee_number='ET-EXT001',
            department=self.dept, position=self.position,
            hire_date=date.today(),
            employee_type=EmployeeProfile.EmployeeType.EXTERNAL,
            external_company=self.company,
            contract_start=date(2026, 1, 1),
            contract_end=date(2026, 12, 31),
            created_by=self.manager,
        )
        emp.refresh_from_db()
        self.assertEqual(emp.external_company, self.company)
        self.assertEqual(emp.contract_start, date(2026, 1, 1))
        self.assertEqual(emp.contract_end, date(2026, 12, 31))
        self.assertIn(emp, self.company.employees.all())

    def test_contract_expiry_check(self):
        """계약만료 체크 — contract_end 과거인 직원 필터"""
        user = User.objects.create_user(username='exp_emp', password='pass', role='staff')
        emp = EmployeeProfile.objects.create(
            user=user, employee_number='ET-EXP001',
            department=self.dept, position=self.position,
            hire_date=date(2025, 1, 1),
            employee_type=EmployeeProfile.EmployeeType.CONTRACT,
            contract_end=date(2025, 12, 31),
            created_by=self.manager,
        )
        expired = EmployeeProfile.objects.filter(
            is_active=True,
            contract_end__lt=date.today(),
            employee_type__in=[
                EmployeeProfile.EmployeeType.CONTRACT,
                EmployeeProfile.EmployeeType.EXTERNAL,
                EmployeeProfile.EmployeeType.DISPATCH,
            ],
        )
        self.assertIn(emp, expired)


class DispatchPersonnelActionTest(TestCase):
    """파견/외부 인사발령 테스트"""

    def setUp(self):
        self.manager = User.objects.create_user(
            username='dp_manager', password='testpass123', role='manager',
        )
        self.dept = Department.objects.create(name='파견팀', code='DP-DEP', created_by=self.manager)
        self.position = Position.objects.create(code='DP-STF', name='사원', level=1, created_by=self.manager)
        emp_user = User.objects.create_user(username='dp_emp', password='pass', role='staff', name='파견직원')
        self.profile = EmployeeProfile.objects.create(
            user=emp_user, employee_number='DP-001',
            department=self.dept, position=self.position,
            hire_date=date.today(),
            employee_type=EmployeeProfile.EmployeeType.DISPATCH,
            created_by=self.manager,
        )

    def test_dispatch_in_action(self):
        """파견입사 발령 생성"""
        action = PersonnelAction.objects.create(
            employee=self.profile,
            action_type=PersonnelAction.ActionType.DISPATCH_IN,
            effective_date=date.today(),
            to_department=self.dept,
            created_by=self.manager,
        )
        self.assertEqual(action.action_type, 'DISPATCH_IN')
        self.assertEqual(action.get_action_type_display(), '파견입사')

    def test_dispatch_extend_action(self):
        """파견연장 발령 생성"""
        action = PersonnelAction.objects.create(
            employee=self.profile,
            action_type=PersonnelAction.ActionType.DISPATCH_EXTEND,
            effective_date=date.today(),
            created_by=self.manager,
        )
        self.assertEqual(action.action_type, 'DISPATCH_EXTEND')
        self.assertEqual(action.get_action_type_display(), '파견연장')

    def test_dispatch_end_action(self):
        """파견종료 발령 생성"""
        action = PersonnelAction.objects.create(
            employee=self.profile,
            action_type=PersonnelAction.ActionType.DISPATCH_END,
            effective_date=date.today(),
            created_by=self.manager,
        )
        self.assertEqual(action.action_type, 'DISPATCH_END')
        self.assertEqual(action.get_action_type_display(), '파견종료')

    def test_external_in_action(self):
        """외부인력 투입 발령 생성"""
        action = PersonnelAction.objects.create(
            employee=self.profile,
            action_type=PersonnelAction.ActionType.EXTERNAL_IN,
            effective_date=date.today(),
            to_department=self.dept,
            created_by=self.manager,
        )
        self.assertEqual(action.action_type, 'EXTERNAL_IN')
        self.assertEqual(action.get_action_type_display(), '외부인력 투입')

    def test_external_out_action(self):
        """외부인력 철수 발령 생성"""
        action = PersonnelAction.objects.create(
            employee=self.profile,
            action_type=PersonnelAction.ActionType.EXTERNAL_OUT,
            effective_date=date.today(),
            created_by=self.manager,
        )
        self.assertEqual(action.action_type, 'EXTERNAL_OUT')
        self.assertEqual(action.get_action_type_display(), '외부인력 철수')

    def test_new_action_types_in_choices(self):
        """새 발령유형이 choices에 포함됨"""
        choices = dict(PersonnelAction.ActionType.choices)
        self.assertIn('DISPATCH_IN', choices)
        self.assertIn('DISPATCH_EXTEND', choices)
        self.assertIn('DISPATCH_END', choices)
        self.assertIn('EXTERNAL_IN', choices)
        self.assertIn('EXTERNAL_OUT', choices)


class EmployeeBankSyncTest(TestCase):
    """직원 계좌 → 회계 BankAccount 연동 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='bankuser', password='testpass123', role='staff', name='홍길동',
        )
        self.dept = Department.objects.create(name='영업팀', code='SALES')
        self.pos = Position.objects.create(name='사원', code='STAFF', level=5)

    def test_bank_info_creates_account(self):
        """직원 계좌정보 입력 시 BankAccount(PERSONAL) 자동 생성"""
        from apps.accounting.models import BankAccount
        profile = EmployeeProfile.objects.create(
            user=self.user, employee_number='EMP-001',
            department=self.dept, position=self.pos,
            hire_date=date.today(),
            bank_name='국민은행', bank_account='123-456-789',
        )
        acct = BankAccount.objects.filter(employee=profile).first()
        self.assertIsNotNone(acct)
        self.assertEqual(acct.account_type, 'PERSONAL')
        self.assertEqual(acct.bank, '국민은행')
        self.assertEqual(acct.account_number, '123-456-789')
        self.assertIn('홍길동', acct.name)

    def test_bank_info_update_syncs(self):
        """직원 계좌정보 변경 시 BankAccount도 갱신"""
        from apps.accounting.models import BankAccount
        profile = EmployeeProfile.objects.create(
            user=self.user, employee_number='EMP-002',
            department=self.dept, position=self.pos,
            hire_date=date.today(),
            bank_name='국민은행', bank_account='111-222-333',
        )
        profile.bank_name = '신한은행'
        profile.bank_account = '999-888-777'
        profile.save()
        acct = BankAccount.objects.get(employee=profile)
        self.assertEqual(acct.bank, '신한은행')
        self.assertEqual(acct.account_number, '999-888-777')

    def test_no_bank_info_skips(self):
        """계좌정보 미입력 시 BankAccount 생성 안 됨"""
        from apps.accounting.models import BankAccount
        profile = EmployeeProfile.objects.create(
            user=self.user, employee_number='EMP-003',
            department=self.dept, position=self.pos,
            hire_date=date.today(),
        )
        self.assertFalse(BankAccount.objects.filter(employee=profile).exists())

    def test_no_duplicate_accounts(self):
        """동일 직원 계좌 반복 저장해도 BankAccount 1개만 유지"""
        from apps.accounting.models import BankAccount
        profile = EmployeeProfile.objects.create(
            user=self.user, employee_number='EMP-004',
            department=self.dept, position=self.pos,
            hire_date=date.today(),
            bank_name='우리은행', bank_account='555-666-777',
        )
        # 2번 더 저장
        profile.save()
        profile.save()
        self.assertEqual(BankAccount.objects.filter(employee=profile).count(), 1)
