from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.inventory.models import Product
from apps.marketplace.models import (
    MarketplaceConfig, MarketplaceOrder, SyncLog,
)
from apps.sales.models import Quotation

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


class MarketplaceOrderSignalTest(TestCase):
    """마켓플레이스 주문 → ERP 주문 자동 생성 시그널 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='siguser', password='testpass123', role='manager',
        )
        self.now = timezone.now()
        self.product = Product.objects.create(
            code='MKT-PRD-001',
            name='시그널 테스트 상품',
            product_type=Product.ProductType.FINISHED,
            unit_price=Decimal('50000'),
        )

    def test_new_order_creates_erp_quotation(self):
        """NEW 상태 마켓플레이스 주문 → ERP 견적서 자동 생성"""
        mkt_order = MarketplaceOrder.objects.create(
            store_order_id='SIG-NEW-001',
            product_name='시그널 테스트 상품',
            quantity=3,
            price=Decimal('150000'),
            buyer_name='시그널구매자',
            buyer_phone='010-1234-5678',
            receiver_name='수취인',
            receiver_address='서울시 강남구',
            ordered_at=self.now,
            status=MarketplaceOrder.Status.NEW,
            created_by=self.user,
        )
        mkt_order.refresh_from_db()
        self.assertIsNotNone(mkt_order.erp_quotation)

        quotation = mkt_order.erp_quotation
        self.assertEqual(quotation.status, 'DRAFT')
        self.assertEqual(quotation.quote_items.count(), 1)
        item = quotation.quote_items.first()
        self.assertEqual(item.product, self.product)
        self.assertEqual(item.quantity, 3)

        # 고객에 전화번호/주소 포함 확인
        customer = quotation.customer
        self.assertEqual(customer.name, '시그널구매자')
        self.assertEqual(customer.phone, '010-1234-5678')
        self.assertEqual(customer.address, '서울시 강남구')

    def test_non_new_status_skips_signal(self):
        """NEW가 아닌 상태에서는 견적서 미생성"""
        mkt_order = MarketplaceOrder.objects.create(
            store_order_id='SIG-CONF-001',
            product_name='시그널 테스트 상품',
            quantity=1,
            price=Decimal('50000'),
            buyer_name='구매자',
            receiver_name='수취인',
            ordered_at=self.now,
            status=MarketplaceOrder.Status.CONFIRMED,
            created_by=self.user,
        )
        self.assertIsNone(mkt_order.erp_quotation)

    def test_no_product_match_skips(self):
        """상품명 매칭 실패 시 견적서 미생성"""
        mkt_order = MarketplaceOrder.objects.create(
            store_order_id='SIG-NOMATCH-001',
            product_name='존재하지않는상품',
            quantity=1,
            price=Decimal('10000'),
            buyer_name='구매자',
            receiver_name='수취인',
            ordered_at=self.now,
            status=MarketplaceOrder.Status.NEW,
            created_by=self.user,
        )
        mkt_order.refresh_from_db()
        self.assertIsNone(mkt_order.erp_quotation)

    def test_duplicate_prevention(self):
        """이미 erp_quotation이 있으면 재생성 안 함"""
        # 먼저 정상 생성
        mkt_order = MarketplaceOrder.objects.create(
            store_order_id='SIG-DUP-001',
            product_name='시그널 테스트 상품',
            quantity=1,
            price=Decimal('50000'),
            buyer_name='구매자',
            receiver_name='수취인',
            ordered_at=self.now,
            status=MarketplaceOrder.Status.NEW,
            created_by=self.user,
        )
        mkt_order.refresh_from_db()
        first_quotation = mkt_order.erp_quotation
        self.assertIsNotNone(first_quotation)

        # 다시 save해도 새 견적서 안 생김
        quote_count_before = Quotation.objects.count()
        mkt_order.save()
        self.assertEqual(Quotation.objects.count(), quote_count_before)


class SelectiveImportTest(TestCase):
    """선택적 주문 가져오기 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='importuser', password='testpass123', role='manager',
        )
        self.config = MarketplaceConfig.objects.create(
            shop_name='네이버스토어',
            client_id='test_id',
            client_secret='test_secret',
            created_by=self.user,
        )
        self.now = timezone.now()

    def test_import_selected_orders(self):
        """선택된 주문만 가져오기"""
        from apps.marketplace.sync_service import import_selected_orders

        orders_data = [
            {
                'store_order_id': 'SEL-001',
                'product_name': '선택 상품 1',
                'quantity': 1,
                'price': 10000,
                'buyer_name': '구매자',
                'buyer_phone': '010-1111-2222',
                'receiver_name': '수취인',
                'receiver_phone': '010-3333-4444',
                'receiver_address': '서울시',
                'status': 'NEW',
                'ordered_at': self.now.isoformat(),
            },
            {
                'store_order_id': 'SEL-002',
                'product_name': '선택 상품 2',
                'quantity': 2,
                'price': 20000,
                'buyer_name': '구매자2',
                'buyer_phone': '010-5555-6666',
                'receiver_name': '수취인2',
                'receiver_phone': '010-7777-8888',
                'receiver_address': '부산시',
                'status': 'NEW',
                'ordered_at': self.now.isoformat(),
            },
        ]

        sync_log = import_selected_orders(
            config=self.config,
            orders_data=orders_data,
            user=self.user,
        )
        self.assertEqual(sync_log.success_count, 2)
        self.assertEqual(sync_log.error_count, 0)
        self.assertTrue(MarketplaceOrder.objects.filter(store_order_id='SEL-001').exists())
        self.assertTrue(MarketplaceOrder.objects.filter(store_order_id='SEL-002').exists())

    def test_import_skips_already_imported_flag(self):
        """already_imported 플래그가 있어도 정상 처리"""
        from apps.marketplace.sync_service import import_selected_orders

        orders_data = [{
            'store_order_id': 'FLAG-001',
            'product_name': '플래그 테스트',
            'quantity': 1,
            'price': 5000,
            'buyer_name': '구매자',
            'buyer_phone': '',
            'receiver_name': '수취인',
            'receiver_phone': '',
            'receiver_address': '',
            'status': 'NEW',
            'ordered_at': self.now.isoformat(),
            'already_imported': True,
        }]

        sync_log = import_selected_orders(
            config=self.config,
            orders_data=orders_data,
            user=self.user,
        )
        self.assertEqual(sync_log.success_count, 1)


class SelectiveImportViewTest(TestCase):
    """선택적 가져오기 뷰 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='viewuser', password='testpass123', role='manager',
        )
        self.config = MarketplaceConfig.objects.create(
            shop_name='네이버스토어',
            client_id='test_id',
            client_secret='test_secret',
            created_by=self.user,
        )
        self.client.force_login(self.user)
        self.now = timezone.now()

    def test_import_selected_view_no_selection(self):
        """선택 없이 제출 시 경고"""
        from django.urls import reverse
        response = self.client.post(reverse('marketplace:import_selected'))
        self.assertEqual(response.status_code, 302)

    def test_import_selected_view_with_session_data(self):
        """세션 데이터로 선택 가져오기"""
        from django.urls import reverse
        session = self.client.session
        session['sync_preview_orders'] = [
            {
                'store_order_id': 'VIEW-001',
                'product_name': '뷰 테스트 상품',
                'quantity': 1,
                'price': 15000,
                'buyer_name': '뷰구매자',
                'buyer_phone': '',
                'receiver_name': '뷰수취인',
                'receiver_phone': '',
                'receiver_address': '',
                'status': 'NEW',
                'ordered_at': self.now.isoformat(),
                'already_imported': False,
            },
        ]
        session.save()

        response = self.client.post(
            reverse('marketplace:import_selected'),
            {'selected_orders': ['VIEW-001']},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            MarketplaceOrder.objects.filter(store_order_id='VIEW-001').exists()
        )
