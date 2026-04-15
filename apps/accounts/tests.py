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


# ═══════════════════════════════════════════════════
# IP 화이트리스트 테스트
# ═══════════════════════════════════════════════════

class IPWhitelistModelTest(TestCase):
    """IP 화이트리스트 모델 테스트"""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='ipadmin', password='testpass123', role='admin',
        )

    def test_create_ip_whitelist(self):
        """IP 화이트리스트 항목 생성"""
        from apps.accounts.models import IPWhitelist
        entry = IPWhitelist.objects.create(
            ip_address='192.168.1.100',
            description='사무실 IP',
            scope='ALL',
            created_by=self.admin,
        )
        self.assertEqual(entry.ip_address, '192.168.1.100')
        self.assertEqual(entry.scope, 'ALL')
        self.assertTrue(entry.is_active)

    def test_ip_whitelist_unique_constraint(self):
        """동일 IP+scope 중복 등록 차단"""
        from django.db import IntegrityError
        from apps.accounts.models import IPWhitelist
        IPWhitelist.objects.create(
            ip_address='10.0.0.1', scope='ADMIN',
        )
        with self.assertRaises(IntegrityError):
            IPWhitelist.objects.create(
                ip_address='10.0.0.1', scope='ADMIN',
            )

    def test_ip_whitelist_str(self):
        """__str__ 출력"""
        from apps.accounts.models import IPWhitelist
        entry = IPWhitelist.objects.create(
            ip_address='172.16.0.1', scope='AUDIT',
        )
        self.assertIn('172.16.0.1', str(entry))
        self.assertIn('감사', str(entry))


@override_settings(AXES_ENABLED=False)
class IPWhitelistViewTest(TestCase):
    """IP 화이트리스트 뷰 테스트"""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='ipadminv', password='testpass123', role='admin',
        )
        self.staff = User.objects.create_user(
            username='ipstaff', password='testpass123', role='staff',
        )

    def test_list_view_admin_only(self):
        """관리자만 IP 화이트리스트 목록 접근 가능"""
        self.client.login(username='ipstaff', password='testpass123')
        response = self.client.get(reverse('accounts:ip_whitelist_list'))
        self.assertEqual(response.status_code, 403)

    def test_list_view_admin_access(self):
        """관리자는 IP 화이트리스트 목록 접근 가능"""
        self.client.login(username='ipadminv', password='testpass123')
        response = self.client.get(reverse('accounts:ip_whitelist_list'))
        self.assertEqual(response.status_code, 200)

    def test_create_ip_entry(self):
        """IP 화이트리스트 항목 생성"""
        self.client.login(username='ipadminv', password='testpass123')
        response = self.client.post(reverse('accounts:ip_whitelist_create'), {
            'ip_address': '192.168.1.50',
            'description': '테스트 IP',
            'scope': 'ALL',
        })
        self.assertEqual(response.status_code, 302)
        from apps.accounts.models import IPWhitelist
        self.assertTrue(IPWhitelist.objects.filter(ip_address='192.168.1.50').exists())

    def test_delete_ip_entry(self):
        """IP 화이트리스트 항목 삭제 (soft delete)"""
        from apps.accounts.models import IPWhitelist
        # 테스트 클라이언트 IP (127.0.0.1) 도 허용해야 차단 안 됨
        IPWhitelist.objects.create(ip_address='127.0.0.1', scope='ALL')
        entry = IPWhitelist.objects.create(
            ip_address='10.0.0.5', scope='ALL',
        )
        self.client.login(username='ipadminv', password='testpass123')
        response = self.client.post(
            reverse('accounts:ip_whitelist_delete', kwargs={'pk': entry.pk}),
        )
        self.assertEqual(response.status_code, 302)
        entry.refresh_from_db()
        self.assertFalse(entry.is_active)


@override_settings(AXES_ENABLED=False)
class IPRestrictionMiddlewareTest(TestCase):
    """IP 제한 미들웨어 테스트"""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='ipmid_admin', password='testpass123', role='admin',
        )
        self.staff = User.objects.create_user(
            username='ipmid_staff', password='testpass123', role='staff',
        )

    def test_no_whitelist_allows_all(self):
        """화이트리스트가 비어있으면 모든 IP 허용"""
        self.client.login(username='ipmid_staff', password='testpass123')
        response = self.client.get(reverse('core:dashboard'))
        self.assertNotEqual(response.status_code, 403)

    def test_whitelist_blocks_unlisted_ip(self):
        """ALL 화이트리스트에 IP가 없으면 차단"""
        from apps.accounts.models import IPWhitelist
        # 다른 IP만 허용
        IPWhitelist.objects.create(ip_address='10.99.99.99', scope='ALL')
        self.client.login(username='ipmid_staff', password='testpass123')
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_whitelist_allows_listed_ip(self):
        """ALL 화이트리스트에 IP가 있으면 허용"""
        from apps.accounts.models import IPWhitelist
        # 테스트 클라이언트의 기본 IP는 127.0.0.1
        IPWhitelist.objects.create(ip_address='127.0.0.1', scope='ALL')
        self.client.login(username='ipmid_staff', password='testpass123')
        response = self.client.get(reverse('core:dashboard'))
        self.assertNotEqual(response.status_code, 403)


# ═══════════════════════════════════════════════════
# 세션 동시 로그인 제한 테스트
# ═══════════════════════════════════════════════════

@override_settings(AXES_ENABLED=False)
class UserSessionModelTest(TestCase):
    """UserSession 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='sessionuser', password='testpass123', role='staff',
        )

    def test_session_created_on_login(self):
        """로그인 시 UserSession 레코드 생성"""
        from apps.accounts.models import UserSession
        self.client.login(username='sessionuser', password='testpass123')
        self.assertTrue(UserSession.objects.filter(user=self.user).exists())

    def test_session_removed_on_logout(self):
        """로그아웃 시 UserSession 비활성화"""
        from apps.accounts.models import UserSession
        self.client.login(username='sessionuser', password='testpass123')
        self.client.logout()
        active_sessions = UserSession.objects.filter(
            user=self.user, is_active=True,
        ).count()
        self.assertEqual(active_sessions, 0)

    def test_max_concurrent_sessions_enforced(self):
        """최대 동시 세션 수 초과 시 오래된 세션 삭제"""
        from apps.accounts.models import UserSession
        # 여러 클라이언트로 로그인하여 세션 생성
        for i in range(5):
            c = Client()
            c.login(username='sessionuser', password='testpass123')

        active_count = UserSession.objects.filter(
            user=self.user, is_active=True,
        ).count()
        # MAX_CONCURRENT_SESSIONS 기본값 3 이하여야 함
        self.assertLessEqual(active_count, 3)


@override_settings(AXES_ENABLED=False)
class ActiveSessionsViewTest(TestCase):
    """활성 세션 뷰 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='sessionview', password='testpass123', role='staff',
        )

    def test_active_sessions_view(self):
        """활성 세션 목록 페이지 접근"""
        self.client.login(username='sessionview', password='testpass123')
        response = self.client.get(reverse('accounts:active_sessions'))
        self.assertEqual(response.status_code, 200)

    def test_terminate_other_session(self):
        """다른 세션 강제 종료"""
        from apps.accounts.models import UserSession
        # 두 번째 세션 생성
        c2 = Client()
        c2.login(username='sessionview', password='testpass123')

        # 첫 번째 클라이언트로 로그인
        self.client.login(username='sessionview', password='testpass123')

        other_sessions = UserSession.objects.filter(
            user=self.user, is_active=True,
        ).exclude(session_key=self.client.session.session_key)

        if other_sessions.exists():
            other = other_sessions.first()
            response = self.client.post(
                reverse('accounts:terminate_session', kwargs={'pk': other.pk}),
            )
            self.assertEqual(response.status_code, 302)
            other.refresh_from_db()
            self.assertFalse(other.is_active)

    def test_terminate_all_sessions(self):
        """현재 세션 외 모든 세션 종료"""
        from apps.accounts.models import UserSession
        # 여러 세션 생성
        for _ in range(3):
            c = Client()
            c.login(username='sessionview', password='testpass123')

        self.client.login(username='sessionview', password='testpass123')
        response = self.client.post(reverse('accounts:terminate_all_sessions'))
        self.assertEqual(response.status_code, 302)

        active_count = UserSession.objects.filter(
            user=self.user, is_active=True,
        ).count()
        self.assertEqual(active_count, 1)  # 현재 세션만 남음


# ═══════════════════════════════════════════════════
# TOTP 2FA 테스트
# ═══════════════════════════════════════════════════

class TOTPTest(TestCase):
    """Pure Python TOTP 구현 테스트"""

    def test_generate_secret(self):
        """시크릿 키 생성"""
        from apps.accounts.totp import generate_secret
        secret = generate_secret()
        self.assertEqual(len(secret), 32)  # base32 encoded 20 bytes
        self.assertTrue(all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567=' for c in secret))

    def test_totp_generation(self):
        """TOTP 코드 생성"""
        from apps.accounts.totp import totp
        secret = 'JBSWY3DPEHPK3PXP'  # known test secret
        code = totp(secret, now=0)
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

    def test_totp_verification(self):
        """TOTP 코드 검증"""
        from apps.accounts.totp import generate_secret, totp, verify_totp
        secret = generate_secret()
        code = totp(secret)
        self.assertTrue(verify_totp(secret, code))

    def test_totp_wrong_code_rejected(self):
        """잘못된 코드는 거부"""
        from apps.accounts.totp import generate_secret, verify_totp
        secret = generate_secret()
        self.assertFalse(verify_totp(secret, '000000'))

    def test_totp_uri_generation(self):
        """OTP URI 생성"""
        from apps.accounts.totp import get_totp_uri
        uri = get_totp_uri('JBSWY3DPEHPK3PXP', 'testuser')
        self.assertTrue(uri.startswith('otpauth://totp/'))
        self.assertIn('JBSWY3DPEHPK3PXP', uri)
        self.assertIn('testuser', uri)
        self.assertIn('ERP+Suite', uri)

    def test_generate_backup_codes(self):
        """백업코드 생성"""
        from apps.accounts.totp import generate_backup_codes
        codes = generate_backup_codes(count=10, length=8)
        self.assertEqual(len(codes), 10)
        self.assertTrue(all(len(c) == 8 for c in codes))


class TOTPDeviceModelTest(TestCase):
    """TOTPDevice 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='totpuser', password='TestPass123!@#',
            name='TOTP유저', role='manager',
        )

    def test_totp_device_creation(self):
        """TOTP 장치 생성"""
        from apps.accounts.models import TOTPDevice
        from apps.accounts.totp import generate_secret
        device = TOTPDevice.objects.create(
            user=self.user,
            secret_key=generate_secret(),
        )
        self.assertFalse(device.is_verified)
        self.assertEqual(device.backup_codes, [])

    def test_totp_device_str(self):
        """TOTP 장치 __str__"""
        from apps.accounts.models import TOTPDevice
        device = TOTPDevice.objects.create(
            user=self.user,
            secret_key='TESTKEY12345678901',
        )
        self.assertIn('미인증', str(device))
        device.is_verified = True
        device.save()
        self.assertIn('인증됨', str(device))

    def test_backup_code_verification(self):
        """백업코드 사용 — 일회용"""
        from apps.accounts.models import TOTPDevice
        device = TOTPDevice.objects.create(
            user=self.user,
            secret_key='TESTKEY12345678901',
            backup_codes=['abc12345', 'def67890'],
            is_verified=True,
        )
        self.assertTrue(device.verify_backup_code('abc12345'))
        self.assertFalse(device.verify_backup_code('abc12345'))  # already used
        device.refresh_from_db()
        self.assertEqual(len(device.backup_codes), 1)

    def test_backup_code_invalid(self):
        """잘못된 백업코드 거부"""
        from apps.accounts.models import TOTPDevice
        device = TOTPDevice.objects.create(
            user=self.user,
            secret_key='TESTKEY12345678901',
            backup_codes=['abc12345'],
            is_verified=True,
        )
        self.assertFalse(device.verify_backup_code('wrong'))


class TwoFactorViewTest(TestCase):
    """2FA 뷰 테스트"""

    def setUp(self):
        self.manager = User.objects.create_user(
            username='twofamanager', password='TestPass123!@#',
            name='2FA매니저', role='manager',
        )
        self.staff = User.objects.create_user(
            username='twofastaff', password='TestPass123!@#',
            name='2FA직원', role='staff',
        )

    def test_setup_page_accessible(self):
        """2FA 설정 페이지 접근 가능"""
        self.client.force_login(self.manager)
        response = self.client.get(reverse('accounts:two_factor_setup'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '비밀키')

    def test_setup_creates_device(self):
        """2FA 설정 시 TOTPDevice 생성"""
        from apps.accounts.models import TOTPDevice
        self.client.force_login(self.manager)
        self.client.get(reverse('accounts:two_factor_setup'))
        self.assertTrue(
            TOTPDevice.all_objects.filter(user=self.manager).exists()
        )

    def test_setup_verify_correct_code(self):
        """올바른 코드로 2FA 설정 완료"""
        from apps.accounts.models import TOTPDevice
        from apps.accounts.totp import generate_secret, totp
        self.client.force_login(self.manager)
        # Create device manually with known secret
        secret = generate_secret()
        TOTPDevice.objects.create(
            user=self.manager, secret_key=secret, is_verified=False,
        )
        code = totp(secret)
        response = self.client.post(reverse('accounts:two_factor_setup'), {'code': code})
        self.assertEqual(response.status_code, 302)
        device = TOTPDevice.objects.get(user=self.manager)
        self.assertTrue(device.is_verified)
        self.assertTrue(len(device.backup_codes) > 0)

    def test_setup_wrong_code_rejected(self):
        """잘못된 코드는 거부"""
        from apps.accounts.models import TOTPDevice
        self.client.force_login(self.manager)
        TOTPDevice.objects.create(
            user=self.manager, secret_key='TESTKEY12345678901', is_verified=False,
        )
        response = self.client.post(reverse('accounts:two_factor_setup'), {'code': '000000'})
        self.assertEqual(response.status_code, 302)
        device = TOTPDevice.objects.get(user=self.manager)
        self.assertFalse(device.is_verified)

    def test_verify_page(self):
        """2FA 검증 페이지 접근"""
        self.client.force_login(self.manager)
        response = self.client.get(reverse('accounts:two_factor_verify'))
        self.assertEqual(response.status_code, 200)

    def test_disable_2fa(self):
        """2FA 비활성화"""
        from apps.accounts.models import TOTPDevice
        self.client.force_login(self.manager)
        TOTPDevice.objects.create(
            user=self.manager, secret_key='TESTKEY12345678901',
            is_verified=True, backup_codes=['code1'],
        )
        response = self.client.post(reverse('accounts:two_factor_disable'))
        self.assertEqual(response.status_code, 302)
        device = TOTPDevice.all_objects.get(user=self.manager)
        self.assertFalse(device.is_verified)
        self.assertFalse(device.is_active)

    def test_backup_codes_view(self):
        """백업코드 조회 페이지"""
        from apps.accounts.models import TOTPDevice
        self.client.force_login(self.manager)
        TOTPDevice.objects.create(
            user=self.manager, secret_key='TESTKEY12345678901',
            is_verified=True, backup_codes=['abc12345', 'def67890'],
        )
        response = self.client.get(reverse('accounts:two_factor_backup_codes'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'abc12345')

    def test_regenerate_backup_codes(self):
        """백업코드 재발급"""
        from apps.accounts.models import TOTPDevice
        self.client.force_login(self.manager)
        TOTPDevice.objects.create(
            user=self.manager, secret_key='TESTKEY12345678901',
            is_verified=True, backup_codes=['old_code'],
        )
        response = self.client.post(reverse('accounts:two_factor_regenerate_backup'))
        self.assertEqual(response.status_code, 302)
        device = TOTPDevice.objects.get(user=self.manager)
        self.assertEqual(len(device.backup_codes), 10)
        self.assertNotIn('old_code', device.backup_codes)


class TwoFactorMiddlewareTest(TestCase):
    """2FA 미들웨어 테스트"""

    def setUp(self):
        self.manager = User.objects.create_user(
            username='mw_manager', password='TestPass123!@#',
            role='manager',
        )
        self.staff = User.objects.create_user(
            username='mw_staff', password='TestPass123!@#',
            role='staff',
        )

    def test_staff_not_redirected(self):
        """staff 역할은 2FA 미들웨어에 걸리지 않음"""
        self.client.force_login(self.staff)
        response = self.client.get(reverse('core:dashboard'))
        self.assertNotEqual(response.status_code, 302)

    def test_manager_without_device_not_redirected(self):
        """2FA 미설정 매니저는 리다이렉트 안 됨"""
        self.client.force_login(self.manager)
        response = self.client.get(reverse('core:dashboard'))
        # Should not redirect to 2FA verify
        if response.status_code == 302:
            self.assertNotIn('two-factor/verify', response.url)

    def test_manager_with_device_redirected(self):
        """2FA 설정된 매니저는 검증 페이지로 리다이렉트"""
        from apps.accounts.models import TOTPDevice
        from apps.accounts.totp import generate_secret
        TOTPDevice.objects.create(
            user=self.manager, secret_key=generate_secret(),
            is_verified=True,
        )
        self.client.force_login(self.manager)
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('two-factor/verify', response.url)

    def test_2fa_verified_session_passes(self):
        """세션에 2fa_verified 있으면 통과"""
        from apps.accounts.models import TOTPDevice
        from apps.accounts.totp import generate_secret
        TOTPDevice.objects.create(
            user=self.manager, secret_key=generate_secret(),
            is_verified=True,
        )
        self.client.force_login(self.manager)
        session = self.client.session
        session['2fa_verified'] = True
        session.save()
        response = self.client.get(reverse('core:dashboard'))
        self.assertNotEqual(response.status_code, 302)


# ═══════════════════════════════════════════════════
# 비밀번호 정책 테스트
# ═══════════════════════════════════════════════════

class PasswordValidatorTest(TestCase):
    """커스텀 비밀번호 검증 테스트"""

    def test_complexity_validator_requires_uppercase(self):
        """대문자 필수"""
        from django.core.exceptions import ValidationError
        from apps.accounts.validators import ComplexityValidator
        v = ComplexityValidator()
        with self.assertRaises(ValidationError):
            v.validate('abcdefgh1!')

    def test_complexity_validator_requires_lowercase(self):
        """소문자 필수"""
        from django.core.exceptions import ValidationError
        from apps.accounts.validators import ComplexityValidator
        v = ComplexityValidator()
        with self.assertRaises(ValidationError):
            v.validate('ABCDEFGH1!')

    def test_complexity_validator_requires_digit(self):
        """숫자 필수"""
        from django.core.exceptions import ValidationError
        from apps.accounts.validators import ComplexityValidator
        v = ComplexityValidator()
        with self.assertRaises(ValidationError):
            v.validate('Abcdefghij!')

    def test_complexity_validator_requires_special(self):
        """특수문자 필수"""
        from django.core.exceptions import ValidationError
        from apps.accounts.validators import ComplexityValidator
        v = ComplexityValidator()
        with self.assertRaises(ValidationError):
            v.validate('Abcdefgh1x')

    def test_complexity_validator_requires_min_length(self):
        """최소 10자"""
        from django.core.exceptions import ValidationError
        from apps.accounts.validators import ComplexityValidator
        v = ComplexityValidator()
        with self.assertRaises(ValidationError):
            v.validate('Abc1!xyz')

    def test_complexity_validator_accepts_valid(self):
        """유효한 비밀번호 통과"""
        from apps.accounts.validators import ComplexityValidator
        v = ComplexityValidator()
        v.validate('Abcdefgh1!')  # Should not raise

    def test_no_reuse_validator(self):
        """최근 5개 비밀번호 재사용 금지"""
        from django.core.exceptions import ValidationError
        from django.contrib.auth.hashers import make_password
        from apps.accounts.models import PasswordHistory
        from apps.accounts.validators import NoReuseValidator

        user = User.objects.create_user(
            username='reusetest', password='OldPass123!@#',
        )
        # Record old password in history
        PasswordHistory.objects.create(
            user=user,
            password_hash=make_password('OldPass123!@#'),
        )
        v = NoReuseValidator()
        with self.assertRaises(ValidationError):
            v.validate('OldPass123!@#', user=user)

    def test_no_reuse_validator_allows_different(self):
        """다른 비밀번호는 허용"""
        from django.contrib.auth.hashers import make_password
        from apps.accounts.models import PasswordHistory
        from apps.accounts.validators import NoReuseValidator

        user = User.objects.create_user(
            username='reusetest2', password='OldPass123!@#',
        )
        PasswordHistory.objects.create(
            user=user,
            password_hash=make_password('OldPass123!@#'),
        )
        v = NoReuseValidator()
        v.validate('NewDifferent9!@', user=user)  # Should not raise

    def test_no_reuse_validator_no_user(self):
        """사용자 없으면 통과"""
        from apps.accounts.validators import NoReuseValidator
        v = NoReuseValidator()
        v.validate('AnyPassword1!', user=None)  # Should not raise


class PasswordHistorySignalTest(TestCase):
    """비밀번호 변경 시 히스토리 기록 테스트"""

    def test_password_change_records_history(self):
        """비밀번호 변경 시 PasswordHistory 기록"""
        from apps.accounts.models import PasswordHistory
        user = User.objects.create_user(
            username='histtest', password='OldPass123!@#',
        )
        user.set_password('NewPass456!@#')
        user.save()
        count = PasswordHistory.objects.filter(user=user).count()
        self.assertGreaterEqual(count, 1)


# ═══════════════════════════════════════════════════
# PII 마스킹 템플릿 필터 테스트
# ═══════════════════════════════════════════════════

class PIIMaskingTest(TestCase):
    """PII 마스킹 필터 테스트"""

    def test_mask_ssn_with_dash(self):
        """주민번호 마스킹 (하이픈 포함)"""
        from apps.core.templatetags.pii_filters import mask_ssn
        self.assertEqual(mask_ssn('123456-1234567'), '123456-*******')

    def test_mask_ssn_without_dash(self):
        """주민번호 마스킹 (하이픈 없음)"""
        from apps.core.templatetags.pii_filters import mask_ssn
        self.assertEqual(mask_ssn('1234561234567'), '123456-*******')

    def test_mask_ssn_empty(self):
        """빈 값은 그대로"""
        from apps.core.templatetags.pii_filters import mask_ssn
        self.assertEqual(mask_ssn(''), '')
        self.assertIsNone(mask_ssn(None))

    def test_mask_account_with_dashes(self):
        """계좌번호 마스킹 (하이픈 포함)"""
        from apps.core.templatetags.pii_filters import mask_account
        result = mask_account('110-123-456789')
        self.assertTrue(result.endswith('6789'))
        self.assertIn('*', result)

    def test_mask_account_without_dashes(self):
        """계좌번호 마스킹 (하이픈 없음)"""
        from apps.core.templatetags.pii_filters import mask_account
        result = mask_account('110123456789')
        self.assertTrue(result.endswith('6789'))
        self.assertIn('*', result)

    def test_mask_phone(self):
        """전화번호 마스킹"""
        from apps.core.templatetags.pii_filters import mask_phone
        self.assertEqual(mask_phone('010-1234-5678'), '010-****-5678')

    def test_mask_phone_international(self):
        """국제 전화번호 마스킹"""
        from apps.core.templatetags.pii_filters import mask_phone
        result = mask_phone('+82-10-1234-5678')
        self.assertIn('+82', result)
        self.assertIn('5678', result)
        self.assertIn('****', result)

    def test_mask_email(self):
        """이메일 마스킹"""
        from apps.core.templatetags.pii_filters import mask_email
        result = mask_email('abcdef@example.com')
        self.assertTrue(result.startswith('ab'))
        self.assertIn('***', result)
        self.assertTrue(result.endswith('@example.com'))

    def test_mask_email_short_local(self):
        """짧은 이메일 마스킹"""
        from apps.core.templatetags.pii_filters import mask_email
        result = mask_email('ab@test.com')
        self.assertTrue(result.startswith('a'))
        self.assertTrue(result.endswith('@test.com'))

    def test_mask_name_korean(self):
        """한국 이름 마스킹"""
        from apps.core.templatetags.pii_filters import mask_name
        self.assertEqual(mask_name('홍길동'), '홍*동')

    def test_mask_name_two_chars(self):
        """2글자 이름 마스킹"""
        from apps.core.templatetags.pii_filters import mask_name
        self.assertEqual(mask_name('김철'), '김*')

    def test_mask_name_four_chars(self):
        """4글자 이름 마스킹"""
        from apps.core.templatetags.pii_filters import mask_name
        self.assertEqual(mask_name('남궁민수'), '남**수')

    def test_mask_name_empty(self):
        """빈 이름"""
        from apps.core.templatetags.pii_filters import mask_name
        self.assertEqual(mask_name(''), '')


# ═══════════════════════════════════════════════════
# Excel 감사 로그 테스트
# ═══════════════════════════════════════════════════

class ExcelDownloadLogTest(TestCase):
    """Excel 다운로드 감사 로그 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='exceluser', password='TestPass123!@#',
            name='Excel유저', role='manager',
        )

    def test_log_creation(self):
        """다운로드 로그 기록"""
        from apps.core.excel_audit import ExcelDownloadLog
        ExcelDownloadLog.log_download(
            user=self.user,
            view_name='TestExcelView',
            row_count=100,
            ip_address='127.0.0.1',
        )
        self.assertEqual(
            ExcelDownloadLog.objects.filter(user=self.user).count(), 1,
        )

    def test_log_str(self):
        """__str__ 출력"""
        from apps.core.excel_audit import ExcelDownloadLog
        log = ExcelDownloadLog.objects.create(
            user=self.user,
            view_name='TestView',
            row_count=50,
            ip_address='127.0.0.1',
        )
        self.assertIn('TestView', str(log))


class EmployeeMaskedPropertyTest(TestCase):
    """EmployeeProfile 마스킹 프로퍼티 테스트"""

    def test_masked_account_number(self):
        """계좌번호 마스킹 프로퍼티"""
        user = User.objects.create_user(
            username='emp_mask', password='TestPass123!@#',
            name='테스트', role='staff',
        )
        from apps.hr.models import EmployeeProfile
        from datetime import date
        emp = EmployeeProfile.objects.create(
            user=user,
            hire_date=date(2024, 1, 1),
            bank_name='국민은행',
            bank_account='110-123-456789',
        )
        masked = emp.masked_account_number
        self.assertTrue(masked.endswith('6789'))
        self.assertIn('*', masked)

    def test_masked_account_number_empty(self):
        """빈 계좌번호"""
        user = User.objects.create_user(
            username='emp_mask2', password='TestPass123!@#',
            name='테스트2', role='staff',
        )
        from apps.hr.models import EmployeeProfile
        from datetime import date
        emp = EmployeeProfile.objects.create(
            user=user,
            hire_date=date(2024, 1, 1),
            bank_account='',
        )
        self.assertEqual(emp.masked_account_number, '')
