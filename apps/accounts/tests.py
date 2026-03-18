from django.test import TestCase, Client
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
        """이름이 있으면 이름 반환"""
        self.assertEqual(str(self.user), '테스트유저')

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
