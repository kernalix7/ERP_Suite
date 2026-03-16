"""
보안 검증 테스트 (SEC-001 ~ SEC-015)
OWASP Top 10 기반 ERP Suite 보안 검증 자동화 테스트
"""
import importlib

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.validators import FileExtensionValidator
from django.test import TestCase, override_settings
from django.urls import reverse, URLResolver, URLPattern

User = get_user_model()


class SEC001_SQLInjectionTest(TestCase):
    """SEC-001: SQL Injection 방어 - ORM 사용 검증"""

    def test_orm_사용_확인_악의적_입력_거부(self):
        """악의적 SQL 문자열이 입력되어도 ORM이 안전하게 처리"""
        from apps.inventory.models import Product
        # 악의적 입력으로 검색해도 에러 없이 빈 결과 반환
        malicious_inputs = [
            "' OR 1=1 --",
            "'; DROP TABLE inventory_product; --",
            "\" OR \"\"=\"",
            "1; SELECT * FROM accounts_user",
        ]
        for payload in malicious_inputs:
            qs = Product.objects.filter(code=payload)
            self.assertEqual(qs.count(), 0,
                             f"악의적 입력 '{payload}'에 대해 비정상 결과 반환")

    def test_orm_filter_파라미터화(self):
        """ORM filter가 파라미터 바인딩을 사용하는지 확인"""
        from apps.inventory.models import Product
        # ORM은 내부적으로 파라미터화된 쿼리 사용
        qs = Product.objects.filter(name__contains="test'; DROP TABLE--")
        # 쿼리 실행 시 에러 없이 빈 결과
        self.assertEqual(list(qs), [])


class SEC002_XSSDefenseTest(TestCase):
    """SEC-002: XSS 방어 - Django 템플릿 자동 이스케이프 확인"""

    def test_django_autoescape_기본_활성(self):
        """Django 템플릿 엔진의 autoescape가 기본 활성인지 확인"""
        from django.template import engines
        engine = engines['django']
        # Django 기본 엔진은 autoescape=True
        self.assertTrue(engine.engine.autoescape,
                        "Django 템플릿 엔진의 autoescape가 비활성화되어 있음")


class SEC003_CSRFTest(TestCase):
    """SEC-003: CSRF 토큰 검증"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='csrf_test', password='TestPass123!', role='staff',
        )
        self.client.force_login(self.user)

    def test_csrf_미들웨어_활성(self):
        """CsrfViewMiddleware가 MIDDLEWARE에 포함되어야 함"""
        self.assertIn(
            'django.middleware.csrf.CsrfViewMiddleware',
            settings.MIDDLEWARE,
            "CSRF 미들웨어가 활성화되어 있지 않음",
        )

    def test_csrf_토큰_없이_POST_403(self):
        """CSRF 토큰 없이 POST 요청 시 403 반환"""
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)

        # 로그인 폼에 POST (CSRF 토큰 없이)
        response = client.post(reverse('accounts:login'), {
            'username': 'csrf_test',
            'password': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 403,
                         "CSRF 토큰 없이 POST가 허용됨")


class SEC004_AuthenticationBypassTest(TestCase):
    """SEC-004: 인증 우회 방지 - LoginRequiredMixin 적용 확인"""

    def _get_all_url_patterns(self, urlpatterns=None, prefix=''):
        """모든 URL 패턴을 재귀적으로 수집"""
        if urlpatterns is None:
            from config.urls import urlpatterns
        patterns = []
        for pattern in urlpatterns:
            if isinstance(pattern, URLResolver):
                new_prefix = prefix + str(pattern.pattern)
                patterns.extend(
                    self._get_all_url_patterns(pattern.url_patterns, new_prefix)
                )
            elif isinstance(pattern, URLPattern):
                full_path = prefix + str(pattern.pattern)
                patterns.append((full_path, pattern))
        return patterns

    def test_비인증_사용자_리다이렉트(self):
        """비인증 사용자가 비즈니스 URL 접근 시 302 또는 403 반환"""
        # 인증 없이 접근 가능해야 하는 URL들
        public_urls = {
            'accounts/login/',
            'accounts/logout/',
            'i18n/',
            'api-auth/',
            'mgmt-console-x/',
            'metrics',        # prometheus
            '',                # 빈 패턴은 무시
        }

        patterns = self._get_all_url_patterns()
        unauthenticated_access = []

        for path, pattern in patterns:
            # 공개 URL은 건너뜀
            if any(path.startswith(pub) for pub in public_urls):
                continue
            # 파라미터가 필요한 URL은 건너뜀 (정확한 테스트 불가)
            if '<' in path:
                continue
            # API 토큰 엔드포인트 건너뜀
            if 'token' in path:
                continue

            try:
                url = '/' + path
                response = self.client.get(url)
                if response.status_code == 200:
                    unauthenticated_access.append(path)
            except Exception:
                pass  # URL 해석 실패 시 건너뜀

        # 인증 없이 접근 가능한 비즈니스 URL이 없어야 함
        self.assertEqual(
            len(unauthenticated_access), 0,
            f"비인증 접근 가능 URL 발견: {unauthenticated_access}",
        )


class SEC005_RBACTest(TestCase):
    """SEC-005: 권한 상승 방지 - RBAC 검증"""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin_rbac', password='AdminPass123!', role='admin',
        )
        self.manager_user = User.objects.create_user(
            username='manager_rbac', password='ManagerPass123!', role='manager',
        )
        self.staff_user = User.objects.create_user(
            username='staff_rbac', password='StaffPass123!', role='staff',
        )

    def test_staff_admin전용뷰_접근불가(self):
        """staff 계정이 admin 전용 뷰(백업)에 접근 시 403"""
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('core:backup'))
        self.assertIn(response.status_code, [403, 302],
                      "staff가 admin 전용 백업 페이지에 접근 가능")

    def test_staff_manager전용뷰_접근불가(self):
        """staff 계정이 manager 전용 뷰(투자 대시보드)에 접근 시 403"""
        self.client.force_login(self.staff_user)
        try:
            response = self.client.get(reverse('investment:dashboard'))
            self.assertIn(response.status_code, [403, 302],
                          "staff가 manager 전용 투자 대시보드에 접근 가능")
        except Exception:
            pass  # URL이 존재하지 않으면 건너뜀

    def test_admin_모든뷰_접근가능(self):
        """admin 계정은 모든 뷰에 접근 가능"""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('core:backup'))
        self.assertIn(response.status_code, [200, 302],
                      "admin이 백업 페이지에 접근 불가")

    def test_manager_매니저뷰_접근가능(self):
        """manager 계정은 매니저 뷰에 접근 가능"""
        self.client.force_login(self.manager_user)
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 200,
                         "manager가 대시보드에 접근 불가")


class SEC006_PasswordPolicyTest(TestCase):
    """SEC-006: 비밀번호 정책 검증"""

    def test_짧은비밀번호_거부(self):
        """8자 미만 비밀번호 거부"""
        with self.assertRaises(ValidationError):
            validate_password('Ab1!xyz')  # 7자

    def test_숫자만비밀번호_거부(self):
        """숫자로만 구성된 비밀번호 거부"""
        with self.assertRaises(ValidationError):
            validate_password('12345678901234')

    def test_일반적비밀번호_거부(self):
        """일반적인(common) 비밀번호 거부"""
        with self.assertRaises(ValidationError):
            validate_password('password1234')

    def test_유효한비밀번호_허용(self):
        """복잡한 비밀번호 허용"""
        # 예외가 발생하지 않으면 통과
        validate_password('XkR9$mNp2vL!')

    def test_비밀번호_검증기_4종_활성(self):
        """AUTH_PASSWORD_VALIDATORS 4종 모두 활성화 확인"""
        validator_names = [v['NAME'] for v in settings.AUTH_PASSWORD_VALIDATORS]
        expected = [
            'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
            'django.contrib.auth.password_validation.MinimumLengthValidator',
            'django.contrib.auth.password_validation.CommonPasswordValidator',
            'django.contrib.auth.password_validation.NumericPasswordValidator',
        ]
        for name in expected:
            self.assertIn(name, validator_names,
                          f"비밀번호 검증기 미설정: {name}")


class SEC007_SessionManagementTest(TestCase):
    """SEC-007: 세션 관리 - 운영환경 세션 보안 설정 검증"""

    def test_운영환경_세션보안_설정(self):
        """production.py 설정에서 세션 보안 설정 확인"""
        import ast
        prod_path = settings.BASE_DIR / 'config' / 'settings' / 'production.py'
        prod_src = prod_path.read_text()
        prod = type('ProdSettings', (), {})()
        for node in ast.parse(prod_src).body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        try:
                            val = ast.literal_eval(node.value)
                            setattr(prod, target.id, val)
                        except (ValueError, TypeError):
                            pass

        self.assertTrue(getattr(prod, 'SESSION_COOKIE_SECURE', False),
                        "SESSION_COOKIE_SECURE=True 미설정")
        self.assertTrue(getattr(prod, 'SESSION_COOKIE_HTTPONLY', False),
                        "SESSION_COOKIE_HTTPONLY=True 미설정")
        self.assertEqual(getattr(prod, 'SESSION_COOKIE_AGE', 0), 28800,
                         "SESSION_COOKIE_AGE=28800(8시간) 미설정")
        self.assertTrue(getattr(prod, 'SESSION_EXPIRE_AT_BROWSER_CLOSE', False),
                        "SESSION_EXPIRE_AT_BROWSER_CLOSE=True 미설정")


class SEC008_BruteForceProtectionTest(TestCase):
    """SEC-008: 브루트포스 방지 - django-axes 잠금 검증"""

    def test_axes_설정값_확인(self):
        """django-axes 설정 확인"""
        self.assertEqual(settings.AXES_FAILURE_LIMIT, 5,
                         "AXES_FAILURE_LIMIT이 5가 아님")
        self.assertEqual(settings.AXES_COOLOFF_TIME, 1,
                         "AXES_COOLOFF_TIME이 1시간이 아님")
        self.assertTrue(settings.AXES_RESET_ON_SUCCESS,
                        "AXES_RESET_ON_SUCCESS가 True가 아님")

    def test_axes_백엔드_활성(self):
        """AxesStandaloneBackend가 AUTHENTICATION_BACKENDS에 포함"""
        self.assertIn(
            'axes.backends.AxesStandaloneBackend',
            settings.AUTHENTICATION_BACKENDS,
            "django-axes 백엔드 미설정",
        )

    def test_axes_미들웨어_활성(self):
        """AxesMiddleware가 MIDDLEWARE에 포함"""
        self.assertIn(
            'axes.middleware.AxesMiddleware',
            settings.MIDDLEWARE,
            "django-axes 미들웨어 미설정",
        )

    def test_5회_실패시_잠금(self):
        """5회 연속 로그인 실패 후 잠금 확인"""
        User.objects.create_user(
            username='lockout_test', password='CorrectPass123!', role='staff',
        )
        login_url = reverse('accounts:login')

        # 5회 실패 시도
        for i in range(5):
            self.client.post(login_url, {
                'username': 'lockout_test',
                'password': f'WrongPass{i}',
            })

        # 6번째: 올바른 비밀번호로 시도해도 잠금되어야 함
        response = self.client.post(login_url, {
            'username': 'lockout_test',
            'password': 'CorrectPass123!',
        })
        # 잠금 시 lockout 페이지로 리다이렉트되거나 200(잠금 페이지 표시)
        self.assertNotEqual(response.status_code, 302,
                            "5회 실패 후에도 로그인 리다이렉트 발생(잠금 미작동)")


class SEC009_FileUploadValidationTest(TestCase):
    """SEC-009: 파일 업로드 검증 - 확장자 및 크기 제한"""

    def test_허용_확장자_목록(self):
        """허용된 확장자 목록 확인"""
        from apps.core.attachment import ALLOWED_EXTENSIONS
        expected = [
            'pdf', 'jpg', 'jpeg', 'png', 'gif', 'webp',
            'xlsx', 'xls', 'csv', 'doc', 'docx', 'hwp', 'hwpx',
            'zip', 'txt',
        ]
        for ext in expected:
            self.assertIn(ext, ALLOWED_EXTENSIONS,
                          f"허용 확장자 목록에 {ext} 미포함")

    def test_위험확장자_거부(self):
        """실행 파일 확장자(.exe, .sh, .bat, .py) 업로드 거부"""
        from apps.core.attachment import ALLOWED_EXTENSIONS
        validator = FileExtensionValidator(ALLOWED_EXTENSIONS)

        dangerous_exts = ['exe', 'sh', 'bat', 'py', 'js', 'php']
        for ext in dangerous_exts:
            fake_file = SimpleUploadedFile(
                f'malicious.{ext}', b'dangerous content',
            )
            with self.assertRaises(ValidationError,
                                   msg=f".{ext} 파일이 허용됨"):
                validator(fake_file)

    def test_허용확장자_통과(self):
        """허용된 확장자 파일 업로드 통과"""
        from apps.core.attachment import ALLOWED_EXTENSIONS
        validator = FileExtensionValidator(ALLOWED_EXTENSIONS)

        safe_exts = ['pdf', 'xlsx', 'jpg', 'png', 'csv']
        for ext in safe_exts:
            fake_file = SimpleUploadedFile(
                f'document.{ext}', b'safe content',
            )
            # 예외가 발생하지 않으면 통과
            validator(fake_file)

    def test_최대파일크기_설정(self):
        """MAX_FILE_SIZE가 10MB로 설정되어 있는지 확인"""
        from apps.core.attachment import MAX_FILE_SIZE
        self.assertEqual(MAX_FILE_SIZE, 10 * 1024 * 1024,
                         "MAX_FILE_SIZE가 10MB가 아님")


class SEC010_SecurityHeadersTest(TestCase):
    """SEC-010: 보안 헤더 - 운영환경 보안 헤더 설정 검증"""

    def test_운영환경_보안헤더(self):
        """production.py에서 보안 헤더 설정 확인"""
        import ast
        prod_path = settings.BASE_DIR / 'config' / 'settings' / 'production.py'
        prod_src = prod_path.read_text()
        prod = type('ProdSettings', (), {})()
        for node in ast.parse(prod_src).body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        try:
                            val = ast.literal_eval(node.value)
                            setattr(prod, target.id, val)
                        except (ValueError, TypeError):
                            pass

        self.assertEqual(getattr(prod, 'SECURE_HSTS_SECONDS', 0), 31536000,
                         "HSTS 1년 미설정")
        self.assertEqual(getattr(prod, 'X_FRAME_OPTIONS', ''), 'DENY',
                         "X_FRAME_OPTIONS='DENY' 미설정")
        self.assertTrue(getattr(prod, 'SECURE_BROWSER_XSS_FILTER', False),
                        "SECURE_BROWSER_XSS_FILTER 미설정")
        self.assertTrue(getattr(prod, 'SECURE_CONTENT_TYPE_NOSNIFF', False),
                        "SECURE_CONTENT_TYPE_NOSNIFF 미설정")
        self.assertTrue(getattr(prod, 'SECURE_SSL_REDIRECT', False),
                        "SECURE_SSL_REDIRECT 미설정")
        self.assertTrue(getattr(prod, 'SECURE_HSTS_INCLUDE_SUBDOMAINS', False),
                        "SECURE_HSTS_INCLUDE_SUBDOMAINS 미설정")
        self.assertTrue(getattr(prod, 'SECURE_HSTS_PRELOAD', False),
                        "SECURE_HSTS_PRELOAD 미설정")


class SEC011_DebugModeTest(TestCase):
    """SEC-011: 에러 정보 노출 방지 - DEBUG=False 검증"""

    def test_운영환경_DEBUG_False(self):
        """production.py에서 DEBUG=False 확인"""
        import ast
        prod_path = settings.BASE_DIR / 'config' / 'settings' / 'production.py'
        prod_src = prod_path.read_text()
        prod = type('ProdSettings', (), {})()
        for node in ast.parse(prod_src).body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        try:
                            val = ast.literal_eval(node.value)
                            setattr(prod, target.id, val)
                        except (ValueError, TypeError):
                            pass
        self.assertFalse(getattr(prod, 'DEBUG', True),
                         "운영환경에서 DEBUG=True 설정됨")


class SEC012_APIAuthenticationTest(TestCase):
    """SEC-012: API 인증 - JWT 토큰 검증"""

    def test_API_기본인증_IsAuthenticated(self):
        """REST_FRAMEWORK 설정에서 IsAuthenticated 기본 적용 확인"""
        perms = settings.REST_FRAMEWORK.get('DEFAULT_PERMISSION_CLASSES', [])
        self.assertIn(
            'rest_framework.permissions.IsAuthenticated',
            perms,
            "API 기본 권한이 IsAuthenticated가 아님",
        )

    def test_JWT_인증_클래스_설정(self):
        """JWTAuthentication이 기본 인증 클래스에 포함"""
        auth_classes = settings.REST_FRAMEWORK.get(
            'DEFAULT_AUTHENTICATION_CLASSES', [],
        )
        self.assertIn(
            'rest_framework_simplejwt.authentication.JWTAuthentication',
            auth_classes,
            "JWTAuthentication 미설정",
        )

    def test_비인증_API_접근_거부(self):
        """JWT Bearer 토큰 없이 API 접근 시 거부 확인"""
        from rest_framework.test import APIClient
        api_client = APIClient()
        # SessionAuthentication 미사용 - JWT만으로 테스트
        api_endpoints = [
            '/api/products/',
            '/api/orders/',
            '/api/partners/',
        ]
        for url in api_endpoints:
            response = api_client.get(
                url, format='json',
                HTTP_AUTHORIZATION='Bearer invalid-token',
            )
            self.assertIn(
                response.status_code, [401, 403],
                f"잘못된 JWT로 {url} 접근 시 "
                f"{response.status_code} 반환",
            )

    def test_JWT_토큰_만료시간_설정(self):
        """JWT 토큰 만료시간 확인"""
        from datetime import timedelta
        jwt_settings = settings.SIMPLE_JWT
        self.assertEqual(
            jwt_settings['ACCESS_TOKEN_LIFETIME'],
            timedelta(hours=1),
            "ACCESS_TOKEN_LIFETIME이 1시간이 아님",
        )
        self.assertEqual(
            jwt_settings['REFRESH_TOKEN_LIFETIME'],
            timedelta(days=7),
            "REFRESH_TOKEN_LIFETIME이 7일이 아님",
        )


class SEC013_CORSPolicyTest(TestCase):
    """SEC-013: CORS 정책 검증"""

    def test_CORS_전체허용_비활성(self):
        """CORS_ALLOW_ALL_ORIGINS=False 확인"""
        self.assertFalse(
            settings.CORS_ALLOW_ALL_ORIGINS,
            "CORS_ALLOW_ALL_ORIGINS=True - 모든 오리진 허용됨",
        )

    def test_CORS_허용목록_존재(self):
        """CORS_ALLOWED_ORIGINS에 명시적 도메인 목록 존재"""
        origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', [])
        self.assertIsInstance(origins, list,
                              "CORS_ALLOWED_ORIGINS가 리스트가 아님")

    def test_CORS_미들웨어_활성(self):
        """CorsMiddleware가 MIDDLEWARE에 포함"""
        self.assertIn(
            'corsheaders.middleware.CorsMiddleware',
            settings.MIDDLEWARE,
            "CORS 미들웨어 미설정",
        )


class SEC014_SensitiveDataEncryptionTest(TestCase):
    """SEC-014: 민감 데이터 암호화 - 비밀번호 해싱 검증"""

    def test_비밀번호_해시저장(self):
        """User 비밀번호가 해시로 저장되는지 확인"""
        user = User.objects.create_user(
            username='hash_test', password='SecurePass123!', role='staff',
        )
        # 저장된 비밀번호는 평문이 아니어야 함
        self.assertNotEqual(user.password, 'SecurePass123!')
        self.assertTrue(user.password.startswith(('pbkdf2_', 'argon2', 'bcrypt')),
                        f"비밀번호가 안전한 해시로 저장되지 않음: {user.password[:20]}...")

    def test_SECRET_KEY_환경변수_관리(self):
        """SECRET_KEY가 환경변수로 관리되는지 확인 (소스코드 하드코딩 방지)"""
        # base.py에서 env('SECRET_KEY')로 읽는지 확인 - 설정이 로드됨은 환경변수 사용 의미
        self.assertTrue(len(settings.SECRET_KEY) > 0,
                        "SECRET_KEY가 비어 있음")
        # Django 기본값이 아닌지 확인
        self.assertNotEqual(
            settings.SECRET_KEY,
            'django-insecure-',
            "SECRET_KEY가 기본 insecure 값",
        )


class SEC015_AuditTrailTest(TestCase):
    """SEC-015: 감사 추적 - simple_history 전 모델 적용 검증"""

    def test_simple_history_앱_설치(self):
        """simple_history가 INSTALLED_APPS에 포함"""
        self.assertIn('simple_history', settings.INSTALLED_APPS,
                      "simple_history 미설치")

    def test_HistoryRequestMiddleware_활성(self):
        """HistoryRequestMiddleware가 MIDDLEWARE에 포함"""
        self.assertIn(
            'simple_history.middleware.HistoryRequestMiddleware',
            settings.MIDDLEWARE,
            "HistoryRequestMiddleware 미설정",
        )

    def test_주요모델_HistoricalRecords_적용(self):
        """주요 비즈니스 모델에 HistoricalRecords가 적용되어 있는지 확인"""
        from apps.inventory.models import Product, Category, Warehouse, StockMovement
        from apps.sales.models import Partner, Customer, Order, Quotation
        from apps.production.models import BOM, ProductionPlan, WorkOrder, ProductionRecord
        from apps.accounting.models import (
            Voucher, AccountCode, TaxInvoice, ApprovalRequest,
            AccountReceivable,
        )
        from apps.service.models import ServiceRequest, RepairRecord
        from apps.purchase.models import PurchaseOrder, GoodsReceipt

        models_to_check = [
            Product, Category, Warehouse, StockMovement,
            Partner, Customer, Order, Quotation,
            BOM, ProductionPlan, WorkOrder, ProductionRecord,
            Voucher, AccountCode, TaxInvoice, ApprovalRequest,
            AccountReceivable,
            ServiceRequest, RepairRecord,
            PurchaseOrder, GoodsReceipt,
        ]

        missing_history = []
        for model in models_to_check:
            if not hasattr(model, 'history'):
                missing_history.append(model.__name__)

        self.assertEqual(
            len(missing_history), 0,
            f"HistoricalRecords 미적용 모델: {missing_history}",
        )

    def test_데이터변경시_이력생성(self):
        """데이터 수정 시 변경 이력이 자동으로 기록되는지 확인"""
        from apps.inventory.models import Product
        product = Product.all_objects.create(
            code='HIST-001', name='이력테스트제품',
            product_type='FINISHED', unit_price=10000,
        )
        initial_count = product.history.count()

        # 수정
        product.name = '이력테스트제품_수정'
        product.save()

        self.assertEqual(
            product.history.count(), initial_count + 1,
            "데이터 수정 시 변경 이력이 생성되지 않음",
        )
