from django.core.cache import cache
from django.test import TestCase, Client, RequestFactory, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class UserModelTest(TestCase):
    """User 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123',
            name='테스트유저', phone='010-1234-5678', role='staff',
        )

    def test_user_creation(self):
        """사용자 생성 및 기본값 확인"""
        self.assertEqual(self.user.username, 'testuser')
        self.assertEqual(self.user.name, '테스트유저')
        self.assertEqual(self.user.phone, '010-1234-5678')
        self.assertEqual(self.user.role, 'staff')

    def test_str_with_name(self):
        """이름이 있으면 이름(username) 반환"""
        self.assertEqual(str(self.user), '테스트유저 (testuser)')

    def test_str_without_name(self):
        """이름이 없으면 username 반환"""
        user = User.objects.create_user(
            username='noname', password='testpass123',
        )
        self.assertEqual(str(user), 'noname')

    def test_default_role_is_staff(self):
        """기본 역할은 staff"""
        user = User.objects.create_user(
            username='defaultrole', password='testpass123',
        )
        self.assertEqual(user.role, User.Role.STAFF)

    def test_is_admin_role(self):
        """admin 역할일 때 is_admin_role True"""
        admin = User.objects.create_user(
            username='admin_user', password='testpass123', role='admin',
        )
        self.assertTrue(admin.is_admin_role)
        self.assertFalse(self.user.is_admin_role)

    def test_is_manager_role(self):
        """admin 또는 manager 역할일 때 is_manager_role True"""
        admin = User.objects.create_user(
            username='admin2', password='testpass123', role='admin',
        )
        manager = User.objects.create_user(
            username='manager2', password='testpass123', role='manager',
        )
        self.assertTrue(admin.is_manager_role)
        self.assertTrue(manager.is_manager_role)
        self.assertFalse(self.user.is_manager_role)

    def test_role_choices(self):
        """역할 선택지 확인"""
        choices = dict(User.Role.choices)
        self.assertIn('admin', choices)
        self.assertIn('manager', choices)
        self.assertIn('staff', choices)


class UserViewAccessTest(TestCase):
    """사용자 관리 뷰 접근 제어 테스트"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin', password='testpass123',
            role='admin', name='관리자',
        )
        self.manager = User.objects.create_user(
            username='manager', password='testpass123',
            role='manager', name='매니저',
        )
        self.staff = User.objects.create_user(
            username='staff', password='testpass123',
            role='staff', name='직원',
        )

    def test_user_list_requires_admin(self):
        """사용자 목록은 admin만 접근 가능"""
        self.client.force_login(User.objects.get(username='admin'))
        response = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(response.status_code, 200)

    def test_user_list_denied_for_manager(self):
        """사용자 목록은 manager 접근 불가 (403)"""
        self.client.force_login(User.objects.get(username='manager'))
        response = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(response.status_code, 403)

    def test_user_list_denied_for_staff(self):
        """사용자 목록은 staff 접근 불가 (403)"""
        self.client.force_login(User.objects.get(username='staff'))
        response = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(response.status_code, 403)

    def test_user_list_redirect_for_anonymous(self):
        """비로그인 사용자는 로그인 페이지로 리다이렉트"""
        response = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_user_create_requires_admin(self):
        """사용자 생성 폼 접근은 admin만 가능"""
        self.client.force_login(User.objects.get(username='admin'))
        response = self.client.get(reverse('accounts:user_create'))
        self.assertEqual(response.status_code, 200)

    def test_user_create_denied_for_staff(self):
        """사용자 생성 폼은 staff 접근 불가"""
        self.client.force_login(User.objects.get(username='staff'))
        response = self.client.get(reverse('accounts:user_create'))
        self.assertEqual(response.status_code, 403)

    def test_user_update_requires_admin(self):
        """사용자 수정은 admin만 가능"""
        self.client.force_login(User.objects.get(username='admin'))
        response = self.client.get(
            reverse('accounts:user_update', kwargs={'pk': self.staff.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_user_update_denied_for_manager(self):
        """사용자 수정은 manager 접근 불가"""
        self.client.force_login(User.objects.get(username='manager'))
        response = self.client.get(
            reverse('accounts:user_update', kwargs={'pk': self.staff.pk})
        )
        self.assertEqual(response.status_code, 403)


class LoginLogoutTest(TestCase):
    """로그인/로그아웃 테스트"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='logintest', password='testpass123',
            name='로그인테스트', role='staff',
        )

    def test_login_page_loads(self):
        """로그인 페이지 로드"""
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)

    def test_login_success(self):
        """올바른 자격 증명으로 로그인 성공"""
        response = self.client.post(reverse('accounts:login'), {
            'username': 'logintest',
            'password': 'testpass123',
        })
        # 성공 시 리다이렉트
        self.assertEqual(response.status_code, 302)

    def test_login_failure(self):
        """잘못된 비밀번호로 로그인 실패"""
        response = self.client.post(reverse('accounts:login'), {
            'username': 'logintest',
            'password': 'wrongpassword',
        })
        # 실패 시 200 (같은 페이지에 에러 표시)
        self.assertEqual(response.status_code, 200)

    def test_logout(self):
        """로그아웃 후 리다이렉트"""
        self.client.force_login(User.objects.get(username='logintest'))
        response = self.client.post(reverse('accounts:logout'))
        self.assertEqual(response.status_code, 302)

    def test_login_with_email(self):
        """이메일로 로그인"""
        self.user.email = 'login@test.com'
        self.user.save(update_fields=['email'])
        response = self.client.post(reverse('accounts:login'), {
            'username': 'login@test.com',
            'password': 'testpass123',
        })
        self.assertEqual(response.status_code, 302)

    def test_login_with_employee_number(self):
        """사번으로 로그인 (username=사번 설계)"""
        from apps.hr.models import EmployeeProfile
        from datetime import date
        # 새 설계: User.username = 사번
        self.user.username = 'EMP-001'
        self.user.save(update_fields=['username'])
        EmployeeProfile.objects.create(
            user=self.user, employee_number='EMP-001',
            hire_date=date.today(),
            created_by=self.user,
        )
        response = self.client.post(reverse('accounts:login'), {
            'username': 'EMP-001',
            'password': 'testpass123',
        })
        self.assertEqual(response.status_code, 302)


class UserCreateFormTest(TestCase):
    """사용자 생성 폼 테스트"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin', password='testpass123', role='admin',
        )
        self.client.force_login(User.objects.get(username='admin'))

    def test_create_user_via_form(self):
        """admin이 새 사용자 생성"""
        response = self.client.post(reverse('accounts:user_create'), {
            'username': 'newuser',
            'name': '신규사용자',
            'phone': '010-9999-8888',
            'role': 'staff',
            'password1': 'ComplexPass123!',
            'password2': 'ComplexPass123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newuser').exists())
        new_user = User.objects.get(username='newuser')
        self.assertEqual(new_user.name, '신규사용자')
        self.assertEqual(new_user.role, 'staff')

    def test_create_user_password_mismatch(self):
        """비밀번호 불일치 시 생성 실패"""
        response = self.client.post(reverse('accounts:user_create'), {
            'username': 'failuser',
            'name': '실패사용자',
            'role': 'staff',
            'password1': 'ComplexPass123!',
            'password2': 'DifferentPass456!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='failuser').exists())


class PermissionRequestViewTest(TestCase):
    """권한 신청 뷰 테스트"""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='perm_staff', password='testpass123', role='staff',
            name='일반직원',
        )
        self.manager = User.objects.create_user(
            username='perm_manager', password='testpass123', role='manager',
            name='매니저',
        )
        self.admin = User.objects.create_user(
            username='perm_admin', password='testpass123', role='admin',
            name='관리자',
        )
        self.url = reverse('accounts:permission_request')

    def test_staff_access(self):
        """직원 접근 가능"""
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '권한 신청')

    def test_anonymous_redirect(self):
        """비로그인 리다이렉트"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_staff_request_manager(self):
        """직원이 매니저 권한 신청"""
        self.client.force_login(self.staff)
        response = self.client.post(self.url, {
            'requested_role': 'manager',
            'reason': '업무 확장 필요',
        })
        self.assertEqual(response.status_code, 302)
        from apps.approval.models import ApprovalRequest
        self.assertTrue(
            ApprovalRequest.objects.filter(
                requester=self.staff,
                status='SUBMITTED',
            ).exists()
        )

    def test_manager_request_admin(self):
        """매니저가 관리자 권한 신청"""
        self.client.force_login(self.manager)
        response = self.client.post(self.url, {
            'requested_role': 'admin',
            'reason': '관리자 업무 필요',
        })
        self.assertEqual(response.status_code, 302)

    def test_admin_cannot_request(self):
        """관리자는 신청 불가 (이미 최상위)"""
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '최상위 권한')

    def test_duplicate_request_blocked(self):
        """중복 신청 방지"""
        self.client.force_login(self.staff)
        self.client.post(self.url, {
            'requested_role': 'manager',
            'reason': '첫 번째 신청',
        })
        response = self.client.post(self.url, {
            'requested_role': 'manager',
            'reason': '두 번째 신청',
        })
        self.assertEqual(response.status_code, 200)  # form_invalid
        from apps.approval.models import ApprovalRequest
        self.assertEqual(
            ApprovalRequest.objects.filter(
                requester=self.staff,
                status='SUBMITTED',
            ).count(),
            1,
        )

    def test_request_history_shown(self):
        """신청 이력 표시"""
        self.client.force_login(self.staff)
        self.client.post(self.url, {
            'requested_role': 'manager',
            'reason': '테스트 사유',
        })
        response = self.client.get(self.url)
        self.assertContains(response, '신청 이력')


# ── 모듈 권한 시스템 테스트 ──

class ModulePermissionModelTest(TestCase):
    """ModulePermission 모델 테스트"""

    def test_auto_codename(self):
        """codename 자동 생성"""
        from apps.accounts.models import ModulePermission
        # 시드 데이터가 이미 존재할 수 있으므로 get_or_create 사용
        perm, _ = ModulePermission.objects.get_or_create(
            codename='sales.VIEW',
            defaults={'module': 'sales', 'action': 'VIEW',
                      'created_by': User.objects.create_user(username='t1', password='p')},
        )
        self.assertEqual(perm.codename, 'sales.VIEW')

    def test_auto_description(self):
        """설명 자동 생성"""
        from apps.accounts.models import ModulePermission
        perm, _ = ModulePermission.objects.get_or_create(
            codename='inventory.CREATE',
            defaults={'module': 'inventory', 'action': 'CREATE',
                      'created_by': User.objects.create_user(username='t2', password='p')},
        )
        self.assertIn('재고관리', perm.description)
        self.assertIn('생성', perm.description)

    def test_codename_unique(self):
        """codename 중복 방지"""
        from django.db import IntegrityError
        from apps.accounts.models import ModulePermission
        u = User.objects.create_user(username='t3', password='p')
        # 시드와 충돌 없는 코드로 테스트
        ModulePermission.objects.get_or_create(
            codename='sales.VIEW',
            defaults={'module': 'sales', 'action': 'VIEW', 'created_by': u})
        with self.assertRaises(IntegrityError):
            ModulePermission.objects.create(
                module='sales', action='VIEW', codename='sales.VIEW', created_by=u)


class PermissionGroupModelTest(TestCase):
    """PermissionGroup 모델 테스트"""

    def setUp(self):
        self.admin = User.objects.create_user(username='grp_admin', password='p', role='admin')

    def test_create_group(self):
        from apps.accounts.models import PermissionGroup
        g = PermissionGroup.objects.create(name='테스트그룹', created_by=self.admin)
        self.assertEqual(str(g), '테스트그룹')

    def test_group_ordering(self):
        from apps.accounts.models import PermissionGroup
        g1 = PermissionGroup.objects.create(name='OrderA', priority=10, created_by=self.admin)
        g2 = PermissionGroup.objects.create(name='OrderB', priority=20, created_by=self.admin)
        groups = list(PermissionGroup.objects.filter(
            is_active=True, name__startswith='Order'))
        self.assertEqual(groups[0], g2)  # priority 20 먼저
        self.assertEqual(groups[1], g1)


class PermissionResolutionTest(TestCase):
    """권한 해석 로직 테스트 (그룹 + 사용자 오버라이드)"""

    def setUp(self):
        from apps.accounts.models import (
            ModulePermission, PermissionGroup,
            PermissionGroupPermission, PermissionGroupMembership,
            UserPermission,
        )
        self.admin = User.objects.create_user(username='res_admin', password='p', role='admin')
        self.staff = User.objects.create_user(username='res_staff', password='p', role='staff')

        # 권한 가져오기 (시드 데이터 존재)
        self.perm_sales_view, _ = ModulePermission.objects.get_or_create(
            codename='sales.VIEW',
            defaults={'module': 'sales', 'action': 'VIEW', 'created_by': self.admin})
        self.perm_sales_create, _ = ModulePermission.objects.get_or_create(
            codename='sales.CREATE',
            defaults={'module': 'sales', 'action': 'CREATE', 'created_by': self.admin})
        self.perm_inv_view, _ = ModulePermission.objects.get_or_create(
            codename='inventory.VIEW',
            defaults={'module': 'inventory', 'action': 'VIEW', 'created_by': self.admin})

        # 그룹 생성 + 권한 할당
        self.group = PermissionGroup.objects.create(name='영업팀', created_by=self.admin)
        PermissionGroupPermission.objects.create(
            group=self.group, permission=self.perm_sales_view, created_by=self.admin)
        PermissionGroupPermission.objects.create(
            group=self.group, permission=self.perm_sales_create, created_by=self.admin)

        # 사용자를 그룹에 추가
        PermissionGroupMembership.objects.create(
            user=self.staff, group=self.group, assigned_by=self.admin, created_by=self.admin)

        cache.clear()

    def test_admin_bypass(self):
        """admin은 None 반환 (전체 통과)"""
        self.assertIsNone(self.admin.get_module_permissions())
        self.assertTrue(self.admin.has_module_permission('sales', 'VIEW'))
        self.assertTrue(self.admin.has_module_permission('anything', 'DELETE'))

    def test_group_permissions(self):
        """그룹 권한 정상 해석"""
        self.assertTrue(self.staff.has_module_permission('sales', 'VIEW'))
        self.assertTrue(self.staff.has_module_permission('sales', 'CREATE'))
        self.assertFalse(self.staff.has_module_permission('inventory', 'VIEW'))

    def test_user_grant_override(self):
        """사용자 직접 부여가 그룹에 없는 권한을 추가"""
        from apps.accounts.models import UserPermission
        cache.clear()
        UserPermission.objects.create(
            user=self.staff, permission=self.perm_inv_view,
            grant=True, assigned_by=self.admin, created_by=self.admin)
        cache.clear()
        self.assertTrue(self.staff.has_module_permission('inventory', 'VIEW'))

    def test_user_deny_override(self):
        """사용자 직접 차단이 그룹 권한을 제거"""
        from apps.accounts.models import UserPermission
        cache.clear()
        UserPermission.objects.create(
            user=self.staff, permission=self.perm_sales_create,
            grant=False, assigned_by=self.admin, created_by=self.admin)
        cache.clear()
        self.assertTrue(self.staff.has_module_permission('sales', 'VIEW'))  # 그룹 유지
        self.assertFalse(self.staff.has_module_permission('sales', 'CREATE'))  # 차단됨

    def test_no_group_no_permission(self):
        """그룹 미소속 사용자는 권한 없음"""
        lonely = User.objects.create_user(username='lonely', password='p', role='staff')
        self.assertFalse(lonely.has_module_permission('sales', 'VIEW'))

    def test_inactive_membership_ignored(self):
        """비활성 멤버십은 무시"""
        from apps.accounts.models import PermissionGroupMembership
        cache.clear()
        PermissionGroupMembership.objects.filter(
            user=self.staff, group=self.group).update(is_active=False)
        cache.clear()
        self.assertFalse(self.staff.has_module_permission('sales', 'VIEW'))


class PermissionCacheTest(TestCase):
    """권한 캐시 및 무효화 테스트"""

    def setUp(self):
        from apps.accounts.models import (
            ModulePermission, PermissionGroup,
            PermissionGroupPermission, PermissionGroupMembership,
        )
        self.admin = User.objects.create_user(username='cache_admin', password='p', role='admin')
        self.staff = User.objects.create_user(username='cache_staff', password='p', role='staff')

        self.perm, _ = ModulePermission.objects.get_or_create(
            codename='hr.VIEW',
            defaults={'module': 'hr', 'action': 'VIEW', 'created_by': self.admin})
        self.group = PermissionGroup.objects.create(name='인사팀_테스트', created_by=self.admin)
        PermissionGroupPermission.objects.create(
            group=self.group, permission=self.perm, created_by=self.admin)
        PermissionGroupMembership.objects.create(
            user=self.staff, group=self.group, assigned_by=self.admin, created_by=self.admin)
        cache.clear()

    def test_cache_populated(self):
        """첫 조회 후 캐시에 저장"""
        self.staff.get_module_permissions()
        cached = cache.get(f'user_perms:{self.staff.id}')
        self.assertIsNotNone(cached)
        self.assertIn('hr.VIEW', cached)

    def test_cache_invalidated_on_membership_change(self):
        """멤버십 변경 시 캐시 무효화"""
        self.staff.get_module_permissions()
        self.assertIsNotNone(cache.get(f'user_perms:{self.staff.id}'))

        from apps.accounts.models import PermissionGroupMembership
        PermissionGroupMembership.objects.filter(user=self.staff).update(is_active=False)
        # signal fires on save, not update — manual invalidation for update()
        from apps.accounts.permission_utils import invalidate_user_perm_cache
        invalidate_user_perm_cache(self.staff.id)
        self.assertIsNone(cache.get(f'user_perms:{self.staff.id}'))

    def test_cache_invalidated_on_user_permission_change(self):
        """직접 권한 변경 시 캐시 무효화"""
        self.staff.get_module_permissions()
        self.assertIsNotNone(cache.get(f'user_perms:{self.staff.id}'))

        from apps.accounts.models import UserPermission
        UserPermission.objects.create(
            user=self.staff, permission=self.perm,
            grant=False, created_by=self.admin)
        # post_save signal fires → cache invalidated
        self.assertIsNone(cache.get(f'user_perms:{self.staff.id}'))


class ModulePermissionMixinTest(TestCase):
    """ModulePermissionMixin 뷰 접근 제어 테스트"""

    def setUp(self):
        from apps.accounts.models import (
            ModulePermission, PermissionGroup,
            PermissionGroupPermission, PermissionGroupMembership,
        )
        self.client = Client()
        self.admin = User.objects.create_user(username='mx_admin', password='p', role='admin')
        self.staff = User.objects.create_user(username='mx_staff', password='p', role='staff')
        self.perm, _ = ModulePermission.objects.get_or_create(
            codename='sales.VIEW',
            defaults={'module': 'sales', 'action': 'VIEW', 'created_by': self.admin})
        self.group = PermissionGroup.objects.create(name='영업조회_테스트', created_by=self.admin)
        PermissionGroupPermission.objects.create(
            group=self.group, permission=self.perm, created_by=self.admin)
        cache.clear()

    def test_admin_always_passes(self):
        """admin은 ModulePermissionMixin 통과"""
        self.client.force_login(self.admin)
        # 권한 그룹 리스트 (AdminRequiredMixin) 접근 테스트
        response = self.client.get(reverse('accounts:permission_group_list'))
        self.assertEqual(response.status_code, 200)

    def test_staff_without_permission_denied(self):
        """권한 없는 staff는 접근 거부"""
        # has_module_permission 직접 테스트
        self.assertFalse(self.staff.has_module_permission('sales', 'VIEW'))

    def test_staff_with_group_permission_allowed(self):
        """그룹 권한 부여 후 접근 허용"""
        from apps.accounts.models import PermissionGroupMembership
        PermissionGroupMembership.objects.create(
            user=self.staff, group=self.group, assigned_by=self.admin, created_by=self.admin)
        cache.clear()
        self.assertTrue(self.staff.has_module_permission('sales', 'VIEW'))


class PermissionGroupViewTest(TestCase):
    """권한 그룹 CRUD 뷰 테스트"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='pgv_admin', password='testpass123', role='admin', name='관리자')
        self.staff = User.objects.create_user(
            username='pgv_staff', password='testpass123', role='staff', name='직원')
        self.client.force_login(self.admin)

    def test_list_view(self):
        """권한 그룹 목록 접근"""
        response = self.client.get(reverse('accounts:permission_group_list'))
        self.assertEqual(response.status_code, 200)

    def test_list_denied_for_staff(self):
        """직원은 권한 그룹 목록 접근 불가"""
        self.client.force_login(self.staff)
        response = self.client.get(reverse('accounts:permission_group_list'))
        self.assertEqual(response.status_code, 403)

    def test_create_group(self):
        """권한 그룹 생성"""
        response = self.client.post(reverse('accounts:permission_group_create'), {
            'name': '테스트그룹',
            'description': '테스트용 그룹',
            'priority': 5,
        })
        self.assertEqual(response.status_code, 302)
        from apps.accounts.models import PermissionGroup
        self.assertTrue(PermissionGroup.objects.filter(name='테스트그룹').exists())

    def test_create_group_with_permissions(self):
        """권한 포함하여 그룹 생성"""
        from apps.accounts.models import ModulePermission
        ModulePermission.objects.get_or_create(
            codename='sales.VIEW',
            defaults={'module': 'sales', 'action': 'VIEW', 'created_by': self.admin})
        ModulePermission.objects.get_or_create(
            codename='sales.CREATE',
            defaults={'module': 'sales', 'action': 'CREATE', 'created_by': self.admin})
        response = self.client.post(reverse('accounts:permission_group_create'), {
            'name': '영업팀',
            'description': '',
            'priority': 0,
            'permissions': ['sales.VIEW', 'sales.CREATE'],
        })
        self.assertEqual(response.status_code, 302)
        from apps.accounts.models import PermissionGroup, PermissionGroupPermission
        grp = PermissionGroup.objects.get(name='영업팀')
        self.assertEqual(
            PermissionGroupPermission.objects.filter(group=grp, is_active=True).count(), 2)

    def test_update_group(self):
        """권한 그룹 수정"""
        from apps.accounts.models import PermissionGroup
        grp = PermissionGroup.objects.create(name='원본', created_by=self.admin)
        response = self.client.post(
            reverse('accounts:permission_group_update', kwargs={'pk': grp.pk}), {
                'name': '수정됨',
                'description': '설명 추가',
                'priority': 10,
            })
        self.assertEqual(response.status_code, 302)
        grp.refresh_from_db()
        self.assertEqual(grp.name, '수정됨')

    def test_create_group_with_members(self):
        """멤버 포함하여 그룹 생성"""
        response = self.client.post(reverse('accounts:permission_group_create'), {
            'name': '멤버그룹',
            'description': '',
            'priority': 0,
            'members': [str(self.staff.pk)],
        })
        self.assertEqual(response.status_code, 302)
        from apps.accounts.models import PermissionGroupMembership
        self.assertTrue(
            PermissionGroupMembership.objects.filter(
                user=self.staff, group__name='멤버그룹', is_active=True).exists())


class UserPermissionViewTest(TestCase):
    """사용자별 권한 관리 뷰 테스트"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='upv_admin', password='testpass123', role='admin', name='관리자')
        self.staff = User.objects.create_user(
            username='upv_staff', password='testpass123', role='staff', name='직원')
        self.client.force_login(self.admin)

    def test_user_permissions_view(self):
        """사용자 권한 관리 페이지 접근"""
        url = reverse('accounts:user_permissions', kwargs={'pk': self.staff.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '직원')

    def test_assign_group_via_post(self):
        """POST로 그룹 멤버십 할당"""
        from apps.accounts.models import PermissionGroup
        grp = PermissionGroup.objects.create(name='할당테스트', created_by=self.admin)
        url = reverse('accounts:user_permissions', kwargs={'pk': self.staff.pk})
        response = self.client.post(url, {
            'groups': [str(grp.pk)],
        })
        self.assertEqual(response.status_code, 302)
        from apps.accounts.models import PermissionGroupMembership
        self.assertTrue(
            PermissionGroupMembership.objects.filter(
                user=self.staff, group=grp, is_active=True).exists())

    def test_denied_for_staff(self):
        """직원은 다른 사용자 권한 관리 불가"""
        self.client.force_login(self.staff)
        url = reverse('accounts:user_permissions', kwargs={'pk': self.admin.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)


class TemplateTagsTest(TestCase):
    """권한 관련 템플릿 태그 테스트"""

    def test_perm_codename(self):
        from apps.accounts.templatetags.permissions import perm_codename
        self.assertEqual(perm_codename('sales', 'VIEW'), 'sales.VIEW')

    def test_perm_checked(self):
        from apps.accounts.templatetags.permissions import perm_checked
        assigned = {'sales.VIEW', 'inventory.CREATE'}
        self.assertEqual(perm_checked('sales', 'VIEW', assigned), 'checked')
        self.assertEqual(perm_checked('sales', 'CREATE', assigned), '')

    def test_direct_perm_value(self):
        from apps.accounts.templatetags.permissions import direct_perm_value
        direct = {'sales.VIEW': True, 'hr.DELETE': False}
        self.assertEqual(direct_perm_value('sales', 'VIEW', direct), 'grant')
        self.assertEqual(direct_perm_value('hr', 'DELETE', direct), 'deny')
        self.assertEqual(direct_perm_value('inventory', 'VIEW', direct), 'none')

    def test_has_group_perm(self):
        from apps.accounts.templatetags.permissions import has_group_perm
        group_perms = {'sales.VIEW', 'sales.CREATE'}
        self.assertTrue(has_group_perm('sales', 'VIEW', group_perms))
        self.assertFalse(has_group_perm('hr', 'VIEW', group_perms))

    def test_has_module_access_filter(self):
        from apps.accounts.templatetags.permissions import has_module_access
        cache.clear()
        admin = User.objects.create_user(username='tag_admin', password='p', role='admin')
        staff = User.objects.create_user(username='tag_staff', password='p', role='staff')
        self.assertTrue(has_module_access(admin, 'anything'))
        self.assertFalse(has_module_access(staff, 'sales'))

    def test_has_module_access_unauthenticated(self):
        from apps.accounts.templatetags.permissions import has_module_access
        from django.contrib.auth.models import AnonymousUser
        self.assertFalse(has_module_access(AnonymousUser(), 'sales'))
        self.assertFalse(has_module_access(None, 'sales'))


# ── 엣지케이스 + 삭제 뷰 테스트 ──

class PermissionGroupDeleteViewTest(TestCase):
    """권한 그룹 soft delete 뷰 테스트"""

    def setUp(self):
        from apps.accounts.models import (
            ModulePermission, PermissionGroup,
            PermissionGroupPermission, PermissionGroupMembership,
        )
        self.client = Client()
        self.admin = User.objects.create_user(
            username='del_admin', password='testpass123', role='admin', name='관리자')
        self.staff = User.objects.create_user(
            username='del_staff', password='testpass123', role='staff', name='직원')
        self.client.force_login(self.admin)

        self.perm, _ = ModulePermission.objects.get_or_create(
            codename='sales.VIEW',
            defaults={'module': 'sales', 'action': 'VIEW', 'created_by': self.admin})
        self.group = PermissionGroup.objects.create(
            name='삭제테스트', created_by=self.admin)
        PermissionGroupPermission.objects.create(
            group=self.group, permission=self.perm, created_by=self.admin)
        PermissionGroupMembership.objects.create(
            user=self.staff, group=self.group, assigned_by=self.admin, created_by=self.admin)

    def test_soft_delete_group(self):
        """권한 그룹 soft delete"""
        from apps.accounts.models import (
            PermissionGroup, PermissionGroupPermission, PermissionGroupMembership,
        )
        url = reverse('accounts:permission_group_delete', kwargs={'pk': self.group.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.group.refresh_from_db()
        self.assertFalse(self.group.is_active)
        # 연관 매핑도 비활성화
        self.assertFalse(
            PermissionGroupPermission.objects.filter(
                group=self.group, is_active=True).exists())
        self.assertFalse(
            PermissionGroupMembership.objects.filter(
                group=self.group, is_active=True).exists())

    def test_delete_denied_for_staff(self):
        """직원은 삭제 불가"""
        self.client.force_login(self.staff)
        url = reverse('accounts:permission_group_delete', kwargs={'pk': self.group.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    def test_delete_nonexistent_returns_404(self):
        """존재하지 않는 그룹 삭제 시 404"""
        url = reverse('accounts:permission_group_delete', kwargs={'pk': 99999})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    def test_delete_already_inactive_returns_404(self):
        """이미 비활성화된 그룹 삭제 시 404"""
        self.group.is_active = False
        self.group.save(update_fields=['is_active'])
        url = reverse('accounts:permission_group_delete', kwargs={'pk': self.group.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    def test_get_not_allowed(self):
        """GET 요청은 405"""
        url = reverse('accounts:permission_group_delete', kwargs={'pk': self.group.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)


class PermissionGroupSyncEdgeCaseTest(TestCase):
    """_sync_permissions / _sync_members 엣지케이스"""

    def setUp(self):
        from apps.accounts.models import (
            ModulePermission, PermissionGroup,
            PermissionGroupPermission,
        )
        self.client = Client()
        self.admin = User.objects.create_user(
            username='sync_admin', password='testpass123', role='admin')
        self.client.force_login(self.admin)

        self.perm_sv, _ = ModulePermission.objects.get_or_create(
            codename='sales.VIEW',
            defaults={'module': 'sales', 'action': 'VIEW', 'created_by': self.admin})
        self.perm_sc, _ = ModulePermission.objects.get_or_create(
            codename='sales.CREATE',
            defaults={'module': 'sales', 'action': 'CREATE', 'created_by': self.admin})
        self.group = PermissionGroup.objects.create(name='동기화테스트', created_by=self.admin)
        PermissionGroupPermission.objects.create(
            group=self.group, permission=self.perm_sv, created_by=self.admin)

    def test_sync_permissions_with_nonexistent_codename(self):
        """존재하지 않는 codename은 무시"""
        from apps.accounts.models import PermissionGroupPermission
        url = reverse('accounts:permission_group_update', kwargs={'pk': self.group.pk})
        response = self.client.post(url, {
            'name': '동기화테스트',
            'description': '',
            'priority': 0,
            'permissions': ['nonexistent.FAKE', 'sales.VIEW'],
        })
        self.assertEqual(response.status_code, 302)
        active_perms = PermissionGroupPermission.objects.filter(
            group=self.group, is_active=True)
        codenames = set(active_perms.values_list('permission__codename', flat=True))
        self.assertIn('sales.VIEW', codenames)
        self.assertNotIn('nonexistent.FAKE', codenames)

    def test_sync_reactivates_soft_deleted_permission(self):
        """soft delete된 권한을 다시 선택하면 재활성화"""
        from apps.accounts.models import PermissionGroupPermission
        # sales.VIEW를 비활성화
        PermissionGroupPermission.objects.filter(
            group=self.group, permission=self.perm_sv).update(is_active=False)
        url = reverse('accounts:permission_group_update', kwargs={'pk': self.group.pk})
        response = self.client.post(url, {
            'name': '동기화테스트',
            'description': '',
            'priority': 0,
            'permissions': ['sales.VIEW'],
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            PermissionGroupPermission.objects.filter(
                group=self.group, permission=self.perm_sv, is_active=True).exists())

    def test_sync_with_invalid_member_ids(self):
        """잘못된 멤버 ID는 무시"""
        url = reverse('accounts:permission_group_update', kwargs={'pk': self.group.pk})
        response = self.client.post(url, {
            'name': '동기화테스트',
            'description': '',
            'priority': 0,
            'members': ['abc', '', '99999'],  # invalid, empty, non-existent user
        })
        self.assertEqual(response.status_code, 302)

    def test_sync_removes_unselected_permissions(self):
        """선택 해제된 권한은 soft delete"""
        from apps.accounts.models import PermissionGroupPermission
        url = reverse('accounts:permission_group_update', kwargs={'pk': self.group.pk})
        response = self.client.post(url, {
            'name': '동기화테스트',
            'description': '',
            'priority': 0,
            'permissions': [],  # 모든 권한 해제
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            PermissionGroupPermission.objects.filter(
                group=self.group, is_active=True).exists())


class UserPermissionViewEdgeCaseTest(TestCase):
    """UserPermissionView POST 엣지케이스"""

    def setUp(self):
        from apps.accounts.models import ModulePermission
        self.client = Client()
        self.admin = User.objects.create_user(
            username='upve_admin', password='testpass123', role='admin')
        self.staff = User.objects.create_user(
            username='upve_staff', password='testpass123', role='staff')
        self.client.force_login(self.admin)
        self.perm, _ = ModulePermission.objects.get_or_create(
            codename='hr.VIEW',
            defaults={'module': 'hr', 'action': 'VIEW', 'created_by': self.admin})
        cache.clear()

    def test_empty_post_clears_all(self):
        """빈 POST로 모든 직접 권한 + 그룹 멤버십 해제"""
        from apps.accounts.models import UserPermission, PermissionGroupMembership, PermissionGroup
        UserPermission.objects.create(
            user=self.staff, permission=self.perm,
            grant=True, assigned_by=self.admin, created_by=self.admin)
        grp = PermissionGroup.objects.create(name='임시그룹', created_by=self.admin)
        PermissionGroupMembership.objects.create(
            user=self.staff, group=grp, assigned_by=self.admin, created_by=self.admin)
        url = reverse('accounts:user_permissions', kwargs={'pk': self.staff.pk})
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            UserPermission.objects.filter(user=self.staff, is_active=True).exists())
        self.assertFalse(
            PermissionGroupMembership.objects.filter(user=self.staff, is_active=True).exists())

    def test_grant_and_deny_same_perm(self):
        """같은 권한이 grant와 deny 모두에 있으면 deny 우선 (grant -= deny)"""
        url = reverse('accounts:user_permissions', kwargs={'pk': self.staff.pk})
        response = self.client.post(url, {
            'grant_perms': ['hr.VIEW'],
            'deny_perms': ['hr.VIEW'],
        })
        self.assertEqual(response.status_code, 302)
        from apps.accounts.models import UserPermission
        up = UserPermission.objects.get(user=self.staff, permission=self.perm, is_active=True)
        # grant_perms -= deny_perms 로직에 의해 deny만 적용됨
        self.assertFalse(up.grant)

    def test_invalid_group_ids_ignored(self):
        """잘못된 그룹 ID는 무시"""
        url = reverse('accounts:user_permissions', kwargs={'pk': self.staff.pk})
        response = self.client.post(url, {
            'groups': ['abc', '', 'xyz'],
        })
        self.assertEqual(response.status_code, 302)

    def test_nonexistent_perm_codename_ignored(self):
        """존재하지 않는 codename은 무시"""
        url = reverse('accounts:user_permissions', kwargs={'pk': self.staff.pk})
        response = self.client.post(url, {
            'grant_perms': ['nonexistent.FAKE'],
        })
        self.assertEqual(response.status_code, 302)
        from apps.accounts.models import UserPermission
        self.assertFalse(
            UserPermission.objects.filter(user=self.staff, is_active=True).exists())


class PermissionCacheEdgeCaseTest(TestCase):
    """캐시 무효화 엣지케이스"""

    def setUp(self):
        from apps.accounts.models import (
            ModulePermission, PermissionGroup,
            PermissionGroupPermission, PermissionGroupMembership,
        )
        self.admin = User.objects.create_user(username='cedge_admin', password='p', role='admin')
        self.staff = User.objects.create_user(username='cedge_staff', password='p', role='staff')
        self.perm, _ = ModulePermission.objects.get_or_create(
            codename='hr.EDIT',
            defaults={'module': 'hr', 'action': 'EDIT', 'created_by': self.admin})
        self.group = PermissionGroup.objects.create(name='캐시테스트', created_by=self.admin)
        PermissionGroupPermission.objects.create(
            group=self.group, permission=self.perm, created_by=self.admin)
        PermissionGroupMembership.objects.create(
            user=self.staff, group=self.group, assigned_by=self.admin, created_by=self.admin)
        cache.clear()

    def test_group_permission_change_invalidates_member_cache(self):
        """그룹 권한 변경 시 해당 그룹 멤버 전원 캐시 무효화"""
        from apps.accounts.models import ModulePermission, PermissionGroupPermission
        # 캐시 워밍
        self.staff.get_module_permissions()
        self.assertIsNotNone(cache.get(f'user_perms:{self.staff.id}'))
        # 그룹에 새 권한 추가 (post_save signal 발동)
        new_perm, _ = ModulePermission.objects.get_or_create(
            codename='hr.DELETE',
            defaults={'module': 'hr', 'action': 'DELETE', 'created_by': self.admin})
        PermissionGroupPermission.objects.create(
            group=self.group, permission=new_perm, created_by=self.admin)
        self.assertIsNone(cache.get(f'user_perms:{self.staff.id}'))

    def test_inactive_group_permissions_not_resolved(self):
        """비활성 그룹은 권한 해석에 포함되지 않음"""
        cache.clear()
        self.group.is_active = False
        self.group.save(update_fields=['is_active'])
        cache.clear()
        self.assertFalse(self.staff.has_module_permission('hr', 'EDIT'))

    def test_inactive_permission_not_resolved(self):
        """비활성 ModulePermission은 권한 해석에 포함되지 않음"""
        cache.clear()
        self.perm.is_active = False
        self.perm.save(update_fields=['is_active'])
        cache.clear()
        self.assertFalse(self.staff.has_module_permission('hr', 'EDIT'))


class HasModulePermissionDRFTest(TestCase):
    """DRF HasModulePermission 퍼미션 클래스 테스트"""

    def setUp(self):
        from apps.accounts.models import (
            ModulePermission, PermissionGroup,
            PermissionGroupPermission, PermissionGroupMembership,
        )
        self.admin = User.objects.create_user(username='drf_admin', password='p', role='admin')
        self.staff = User.objects.create_user(username='drf_staff', password='p', role='staff')
        self.perm, _ = ModulePermission.objects.get_or_create(
            codename='sales.VIEW',
            defaults={'module': 'sales', 'action': 'VIEW', 'created_by': self.admin})
        self.group = PermissionGroup.objects.create(name='DRF테스트', created_by=self.admin)
        PermissionGroupPermission.objects.create(
            group=self.group, permission=self.perm, created_by=self.admin)
        PermissionGroupMembership.objects.create(
            user=self.staff, group=self.group, assigned_by=self.admin, created_by=self.admin)
        cache.clear()

    def test_unauthenticated_denied(self):
        from apps.api.permissions import HasModulePermission
        from django.contrib.auth.models import AnonymousUser
        perm = HasModulePermission()
        request = RequestFactory().get('/')
        request.user = AnonymousUser()

        class FakeView:
            module_permission = 'sales'
        self.assertFalse(perm.has_permission(request, FakeView()))

    def test_admin_always_allowed(self):
        from apps.api.permissions import HasModulePermission
        perm = HasModulePermission()
        request = RequestFactory().get('/')
        request.user = self.admin

        class FakeView:
            module_permission = 'sales'
        self.assertTrue(perm.has_permission(request, FakeView()))

    def test_no_module_permission_attr_allows(self):
        from apps.api.permissions import HasModulePermission
        perm = HasModulePermission()
        request = RequestFactory().get('/')
        request.user = self.staff

        class FakeView:
            pass
        self.assertTrue(perm.has_permission(request, FakeView()))

    def test_method_action_mapping(self):
        from apps.api.permissions import HasModulePermission
        perm = HasModulePermission()

        class FakeView:
            module_permission = 'sales'

        # staff has sales.VIEW, not sales.CREATE
        for method in ('GET', 'HEAD', 'OPTIONS'):
            request = RequestFactory().generic(method, '/')
            request.user = self.staff
            self.assertTrue(perm.has_permission(request, FakeView()), f'{method} should pass')

        request = RequestFactory().post('/')
        request.user = self.staff
        self.assertFalse(perm.has_permission(request, FakeView()))


class ModulePermissionMixinEdgeCaseTest(TestCase):
    """ModulePermissionMixin 엣지케이스"""

    def setUp(self):
        from apps.accounts.models import (
            ModulePermission, PermissionGroup,
            PermissionGroupPermission, PermissionGroupMembership,
        )
        self.admin = User.objects.create_user(username='mxe_admin', password='p', role='admin')
        self.staff = User.objects.create_user(username='mxe_staff', password='p', role='staff')
        self.perm_sv, _ = ModulePermission.objects.get_or_create(
            codename='sales.VIEW',
            defaults={'module': 'sales', 'action': 'VIEW', 'created_by': self.admin})
        self.perm_iv, _ = ModulePermission.objects.get_or_create(
            codename='inventory.VIEW',
            defaults={'module': 'inventory', 'action': 'VIEW', 'created_by': self.admin})
        self.group = PermissionGroup.objects.create(name='Mixin테스트', created_by=self.admin)
        PermissionGroupPermission.objects.create(
            group=self.group, permission=self.perm_sv, created_by=self.admin)
        PermissionGroupMembership.objects.create(
            user=self.staff, group=self.group, assigned_by=self.admin, created_by=self.admin)
        cache.clear()

    def test_require_all_permissions_and_logic(self):
        """require_all_permissions=True면 모든 권한 필요"""
        from apps.core.mixins import ModulePermissionMixin
        mixin = ModulePermissionMixin()
        mixin.required_permissions = ['sales.VIEW', 'inventory.VIEW']
        mixin.require_all_permissions = True
        # staff has sales.VIEW but not inventory.VIEW
        self.assertFalse(mixin._check_permissions(self.staff, mixin.required_permissions))

    def test_require_any_permissions_or_logic(self):
        """require_all_permissions=False면 하나만 있으면 통과"""
        from apps.core.mixins import ModulePermissionMixin
        mixin = ModulePermissionMixin()
        mixin.required_permissions = ['sales.VIEW', 'inventory.VIEW']
        mixin.require_all_permissions = False
        self.assertTrue(mixin._check_permissions(self.staff, mixin.required_permissions))

    def test_no_required_permissions_allows(self):
        """required_permission 미설정 시 통과"""
        from apps.core.mixins import ModulePermissionMixin
        mixin = ModulePermissionMixin()
        perms = mixin._get_permissions_to_check()
        self.assertEqual(perms, [])


class MultiGroupPermissionTest(TestCase):
    """복수 그룹 소속 시 권한 합산"""

    def setUp(self):
        from apps.accounts.models import (
            ModulePermission, PermissionGroup,
            PermissionGroupPermission, PermissionGroupMembership,
        )
        self.admin = User.objects.create_user(username='multi_admin', password='p', role='admin')
        self.staff = User.objects.create_user(username='multi_staff', password='p', role='staff')

        self.perm_sv, _ = ModulePermission.objects.get_or_create(
            codename='sales.VIEW',
            defaults={'module': 'sales', 'action': 'VIEW', 'created_by': self.admin})
        self.perm_iv, _ = ModulePermission.objects.get_or_create(
            codename='inventory.VIEW',
            defaults={'module': 'inventory', 'action': 'VIEW', 'created_by': self.admin})

        g1 = PermissionGroup.objects.create(name='그룹A', created_by=self.admin)
        PermissionGroupPermission.objects.create(
            group=g1, permission=self.perm_sv, created_by=self.admin)
        PermissionGroupMembership.objects.create(
            user=self.staff, group=g1, assigned_by=self.admin, created_by=self.admin)

        g2 = PermissionGroup.objects.create(name='그룹B', created_by=self.admin)
        PermissionGroupPermission.objects.create(
            group=g2, permission=self.perm_iv, created_by=self.admin)
        PermissionGroupMembership.objects.create(
            user=self.staff, group=g2, assigned_by=self.admin, created_by=self.admin)
        cache.clear()

    def test_permissions_union_from_multiple_groups(self):
        """두 그룹의 권한이 합산됨"""
        self.assertTrue(self.staff.has_module_permission('sales', 'VIEW'))
        self.assertTrue(self.staff.has_module_permission('inventory', 'VIEW'))


# ── 템플릿 렌더링 + 성능 테스트 ──

class TemplateRenderingTest(TestCase):
    """모든 accounts 템플릿이 에러 없이 렌더링되는지 확인"""

    def setUp(self):
        from apps.accounts.models import (
            ModulePermission, PermissionGroup,
            PermissionGroupPermission, PermissionGroupMembership,
        )
        self.client = Client()
        self.admin = User.objects.create_user(
            username='tpl_admin', password='testpass123', role='admin', name='관리자')
        self.staff = User.objects.create_user(
            username='tpl_staff', password='testpass123', role='staff', name='직원')
        self.manager = User.objects.create_user(
            username='tpl_manager', password='testpass123', role='manager', name='매니저')

        self.perm, _ = ModulePermission.objects.get_or_create(
            codename='sales.VIEW',
            defaults={'module': 'sales', 'action': 'VIEW', 'created_by': self.admin})
        self.group = PermissionGroup.objects.create(
            name='렌더링테스트', description='테스트용', priority=5, created_by=self.admin)
        PermissionGroupPermission.objects.create(
            group=self.group, permission=self.perm, created_by=self.admin)
        PermissionGroupMembership.objects.create(
            user=self.staff, group=self.group, assigned_by=self.admin, created_by=self.admin)
        self.client.force_login(self.admin)
        cache.clear()

    def test_user_list_renders(self):
        """사용자 목록 페이지 렌더링 (검색 + 필터 포함)"""
        response = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '사용자 관리')
        # prefetch된 perm_groups가 렌더링되는지
        self.assertContains(response, '렌더링테스트')

    def test_user_list_search_filter(self):
        """사용자 목록 검색 + 역할 필터"""
        response = self.client.get(reverse('accounts:user_list'), {'q': '직원', 'role': 'staff'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'tpl_staff')

    def test_user_list_pagination(self):
        """사용자 목록 페이지네이션"""
        for i in range(25):
            User.objects.create_user(username=f'page_user_{i}', password='p', name=f'유저{i}')
        response = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'page=2')

    def test_permission_group_list_renders(self):
        """권한 그룹 목록 페이지 — annotated member_count, perm_count 표시"""
        response = self.client.get(reverse('accounts:permission_group_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '렌더링테스트')

    def test_permission_group_create_form_renders(self):
        """권한 그룹 생성 폼 — 체크박스 매트릭스 + 멤버 목록 표시"""
        response = self.client.get(reverse('accounts:permission_group_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '모듈별 권한')
        self.assertContains(response, '멤버 관리')
        # 매트릭스에 모든 모듈이 렌더링되는지
        self.assertContains(response, '판매관리')
        self.assertContains(response, '재고관리')
        # 모든 액션이 렌더링되는지
        self.assertContains(response, '조회')
        self.assertContains(response, '생성')
        # 체크박스 name=permissions
        self.assertContains(response, 'name="permissions"')

    def test_permission_group_update_form_renders(self):
        """권한 그룹 수정 폼 — 기존 권한이 checked로 표시"""
        response = self.client.get(
            reverse('accounts:permission_group_update', kwargs={'pk': self.group.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '렌더링테스트')
        # 기존 할당 권한(sales.VIEW)이 checked
        self.assertContains(response, 'value="sales.VIEW"')

    def test_user_permissions_page_renders(self):
        """사용자 권한 관리 페이지 — 그룹 체크박스 + 직접 권한 select"""
        response = self.client.get(
            reverse('accounts:user_permissions', kwargs={'pk': self.staff.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '직원')
        # 그룹 체크박스
        self.assertContains(response, 'name="groups"')
        # 직접 권한 select
        self.assertContains(response, 'perm-select')
        # 그룹 권한 표시(G 마커)
        self.assertContains(response, 'G')

    def test_user_permissions_admin_notice(self):
        """admin 사용자의 권한 페이지에 관리자 안내 메시지"""
        response = self.client.get(
            reverse('accounts:user_permissions', kwargs={'pk': self.admin.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '관리자 역할은 모든 권한을')

    def test_permission_request_page_renders(self):
        """권한 신청 페이지 렌더링"""
        self.client.force_login(self.staff)
        response = self.client.get(reverse('accounts:permission_request'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '권한 신청')

    def test_permission_request_admin_page(self):
        """관리자 권한 신청 페이지 — 최상위 권한 안내"""
        self.client.force_login(self.admin)
        response = self.client.get(reverse('accounts:permission_request'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '최상위 권한')

    def test_profile_page_renders(self):
        """프로필 페이지 렌더링"""
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 200)

    def test_password_change_page_renders(self):
        """비밀번호 변경 페이지 렌더링"""
        response = self.client.get(reverse('accounts:password_change'))
        self.assertEqual(response.status_code, 200)

    def test_user_create_form_renders(self):
        """사용자 등록 폼 렌더링"""
        response = self.client.get(reverse('accounts:user_create'))
        self.assertEqual(response.status_code, 200)

    def test_user_update_form_renders(self):
        """사용자 수정 폼 렌더링"""
        response = self.client.get(
            reverse('accounts:user_update', kwargs={'pk': self.staff.pk}))
        self.assertEqual(response.status_code, 200)

    def test_admin_password_reset_renders(self):
        """관리자 비밀번호 재설정 페이지 렌더링"""
        response = self.client.get(
            reverse('accounts:admin_password_reset', kwargs={'pk': self.staff.pk}))
        self.assertEqual(response.status_code, 200)

    def test_permission_group_list_empty(self):
        """권한 그룹 0개 시 빈 상태 메시지"""
        from apps.accounts.models import PermissionGroup
        PermissionGroup.objects.update(is_active=False)
        response = self.client.get(reverse('accounts:permission_group_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '등록된 권한 그룹이 없습니다')

    def test_permission_group_delete_button_in_list(self):
        """권한 그룹 목록에 삭제 버튼이 표시"""
        response = self.client.get(reverse('accounts:permission_group_list'))
        delete_url = reverse('accounts:permission_group_delete', kwargs={'pk': self.group.pk})
        self.assertContains(response, delete_url)


class UserListPerformanceTest(TestCase):
    """대량 사용자 목록 Prefetch 성능 테스트"""

    def setUp(self):
        from apps.accounts.models import (
            PermissionGroup, PermissionGroupMembership,
        )
        self.client = Client()
        self.admin = User.objects.create_user(
            username='perf_admin', password='testpass123', role='admin')
        self.client.force_login(self.admin)
        self.group = PermissionGroup.objects.create(
            name='성능테스트', created_by=self.admin)

        # 100명 사용자 bulk create
        users = User.objects.bulk_create([
            User(username=f'perf_user_{i}', name=f'성능유저{i}', role='staff')
            for i in range(100)
        ])
        # 50명을 그룹에 추가
        PermissionGroupMembership.objects.bulk_create([
            PermissionGroupMembership(
                user=u, group=self.group, assigned_by=self.admin, created_by=self.admin)
            for u in users[:50]
        ])

    def test_user_list_with_many_users(self):
        """100+ 사용자 목록이 정상 렌더링"""
        response = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(response.status_code, 200)
        # 페이지네이션이 동작하는지 (20개씩)
        self.assertContains(response, 'page=2')

    def test_prefetch_works_with_pagination(self):
        """prefetch된 perm_groups가 페이지 2에서도 정상"""
        response = self.client.get(reverse('accounts:user_list'), {'page': 2})
        self.assertEqual(response.status_code, 200)

    def test_permission_group_form_many_users(self):
        """100+ 사용자가 멤버 목록에 표시"""
        response = self.client.get(reverse('accounts:permission_group_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '멤버 관리')
