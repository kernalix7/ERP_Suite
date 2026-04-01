from django.test import TestCase, Client, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.core.notification import Notification, create_notification
from apps.core.attachment import Attachment, ALLOWED_EXTENSIONS, MAX_FILE_SIZE
from apps.core.middleware import AccessLogMiddleware
from apps.core.system_config import SystemConfig
from apps.core.audit import AuditAccessLog, AuditDashboardView, AuditExcelExportView
from apps.inventory.models import Product, Warehouse, StockCount

User = get_user_model()


class BaseModelSoftDeleteTest(TestCase):
    """BaseModel soft delete 및 ActiveManager 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='coreuser', password='testpass123', role='staff',
        )
        self.product = Product.objects.create(
            code='CORE-001', name='Soft Delete 테스트 제품',
            product_type='FINISHED', unit_price=1000, cost_price=500,
            created_by=self.user,
        )

    def test_soft_delete(self):
        """soft_delete() 호출 시 is_active=False로 변경"""
        self.assertTrue(self.product.is_active)
        self.product.soft_delete()
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_active)

    def test_active_manager_excludes_soft_deleted(self):
        """ActiveManager(objects)는 soft delete된 객체를 제외"""
        self.product.soft_delete()
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())

    def test_all_objects_includes_soft_deleted(self):
        """all_objects는 soft delete된 객체도 포함"""
        self.product.soft_delete()
        self.assertTrue(
            Product.all_objects.filter(pk=self.product.pk).exists()
        )

    def test_soft_delete_preserves_data(self):
        """soft delete 후 데이터가 그대로 보존"""
        original_name = self.product.name
        self.product.soft_delete()
        restored = Product.all_objects.get(pk=self.product.pk)
        self.assertEqual(restored.name, original_name)

    def test_base_model_timestamps(self):
        """created_at, updated_at이 자동 설정"""
        self.assertIsNotNone(self.product.created_at)
        self.assertIsNotNone(self.product.updated_at)

    def test_base_model_created_by(self):
        """created_by FK가 정상 저장"""
        self.assertEqual(self.product.created_by, self.user)

    def test_base_model_notes(self):
        """notes 필드 테스트"""
        self.product.notes = '비고 테스트'
        self.product.save()
        self.product.refresh_from_db()
        self.assertEqual(self.product.notes, '비고 테스트')

    def test_multiple_soft_deletes_and_active_count(self):
        """여러 객체 soft delete 후 ActiveManager 카운트 확인"""
        p2 = Product.objects.create(
            code='CORE-002', name='제품2', product_type='RAW',
            unit_price=500, cost_price=200, created_by=self.user,
        )
        Product.objects.create(
            code='CORE-003', name='제품3', product_type='SEMI',
            unit_price=800, cost_price=400, created_by=self.user,
        )
        initial_count = Product.objects.count()
        self.product.soft_delete()
        p2.soft_delete()
        self.assertEqual(Product.objects.count(), initial_count - 2)
        self.assertEqual(Product.all_objects.count(), initial_count)


class NotificationModelTest(TestCase):
    """Notification 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='notiuser', password='testpass123', role='staff',
            name='알림유저',
        )

    def test_notification_creation(self):
        """알림 생성"""
        noti = Notification.objects.create(
            user=self.user,
            title='테스트 알림',
            message='알림 내용입니다.',
            noti_type=Notification.NotiType.SYSTEM,
        )
        self.assertEqual(noti.title, '테스트 알림')
        self.assertEqual(noti.user, self.user)
        self.assertFalse(noti.is_read)

    def test_notification_str(self):
        """알림 문자열 표현"""
        noti = Notification.objects.create(
            user=self.user,
            title='문자열 테스트',
            message='test',
        )
        self.assertEqual(str(noti), '문자열 테스트')

    def test_notification_types(self):
        """알림 유형 선택지 확인"""
        types = dict(Notification.NotiType.choices)
        self.assertIn('STOCK_LOW', types)
        self.assertIn('ORDER_NEW', types)
        self.assertIn('SYSTEM', types)

    def test_notification_read_toggle(self):
        """알림 읽음 처리"""
        noti = Notification.objects.create(
            user=self.user, title='읽음 테스트', message='test',
        )
        self.assertFalse(noti.is_read)
        noti.is_read = True
        noti.save()
        noti.refresh_from_db()
        self.assertTrue(noti.is_read)

    def test_notification_ordering(self):
        """알림은 최신순 정렬"""
        Notification.objects.create(
            user=self.user, title='첫번째', message='1',
        )
        Notification.objects.create(
            user=self.user, title='두번째', message='2',
        )
        notis = list(Notification.objects.filter(user=self.user))
        self.assertEqual(notis[0].title, '두번째')
        self.assertEqual(notis[1].title, '첫번째')


class CreateNotificationFunctionTest(TestCase):
    """create_notification 함수 테스트"""

    def setUp(self):
        self.user1 = User.objects.create_user(
            username='user1', password='testpass123',
            role='staff', name='유저1',
        )
        self.user2 = User.objects.create_user(
            username='user2', password='testpass123',
            role='manager', name='유저2',
        )

    def test_create_notification_for_queryset(self):
        """QuerySet 사용자에게 알림 생성"""
        users = User.objects.filter(pk__in=[self.user1.pk, self.user2.pk])
        create_notification(
            users=users,
            title='일괄 알림',
            message='일괄 알림 내용',
            noti_type='SYSTEM',
        )
        self.assertEqual(Notification.objects.filter(title='일괄 알림').count(), 2)

    def test_create_notification_for_all(self):
        """'all' 문자열로 전체 사용자에게 알림 생성"""
        create_notification(
            users='all',
            title='전체 알림',
            message='전체 알림 내용',
        )
        count = User.objects.filter(is_active=True).count()
        noti_count = Notification.objects.filter(
            title='전체 알림',
        ).count()
        self.assertEqual(noti_count, count)


class AttachmentModelTest(TestCase):
    """Attachment 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='attachuser', password='testpass123', role='staff',
        )
        self.product = Product.objects.create(
            code='ATT-001', name='첨부 테스트 제품',
            product_type='FINISHED', unit_price=1000, cost_price=500,
            created_by=self.user,
        )

    def test_attachment_str(self):
        """Attachment 문자열 표현"""
        ct = ContentType.objects.get_for_model(self.product)
        att = Attachment.objects.create(
            content_type=ct,
            object_id=self.product.pk,
            file='test.pdf',
            original_filename='보고서.pdf',
            file_size=1024,
            doc_type=Attachment.DocType.REPORT,
            uploaded_by=self.user,
        )
        self.assertEqual(str(att), '보고서.pdf (보고서)')

    def test_file_size_display_bytes(self):
        """파일 크기 표시 (바이트)"""
        att = Attachment(file_size=500)
        self.assertEqual(att.file_size_display, '500 B')

    def test_file_size_display_kb(self):
        """파일 크기 표시 (KB)"""
        att = Attachment(file_size=2048)
        self.assertEqual(att.file_size_display, '2.0 KB')

    def test_file_size_display_mb(self):
        """파일 크기 표시 (MB)"""
        att = Attachment(file_size=2 * 1024 * 1024)
        self.assertEqual(att.file_size_display, '2.0 MB')

    def test_is_image_true(self):
        """이미지 파일 확인"""
        att = Attachment(original_filename='photo.jpg')
        self.assertTrue(att.is_image)
        att2 = Attachment(original_filename='image.png')
        self.assertTrue(att2.is_image)

    def test_is_image_false(self):
        """비이미지 파일 확인"""
        att = Attachment(original_filename='document.pdf')
        self.assertFalse(att.is_image)

    def test_allowed_extensions(self):
        """허용 확장자 목록 확인"""
        self.assertIn('pdf', ALLOWED_EXTENSIONS)
        self.assertIn('xlsx', ALLOWED_EXTENSIONS)
        self.assertIn('jpg', ALLOWED_EXTENSIONS)

    def test_max_file_size(self):
        """최대 파일 크기 10MB 확인"""
        self.assertEqual(MAX_FILE_SIZE, 10 * 1024 * 1024)


class AccessLogMiddlewareTest(TestCase):
    """AccessLogMiddleware 테스트"""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = AccessLogMiddleware(lambda req: None)
        self.user = User.objects.create_user(
            username='loguser', password='testpass123', role='staff',
        )

    def test_process_request_sets_start_time(self):
        """process_request가 _access_start를 설정"""
        request = self.factory.get('/test/')
        self.middleware.process_request(request)
        self.assertTrue(hasattr(request, '_access_start'))

    def test_static_paths_excluded(self):
        """정적 파일 경로는 로깅 제외"""
        excluded = AccessLogMiddleware.EXCLUDE_PREFIXES
        self.assertIn('/static/', excluded)
        self.assertIn('/media/', excluded)
        self.assertIn('/favicon.ico', excluded)


class MixinAccessTest(TestCase):
    """AdminRequiredMixin, ManagerRequiredMixin 접근 제어 테스트"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='mixin_admin', password='testpass123', role='admin',
        )
        self.manager = User.objects.create_user(
            username='mixin_manager', password='testpass123', role='manager',
        )
        self.staff = User.objects.create_user(
            username='mixin_staff', password='testpass123', role='staff',
        )

    def test_admin_mixin_allows_admin(self):
        """AdminRequiredMixin은 admin 허용"""
        self.client.force_login(User.objects.get(username='mixin_admin'))
        response = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(response.status_code, 200)

    def test_admin_mixin_blocks_manager(self):
        """AdminRequiredMixin은 manager 차단"""
        self.client.force_login(User.objects.get(username='mixin_manager'))
        response = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(response.status_code, 403)

    def test_admin_mixin_blocks_staff(self):
        """AdminRequiredMixin은 staff 차단"""
        self.client.force_login(User.objects.get(username='mixin_staff'))
        response = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(response.status_code, 403)


class SystemConfigModelTest(TestCase):
    """SystemConfig 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='configuser', password='testpass123', role='admin',
        )
        self.config = SystemConfig.objects.create(
            category='NTS',
            key='api_key',
            value='test-secret-key',
            display_name='국세청 API 키',
            description='홈택스 API 인증 키',
            is_secret=True,
            value_type='password',
            created_by=self.user,
        )

    def test_creation(self):
        """SystemConfig 생성"""
        self.assertEqual(self.config.category, 'NTS')
        self.assertEqual(self.config.key, 'api_key')
        self.assertEqual(self.config.display_name, '국세청 API 키')
        self.assertTrue(self.config.is_secret)

    def test_str(self):
        """문자열 표현"""
        self.assertEqual(str(self.config), '[국세청 API] 국세청 API 키')

    def test_masked_value_secret(self):
        """민감정보 마스킹"""
        self.assertEqual(self.config.masked_value, '********')

    def test_masked_value_non_secret(self):
        """비민감정보는 원본 표시"""
        config = SystemConfig.objects.create(
            category='GENERAL', key='company_name',
            value='테스트회사', display_name='회사명',
            is_secret=False,
        )
        self.assertEqual(config.masked_value, '테스트회사')

    def test_encrypted_storage(self):
        """EncryptedCharField로 암호화 저장 확인"""
        # DB에서 직접 읽으면 암호화된 값이어야 함
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT value FROM core_systemconfig WHERE id = %s",
                [self.config.pk],
            )
            raw_value = cursor.fetchone()[0]
        # 암호화된 값은 원본과 다름
        self.assertNotEqual(raw_value, 'test-secret-key')
        # 모델을 통해 읽으면 복호화됨
        self.config.refresh_from_db()
        self.assertEqual(self.config.value, 'test-secret-key')

    def test_unique_together(self):
        """category + key 유니크 제약"""
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            SystemConfig.objects.create(
                category='NTS', key='api_key',
                value='duplicate', display_name='중복키',
            )

    def test_get_value_exists(self):
        """get_value 헬퍼 — 존재하는 키"""
        val = SystemConfig.get_value('NTS', 'api_key')
        self.assertEqual(val, 'test-secret-key')

    def test_get_value_missing(self):
        """get_value 헬퍼 — 없는 키"""
        val = SystemConfig.get_value('NTS', 'nonexistent', default='기본값')
        self.assertEqual(val, '기본값')

    def test_set_value_create(self):
        """set_value 헬퍼 — 새 키 생성"""
        config = SystemConfig.set_value(
            'EMAIL', 'smtp_host',
            value='smtp.example.com',
            display_name='SMTP 호스트',
            is_secret=False,
            value_type='text',
        )
        self.assertEqual(config.value, 'smtp.example.com')
        self.assertEqual(config.display_name, 'SMTP 호스트')

    def test_set_value_update(self):
        """set_value 헬퍼 — 기존 키 업데이트"""
        SystemConfig.set_value('NTS', 'api_key', value='new-key')
        self.config.refresh_from_db()
        self.assertEqual(self.config.value, 'new-key')

    def test_soft_delete(self):
        """soft delete"""
        self.config.soft_delete()
        self.assertFalse(
            SystemConfig.objects.filter(pk=self.config.pk).exists()
        )
        self.assertTrue(
            SystemConfig.all_objects.filter(pk=self.config.pk).exists()
        )

    def test_category_choices(self):
        """카테고리 선택지"""
        choices = dict(SystemConfig.Category.choices)
        self.assertIn('NTS', choices)
        self.assertIn('MARKETPLACE', choices)
        self.assertIn('EMAIL', choices)
        self.assertIn('GENERAL', choices)
        self.assertIn('COMPANY', choices)
        self.assertIn('HR', choices)
        self.assertIn('SECURITY', choices)
        self.assertIn('BACKUP', choices)
        self.assertIn('SHIPPING', choices)
        self.assertIn('AI', choices)
        self.assertIn('ADDRESS', choices)

    def test_initialize_defaults(self):
        """기본 설정값 초기화"""
        count = SystemConfig.initialize_defaults()
        self.assertGreater(count, 0)
        # 회사정보
        self.assertTrue(SystemConfig.objects.filter(category='COMPANY', key='company_name').exists())
        # 인사
        self.assertTrue(SystemConfig.objects.filter(category='HR', key='default_role').exists())
        # 보안
        self.assertTrue(SystemConfig.objects.filter(category='SECURITY', key='session_timeout').exists())
        # 백업
        self.assertTrue(SystemConfig.objects.filter(category='BACKUP', key='auto_backup_enabled').exists())
        # 주소검색 API
        self.assertTrue(SystemConfig.objects.filter(category='ADDRESS', key='JUSO_API_KEY').exists())
        # 택배/배송 API
        self.assertTrue(SystemConfig.objects.filter(category='SHIPPING', key='default_carrier_api_key').exists())
        self.assertTrue(SystemConfig.objects.filter(category='SHIPPING', key='tracking_api_url').exists())
        # AI/자동화
        self.assertTrue(SystemConfig.objects.filter(category='AI', key='anthropic_api_key').exists())
        self.assertTrue(SystemConfig.objects.filter(category='AI', key='auto_reply_enabled').exists())
        # 이메일
        self.assertTrue(SystemConfig.objects.filter(category='EMAIL', key='smtp_host').exists())
        self.assertTrue(SystemConfig.objects.filter(category='EMAIL', key='from_email').exists())
        # 마켓플레이스
        self.assertTrue(SystemConfig.objects.filter(category='MARKETPLACE', key='naver_client_id').exists())
        self.assertTrue(SystemConfig.objects.filter(category='MARKETPLACE', key='coupang_access_key').exists())
        # 국세청
        self.assertTrue(SystemConfig.objects.filter(category='NTS', key='api_key').exists())

    def test_initialize_defaults_idempotent(self):
        """기본 설정값 초기화 중복 실행 시 0 반환"""
        SystemConfig.initialize_defaults()
        second_count = SystemConfig.initialize_defaults()
        self.assertEqual(second_count, 0)

    def test_value_type_choices(self):
        """값 타입 선택지"""
        choices = dict(SystemConfig.ValueType.choices)
        self.assertIn('text', choices)
        self.assertIn('password', choices)
        self.assertIn('url', choices)
        self.assertIn('boolean', choices)

    def test_history_tracking(self):
        """HistoricalRecords 이력 추적"""
        self.config.value = 'updated-key'
        self.config.save()
        self.assertGreaterEqual(self.config.history.count(), 2)


class SystemSettingsViewTest(TestCase):
    """시스템 설정 뷰 테스트"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='settings_admin', password='testpass123', role='admin',
        )
        self.staff = User.objects.create_user(
            username='settings_staff', password='testpass123', role='staff',
        )
        self.url = reverse('core:system_settings')

    def test_admin_access(self):
        """관리자 접근 허용"""
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '시스템 설정')

    def test_staff_denied(self):
        """일반 직원 접근 거부"""
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_anonymous_redirect(self):
        """비로그인 리다이렉트"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_create_config(self):
        """설정 추가"""
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {
            'action': 'save',
            'category': 'GENERAL',
            'key': 'company_name',
            'value': '테스트회사',
            'display_name': '회사명',
            'description': '',
            'value_type': 'text',
            'tab': 'GENERAL',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            SystemConfig.objects.filter(
                category='GENERAL', key='company_name',
            ).exists()
        )

    def test_update_config(self):
        """설정 수정"""
        config = SystemConfig.objects.create(
            category='EMAIL', key='smtp_host',
            value='old.smtp.com', display_name='SMTP 호스트',
        )
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {
            'action': 'save',
            'config_id': config.pk,
            'category': 'EMAIL',
            'key': 'smtp_host',
            'value': 'new.smtp.com',
            'display_name': 'SMTP 호스트',
            'description': '',
            'value_type': 'text',
            'tab': 'EMAIL',
        })
        self.assertEqual(response.status_code, 302)
        config.refresh_from_db()
        self.assertEqual(config.value, 'new.smtp.com')

    def test_delete_config(self):
        """설정 삭제 (soft delete)"""
        config = SystemConfig.objects.create(
            category='GENERAL', key='test_key',
            value='test', display_name='테스트',
        )
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {
            'action': 'delete',
            'config_id': config.pk,
            'tab': 'GENERAL',
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            SystemConfig.objects.filter(pk=config.pk).exists()
        )

    def test_connection_test_email(self):
        """이메일 연결 테스트 (SMTP 미설정)"""
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('core:system_config_test'),
            {'category': 'EMAIL'},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])

    def test_connection_test_nts(self):
        """국세청 연결 테스트 안내"""
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('core:system_config_test'),
            {'category': 'NTS'},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

    def test_system_info_in_context(self):
        """시스템 상태 정보가 컨텍스트에 포함"""
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertIn('system_info', response.context)
        info = response.context['system_info']
        self.assertIn('django_version', info)
        self.assertIn('python_version', info)
        self.assertIn('db_size', info)
        self.assertIn('user_count', info)

    def test_defaults_initialized_on_view(self):
        """설정 페이지 접근 시 기본값 초기화"""
        self.client.force_login(self.admin)
        self.client.get(self.url)
        self.assertTrue(SystemConfig.objects.filter(category='COMPANY', key='company_name').exists())


class RoleSwitchViewTest(TestCase):
    """뷰 모드 전환 테스트"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='switch_admin', password='testpass123', role='admin',
        )
        self.staff = User.objects.create_user(
            username='switch_staff', password='testpass123', role='staff',
        )
        self.url = reverse('core:role_switch')

    def test_admin_switch_to_staff(self):
        """관리자가 사용자 뷰로 전환"""
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {'view_mode': 'staff'})
        self.assertEqual(response.status_code, 302)
        session = self.client.session
        self.assertEqual(session['view_mode'], 'staff')

    def test_admin_switch_to_manager(self):
        """관리자가 매니저 뷰로 전환"""
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {'view_mode': 'manager'})
        self.assertEqual(response.status_code, 302)
        session = self.client.session
        self.assertEqual(session['view_mode'], 'manager')

    def test_staff_cannot_switch(self):
        """일반 직원은 뷰 모드 전환 불가 (403)"""
        self.client.force_login(self.staff)
        response = self.client.post(self.url, {'view_mode': 'admin'})
        self.assertEqual(response.status_code, 403)

    def test_invalid_view_mode_ignored(self):
        """잘못된 뷰 모드 값은 무시"""
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {'view_mode': 'superuser'})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('view_mode', self.client.session)


class ContextProcessorTest(TestCase):
    """effective_role 컨텍스트 프로세서 테스트"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='ctx_admin', password='testpass123', role='admin',
        )
        self.staff = User.objects.create_user(
            username='ctx_staff', password='testpass123', role='staff',
        )

    def test_staff_effective_role(self):
        """일반 직원의 effective_role"""
        self.client.force_login(self.staff)
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.context['effective_role'], 'staff')
        self.assertFalse(response.context['is_view_mode_active'])

    def test_admin_default_role(self):
        """관리자 기본 effective_role"""
        self.client.force_login(self.admin)
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.context['effective_role'], 'admin')
        self.assertFalse(response.context['is_view_mode_active'])

    def test_admin_switched_role(self):
        """관리자 뷰 모드 전환 후 effective_role"""
        self.client.force_login(self.admin)
        self.client.post(reverse('core:role_switch'), {'view_mode': 'staff'})
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.context['effective_role'], 'staff')
        self.assertTrue(response.context['is_view_mode_active'])


class AuditAccessLogModelTest(TestCase):
    """AuditAccessLog 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='audit_user', password='testpass123',
            role='admin', is_auditor=True,
        )

    def test_create_audit_log(self):
        """감사 열람 기록 생성"""
        log = AuditAccessLog.objects.create(
            user=self.user,
            section=AuditAccessLog.Section.DASHBOARD,
            ip_address='127.0.0.1',
            user_agent='TestBrowser/1.0',
        )
        self.assertEqual(log.section, 'DASHBOARD')
        self.assertEqual(log.ip_address, '127.0.0.1')

    def test_str_representation(self):
        """문자열 표현"""
        log = AuditAccessLog.objects.create(
            user=self.user,
            section=AuditAccessLog.Section.ACCESS_LOG,
        )
        self.assertIn('시스템 접근 로그', str(log))

    def test_section_choices(self):
        """섹션 선택지"""
        choices = dict(AuditAccessLog.Section.choices)
        self.assertIn('DASHBOARD', choices)
        self.assertIn('ACCESS_LOG', choices)
        self.assertIn('DATA_CHANGE', choices)
        self.assertIn('LOGIN_HISTORY', choices)
        self.assertIn('AUDIT_LOG', choices)

    def test_ordering(self):
        """최신순 정렬"""
        AuditAccessLog.objects.create(
            user=self.user, section='DASHBOARD',
        )
        AuditAccessLog.objects.create(
            user=self.user, section='ACCESS_LOG',
        )
        logs = list(AuditAccessLog.objects.all())
        self.assertEqual(logs[0].section, 'ACCESS_LOG')


class AuditDashboardViewTest(TestCase):
    """감사 대시보드 뷰 테스트"""

    def setUp(self):
        self.client = Client()
        self.auditor = User.objects.create_user(
            username='auditor', password='testpass123',
            role='admin', is_auditor=True,
        )
        self.non_auditor = User.objects.create_user(
            username='non_auditor', password='testpass123',
            role='admin', is_auditor=False,
        )
        self.staff = User.objects.create_user(
            username='audit_staff', password='testpass123',
            role='staff', is_auditor=False,
        )
        self.url = reverse('core:audit_dashboard')

    def test_auditor_access(self):
        """감사권한 보유자 접근 허용"""
        self.client.force_login(self.auditor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_non_auditor_denied(self):
        """감사권한 미보유자 접근 거부"""
        self.client.force_login(self.non_auditor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_staff_denied(self):
        """일반 직원 접근 거부"""
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_anonymous_redirect(self):
        """비로그인 리다이렉트"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_audit_access_logged(self):
        """대시보드 접근 시 열람 기록 생성"""
        self.client.force_login(self.auditor)
        self.client.get(self.url)
        self.assertTrue(
            AuditAccessLog.objects.filter(
                user=self.auditor, section='DASHBOARD',
            ).exists()
        )

    def test_context_contains_isms_checks(self):
        """컨텍스트에 ISMS 진단 결과 포함"""
        self.client.force_login(self.auditor)
        response = self.client.get(self.url)
        self.assertIn('isms_checks', response.context)
        checks = response.context['isms_checks']
        self.assertEqual(len(checks), 6)
        for check in checks:
            self.assertIn('name', check)
            self.assertIn('passed', check)
            self.assertIn('details', check)

    def test_context_contains_approval_stats(self):
        """컨텍스트에 결재 현황 포함"""
        self.client.force_login(self.auditor)
        response = self.client.get(self.url)
        self.assertIn('approval_pending', response.context)
        self.assertIn('approval_approved', response.context)
        self.assertIn('approval_rejected', response.context)

    def test_context_contains_chart_data(self):
        """컨텍스트에 Chart.js 데이터 포함"""
        self.client.force_login(self.auditor)
        response = self.client.get(self.url)
        self.assertIn('chart_labels', response.context)
        self.assertIn('chart_access_data', response.context)
        self.assertIn('chart_change_data', response.context)
        self.assertIn('chart_login_success', response.context)
        self.assertIn('chart_login_fail', response.context)

    def test_context_contains_role_changes(self):
        """컨텍스트에 권한 변경 이력 포함"""
        self.client.force_login(self.auditor)
        response = self.client.get(self.url)
        self.assertIn('recent_role_changes', response.context)


class ISMSChecksTest(TestCase):
    """ISMS 자동 진단 테스트"""

    def setUp(self):
        User.objects.create_user(
            username='isms_auditor', password='testpass123',
            role='admin', is_auditor=True,
        )

    def test_isms_checks_count(self):
        """6개 진단 항목 확인"""
        checks = AuditDashboardView._run_isms_checks()
        self.assertEqual(len(checks), 6)

    def test_isms_check_names(self):
        """진단 항목 이름 확인"""
        checks = AuditDashboardView._run_isms_checks()
        names = [c['name'] for c in checks]
        self.assertIn('접근통제', names)
        self.assertIn('인증', names)
        self.assertIn('개인정보 보호', names)
        self.assertIn('감사 증적', names)
        self.assertIn('데이터 무결성', names)
        self.assertIn('암호화', names)

    def test_audit_trail_check_passes(self):
        """감사 증적 항목 — auditor 존재 시 통과"""
        checks = AuditDashboardView._run_isms_checks()
        audit_check = [c for c in checks if c['name'] == '감사 증적'][0]
        self.assertTrue(audit_check['passed'])

    def test_data_integrity_check(self):
        """데이터 무결성 — HistoricalRecords 10개 이상이면 통과"""
        checks = AuditDashboardView._run_isms_checks()
        integrity_check = [c for c in checks if c['name'] == '데이터 무결성'][0]
        self.assertTrue(integrity_check['passed'])


class AuditExcelExportViewTest(TestCase):
    """감사 증적 Excel 다운로드 테스트"""

    def setUp(self):
        self.client = Client()
        self.auditor = User.objects.create_user(
            username='excel_auditor', password='testpass123',
            role='admin', is_auditor=True,
        )
        self.non_auditor = User.objects.create_user(
            username='excel_non_auditor', password='testpass123',
            role='admin', is_auditor=False,
        )
        self.url = reverse('core:audit_export')

    def test_auditor_can_download(self):
        """감사권한 보유자 Excel 다운로드"""
        self.client.force_login(self.auditor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertIn('audit_report_', response['Content-Disposition'])

    def test_non_auditor_denied(self):
        """감사권한 미보유자 다운로드 거부"""
        self.client.force_login(self.non_auditor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_excel_has_content(self):
        """Excel 파일에 데이터 포함"""
        # 열람 기록 하나 생성
        AuditAccessLog.objects.create(
            user=self.auditor, section='DASHBOARD',
            ip_address='127.0.0.1',
        )
        self.client.force_login(self.auditor)
        response = self.client.get(self.url)
        self.assertGreater(len(response.content), 0)


class AddressSearchViewTest(TestCase):
    """주소검색 프록시 API 테스트"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='addr_user', password='testpass123', role='staff',
        )
        self.url = reverse('core:address_search')

    def test_login_required(self):
        """로그인 필요"""
        response = self.client.get(self.url, {'q': '세종로'})
        self.assertEqual(response.status_code, 302)

    def test_empty_query_returns_empty(self):
        """빈 쿼리 → 빈 결과"""
        self.client.force_login(self.user)
        response = self.client.get(self.url, {'q': ''})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['results'], [])
        self.assertFalse(data['error'])

    def test_short_query_returns_empty(self):
        """1글자 쿼리 → 빈 결과"""
        self.client.force_login(self.user)
        response = self.client.get(self.url, {'q': '가'})
        data = response.json()
        self.assertEqual(data['results'], [])

    def test_domestic_search_still_works_via_proxy(self):
        """국내 주소 프록시 검색 — API 키 미설정 시 에러"""
        self.client.force_login(self.user)
        response = self.client.get(self.url, {'q': '세종로', 'type': 'domestic'})
        data = response.json()
        self.assertTrue(data['error'])
        self.assertIn('API 키', data.get('message', ''))

    def test_international_search_type(self):
        """해외주소 검색 타입"""
        from unittest.mock import patch, MagicMock
        self.client.force_login(self.user)

        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {'display_name': '1600 Pennsylvania Ave, Washington DC', 'lat': '38.8', 'lon': '-77.0'},
        ]
        mock_resp.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp

        with patch('apps.core.api_utils.create_retry_session', return_value=mock_session):
            response = self.client.get(self.url, {'q': 'Pennsylvania Ave', 'type': 'international'})

        data = response.json()
        self.assertFalse(data['error'])
        self.assertGreaterEqual(len(data['results']), 1)


class JusoPopupViewTest(TestCase):
    """도로명주소 팝업 API 중간 페이지 테스트"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='juso_user', password='testpass123', role='staff',
        )
        self.url = reverse('core:juso_popup')

    def test_login_required(self):
        """미로그인 시 403"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_get_renders_popup(self):
        """GET 요청 시 confm_key 포함된 팝업 페이지 렌더링"""
        SystemConfig.set_value(
            'ADDRESS', 'JUSO_API_KEY', value='popup-test-key',
            display_name='도로명주소 API 키',
        )
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'popup-test-key')
        self.assertTemplateUsed(response, 'core/juso_popup.html')

    def test_post_callback(self):
        """POST with inputYn=Y 시 결과 전달 페이지 렌더링"""
        self.client.force_login(self.user)
        response = self.client.post(self.url, {
            'inputYn': 'Y',
            'roadFullAddr': '서울특별시 종로구 세종대로 209',
            'roadAddrPart1': '서울특별시 종로구 세종대로 209',
            'zipNo': '03154',
            'bdNm': '정부서울청사',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '서울특별시 종로구 세종대로 209')
        self.assertContains(response, '정부서울청사')

    def test_post_csrf_exempt(self):
        """POST 콜백은 CSRF 검증 없이 처리 (juso.go.kr에서 오는 요청)"""
        self.client.force_login(self.user)
        # enforce_csrf_checks=True로 클라이언트 생성하여 CSRF 토큰 없이도 통과하는지 확인
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        response = csrf_client.post(self.url, {
            'inputYn': 'Y',
            'roadFullAddr': '테스트 주소',
        })
        self.assertEqual(response.status_code, 200)


class DashboardAccountWidgetTest(TestCase):
    """대시보드 계좌 위젯 테스트"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='dash_user', password='testpass123', role='admin',
        )
        from apps.accounting.models import BankAccount
        self.BankAccount = BankAccount

    def test_dashboard_shows_flagged_accounts(self):
        """show_on_dashboard=True 계좌만 대시보드 context에 포함"""
        visible = self.BankAccount.objects.create(
            name='법인통장', account_type='BUSINESS',
            owner='테스트회사', bank='국민은행',
            balance=5000000, show_on_dashboard=True,
        )
        hidden = self.BankAccount.objects.create(
            name='숨긴통장', account_type='BUSINESS',
            owner='테스트회사', bank='신한은행',
            balance=3000000, show_on_dashboard=False,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse('core:dashboard'))
        accounts = response.context['dashboard_accounts']
        account_ids = [a.pk for a in accounts]
        self.assertIn(visible.pk, account_ids)
        self.assertNotIn(hidden.pk, account_ids)

    def test_dashboard_accounts_total(self):
        """대시보드 계좌 합계 계산"""
        self.BankAccount.objects.create(
            name='통장A', account_type='BUSINESS',
            owner='회사', balance=1000000, show_on_dashboard=True,
        )
        self.BankAccount.objects.create(
            name='통장B', account_type='PERSONAL',
            owner='대표', balance=2000000, show_on_dashboard=True,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.context['dashboard_accounts_total'], 3000000)

    def test_dashboard_no_accounts(self):
        """대시보드 표시 계좌 없으면 합계 0"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.context['dashboard_accounts_total'], 0)


class SystemConfigTestViewTest(TestCase):
    """SystemConfigTestView API 연결 테스트 뷰 테스트"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='testview_admin', password='testpass123', role='admin',
        )
        self.staff = User.objects.create_user(
            username='testview_staff', password='testpass123', role='staff',
        )
        self.url = reverse('core:system_config_test')

    def test_admin_only(self):
        """staff 접근 시 403"""
        self.client.force_login(self.staff)
        response = self.client.post(self.url, {'category': 'EMAIL'})
        self.assertEqual(response.status_code, 403)

    def test_email_no_host(self):
        """EMAIL 카테고리 — SMTP 호스트 미설정 시 에러"""
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {'category': 'EMAIL'})
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('SMTP', data['message'])

    def test_address_no_key(self):
        """ADDRESS 카테고리 — API 키 미설정 에러"""
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {'category': 'ADDRESS'})
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('API 키', data['message'])

    def test_address_with_key(self):
        """ADDRESS 카테고리 — 팝업 API 키 존재 확인"""
        SystemConfig.set_value(
            'ADDRESS', 'JUSO_API_KEY', value='test-popup-key',
            display_name='도로명주소 API 키',
        )
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {'category': 'ADDRESS'})
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('팝업 API 키 설정 확인', data['message'])

    def test_marketplace_no_keys(self):
        """MARKETPLACE 카테고리 — 키 없음 에러"""
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {'category': 'MARKETPLACE'})
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('마켓플레이스', data['message'])

    def test_marketplace_partial(self):
        """MARKETPLACE 카테고리 — 네이버만 설정 시 성공"""
        SystemConfig.set_value(
            'MARKETPLACE', 'naver_client_id', value='naver-id',
            display_name='네이버 Client ID',
        )
        SystemConfig.set_value(
            'MARKETPLACE', 'naver_client_secret', value='naver-secret',
            display_name='네이버 Client Secret',
        )
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {'category': 'MARKETPLACE'})
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('네이버', data['message'])

    def test_shipping_no_config(self):
        """SHIPPING 카테고리 — 미설정 에러"""
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {'category': 'SHIPPING'})
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('배송', data['message'])

    def test_ai_no_key(self):
        """AI 카테고리 — 키 없음 에러"""
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {'category': 'AI'})
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Anthropic', data['message'])

    def test_ai_with_key(self):
        """AI 카테고리 — 키 있음 성공 (ImportError fallback)"""
        from unittest.mock import patch
        SystemConfig.set_value(
            'AI', 'anthropic_api_key', value='sk-test-key',
            display_name='Anthropic API 키',
        )
        self.client.force_login(self.admin)

        with patch.dict('sys.modules', {'anthropic': None}):
            response = self.client.post(self.url, {'category': 'AI'})

        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('키 설정 확인', data['message'])

    def test_unsupported_category(self):
        """지원하지 않는 카테고리 에러"""
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {'category': 'UNKNOWN'})
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('지원되지 않습니다', data['message'])


class BusinessKeyFieldTest(TestCase):
    """BaseModel BUSINESS_KEY_FIELD soft_delete/restore 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='bkeyuser', password='testpass123', role='staff',
        )
        from datetime import date
        self.warehouse = Warehouse.objects.create(
            code='WH-BK', name='테스트창고', created_by=self.user,
        )
        self.sc = StockCount.objects.create(
            count_number='SC-TEST-001',
            warehouse=self.warehouse,
            count_date=date.today(),
            created_by=self.user,
        )

    def test_soft_delete_prefixes_business_key(self):
        """BUSINESS_KEY_FIELD가 있는 모델: soft_delete 시 키값에 _DEL_ 접두어"""
        self.sc.soft_delete()
        self.sc.refresh_from_db()
        self.assertFalse(self.sc.is_active)
        self.assertTrue(self.sc.count_number.startswith('_DEL_'))
        self.assertIn('SC-TEST-001', self.sc.count_number)

    def test_restore_removes_prefix(self):
        """restore() 시 키값 복원"""
        self.sc.soft_delete()
        self.sc.refresh_from_db()
        self.sc.restore()
        self.sc.refresh_from_db()
        self.assertTrue(self.sc.is_active)
        self.assertEqual(self.sc.count_number, 'SC-TEST-001')

    def test_restore_conflict_raises_error(self):
        """restore() 시 동일 키값이 이미 존재하면 ValueError"""
        from datetime import date
        self.sc.soft_delete()
        # 같은 키값으로 새 레코드 생성
        StockCount.objects.create(
            count_number='SC-TEST-001',
            warehouse=self.warehouse,
            count_date=date.today(),
            created_by=self.user,
        )
        self.sc.refresh_from_db()
        with self.assertRaises(ValueError):
            self.sc.restore()

    def test_soft_delete_without_business_key(self):
        """BUSINESS_KEY_FIELD=None인 모델: 기존 동작 유지"""
        from apps.inventory.models import Warehouse
        wh = Warehouse.objects.create(
            code='WH-BK-001', name='테스트창고',
            created_by=self.user,
        )
        original_code = wh.code
        wh.soft_delete()
        wh.refresh_from_db()
        self.assertFalse(wh.is_active)
        self.assertEqual(wh.code, original_code)

    def test_double_soft_delete_no_double_prefix(self):
        """이미 _DEL_ 접두어가 있으면 중복 추가하지 않음"""
        self.sc.soft_delete()
        self.sc.refresh_from_db()
        first_value = self.sc.count_number
        # soft_delete 재호출 (이미 _DEL_ 상태)
        self.sc.is_active = False
        self.sc.save(update_fields=['is_active', 'updated_at'])
        self.sc.soft_delete()
        self.sc.refresh_from_db()
        self.assertEqual(self.sc.count_number, first_value)

    def test_restore_without_business_key(self):
        """BUSINESS_KEY_FIELD=None인 모델도 restore 가능"""
        product = Product.objects.create(
            code='P-BK-002', name='복원 테스트',
            product_type='FINISHED', unit_price=500, cost_price=200,
            created_by=self.user,
        )
        product.soft_delete()
        product.refresh_from_db()
        self.assertFalse(product.is_active)
        product.restore()
        product.refresh_from_db()
        self.assertTrue(product.is_active)
