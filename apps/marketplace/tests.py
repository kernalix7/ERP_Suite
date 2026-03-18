from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.marketplace.models import (
    MarketplaceConfig, MarketplaceOrder, SyncLog,
)

User = get_user_model()


class MarketplaceConfigModelTest(TestCase):
    """스토어 설정 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='mkpuser', password='testpass123', role='manager',
        )

    def test_config_creation(self):
        """스토어 설정 생성"""
        config = MarketplaceConfig.objects.create(
            shop_name='네이버스토어',
            client_id='test_client_id',
            client_secret='test_secret',
            created_by=self.user,
        )
        self.assertEqual(config.shop_name, '네이버스토어')
        self.assertEqual(config.client_id, 'test_client_id')

    def test_config_str(self):
        """스토어 설정 문자열 표현"""
        config = MarketplaceConfig.objects.create(
            shop_name='쿠팡스토어',
            client_id='coupang_id',
            client_secret='coupang_secret',
            created_by=self.user,
        )
        self.assertEqual(str(config), '쿠팡스토어')

    def test_config_soft_delete(self):
        """스토어 설정 soft delete"""
        config = MarketplaceConfig.objects.create(
            shop_name='삭제테스트',
            client_id='del_id',
            client_secret='del_secret',
            created_by=self.user,
        )
        config.soft_delete()
        qs = MarketplaceConfig.objects.filter(pk=config.pk)
        self.assertFalse(qs.exists())
        qs_all = MarketplaceConfig.all_objects.filter(pk=config.pk)
        self.assertTrue(qs_all.exists())


class MarketplaceOrderModelTest(TestCase):
    """스토어 주문 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='mkporderuser', password='testpass123', role='manager',
        )
        self.now = timezone.now()

    def test_order_creation(self):
        """스토어 주문 생성"""
        order = MarketplaceOrder.objects.create(
            store_order_id='NAVER-2026-001',
            product_name='테스트 상품',
            quantity=2,
            price=Decimal('50000'),
            buyer_name='김구매',
            receiver_name='이수취',
            ordered_at=self.now,
            created_by=self.user,
        )
        self.assertEqual(order.store_order_id, 'NAVER-2026-001')
        self.assertEqual(order.status, MarketplaceOrder.Status.NEW)

    def test_order_str(self):
        """스토어 주문 문자열 표현"""
        order = MarketplaceOrder.objects.create(
            store_order_id='NAVER-STR-001',
            product_name='문자열 상품',
            quantity=1,
            price=Decimal('10000'),
            buyer_name='홍길동',
            receiver_name='홍길동',
            ordered_at=self.now,
            created_by=self.user,
        )
        self.assertIn('NAVER-STR-001', str(order))
        self.assertIn('문자열 상품', str(order))

    def test_order_unique_store_id(self):
        """스토어주문번호 중복 불가"""
        MarketplaceOrder.objects.create(
            store_order_id='DUP-001',
            product_name='상품1',
            quantity=1,
            price=Decimal('10000'),
            buyer_name='구매자',
            receiver_name='수취인',
            ordered_at=self.now,
            created_by=self.user,
        )
        with self.assertRaises(IntegrityError):
            MarketplaceOrder.objects.create(
                store_order_id='DUP-001',
                product_name='상품2',
                quantity=1,
                price=Decimal('20000'),
                buyer_name='구매자2',
                receiver_name='수취인2',
                ordered_at=self.now,
                created_by=self.user,
            )

    def test_order_status_choices(self):
        """스토어 주문 상태 선택지"""
        choices = dict(MarketplaceOrder.Status.choices)
        self.assertIn('NEW', choices)
        self.assertIn('CONFIRMED', choices)
        self.assertIn('SHIPPED', choices)
        self.assertIn('DELIVERED', choices)
        self.assertIn('CANCELLED', choices)
        self.assertIn('RETURNED', choices)

    def test_order_status_transition(self):
        """주문 상태 전환"""
        order = MarketplaceOrder.objects.create(
            store_order_id='TRANS-001',
            product_name='상태전환 테스트',
            quantity=1,
            price=Decimal('10000'),
            buyer_name='구매자',
            receiver_name='수취인',
            ordered_at=self.now,
            created_by=self.user,
        )
        self.assertEqual(order.status, 'NEW')

        order.status = MarketplaceOrder.Status.CONFIRMED
        order.save()
        order.refresh_from_db()
        self.assertEqual(order.status, 'CONFIRMED')

        order.status = MarketplaceOrder.Status.SHIPPED
        order.save()
        order.refresh_from_db()
        self.assertEqual(order.status, 'SHIPPED')

    def test_order_ordering(self):
        """스토어 주문은 최신 주문일시순"""
        o1 = MarketplaceOrder.objects.create(
            store_order_id='ORD-ORD-001',
            product_name='오래된', quantity=1, price=Decimal('10000'),
            buyer_name='구', receiver_name='수',
            ordered_at=self.now - timedelta(days=1),
            created_by=self.user,
        )
        o2 = MarketplaceOrder.objects.create(
            store_order_id='ORD-ORD-002',
            product_name='최신', quantity=1, price=Decimal('10000'),
            buyer_name='구', receiver_name='수',
            ordered_at=self.now,
            created_by=self.user,
        )
        orders = list(MarketplaceOrder.objects.all())
        self.assertEqual(orders[0], o2)
        self.assertEqual(orders[1], o1)

    def test_order_erp_order_link(self):
        """ERP 주문 연결"""
        order = MarketplaceOrder.objects.create(
            store_order_id='LINK-001',
            product_name='연결 테스트',
            quantity=1,
            price=Decimal('10000'),
            buyer_name='구매자',
            receiver_name='수취인',
            ordered_at=self.now,
            created_by=self.user,
        )
        self.assertIsNone(order.erp_order)

    def test_order_soft_delete(self):
        """스토어 주문 soft delete"""
        order = MarketplaceOrder.objects.create(
            store_order_id='SD-001',
            product_name='삭제 테스트',
            quantity=1,
            price=Decimal('10000'),
            buyer_name='구매자',
            receiver_name='수취인',
            ordered_at=self.now,
            created_by=self.user,
        )
        order.soft_delete()
        self.assertFalse(MarketplaceOrder.objects.filter(pk=order.pk).exists())


class SyncLogModelTest(TestCase):
    """동기화 이력 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='syncuser', password='testpass123', role='manager',
        )
        self.now = timezone.now()

    def test_sync_log_creation(self):
        """동기화 이력 생성"""
        log = SyncLog.objects.create(
            direction=SyncLog.Direction.PULL,
            started_at=self.now,
            total_count=100,
            success_count=95,
            error_count=5,
            created_by=self.user,
        )
        self.assertEqual(log.total_count, 100)
        self.assertEqual(log.success_count, 95)
        self.assertEqual(log.error_count, 5)

    def test_sync_log_str(self):
        """동기화 이력 문자열 표현"""
        log = SyncLog.objects.create(
            direction=SyncLog.Direction.PUSH,
            started_at=self.now,
            created_by=self.user,
        )
        result = str(log)
        self.assertIn('발신', result)

    def test_sync_log_direction_choices(self):
        """동기화 방향 선택지"""
        choices = dict(SyncLog.Direction.choices)
        self.assertIn('PULL', choices)
        self.assertIn('PUSH', choices)

    def test_sync_log_with_error_message(self):
        """오류 메시지 기록"""
        log = SyncLog.objects.create(
            direction=SyncLog.Direction.PULL,
            started_at=self.now,
            error_count=3,
            error_message='API 응답 시간 초과',
            created_by=self.user,
        )
        self.assertEqual(log.error_message, 'API 응답 시간 초과')

    def test_sync_log_completed_at(self):
        """완료 시간 기록"""
        log = SyncLog.objects.create(
            direction=SyncLog.Direction.PUSH,
            started_at=self.now,
            completed_at=self.now + timedelta(minutes=5),
            total_count=50,
            success_count=50,
            created_by=self.user,
        )
        self.assertIsNotNone(log.completed_at)
