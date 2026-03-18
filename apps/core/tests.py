from django.test import TestCase, Client, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.core.notification import Notification, create_notification
from apps.core.attachment import Attachment, ALLOWED_EXTENSIONS, MAX_FILE_SIZE
from apps.core.middleware import AccessLogMiddleware
from apps.inventory.models import Product

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
