from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.inventory.models import Product
from apps.marketplace.models import (
    ImportTemplate, MarketplaceConfig, MarketplaceOrder, ProductMapping,
    SettlementReconciliation, SyncLog,
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


class ProductMappingModelTest(TestCase):
    """상품매핑 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='mapuser', password='testpass123', role='manager',
        )
        self.product = Product.objects.create(
            code='MAP-PRD-001',
            name='매핑 테스트 상품',
            product_type=Product.ProductType.FINISHED,
            unit_price=Decimal('30000'),
        )

    def test_mapping_creation(self):
        """상품매핑 생성"""
        mapping = ProductMapping.objects.create(
            store_product_name='스토어 상품명',
            store_option_name='옵션A',
            product=self.product,
            created_by=self.user,
        )
        self.assertEqual(mapping.store_product_name, '스토어 상품명')
        self.assertEqual(mapping.product, self.product)

    def test_mapping_str(self):
        """상품매핑 문자열 표현"""
        m1 = ProductMapping.objects.create(
            store_product_name='이름만',
            product=self.product,
            created_by=self.user,
        )
        self.assertIn('이름만', str(m1))

        m2 = ProductMapping.objects.create(
            store_product_name='이름옵션',
            store_option_name='색상',
            product=self.product,
            created_by=self.user,
        )
        self.assertIn('[색상]', str(m2))

    def test_mapping_unique_together_with_template(self):
        """같은 템플릿 내 같은 스토어상품명+옵션명 중복 불가"""
        tmpl = ImportTemplate.objects.create(
            name='유니크테스트', store_type='OTHER', created_by=self.user,
        )
        ProductMapping.objects.create(
            template=tmpl,
            store_product_name='중복테스트',
            store_option_name='옵션X',
            product=self.product,
            created_by=self.user,
        )
        with self.assertRaises(IntegrityError):
            ProductMapping.objects.create(
                template=tmpl,
                store_product_name='중복테스트',
                store_option_name='옵션X',
                product=self.product,
                created_by=self.user,
            )


class ProductMatchingTest(TestCase):
    """상품 매칭 로직 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='matchuser', password='testpass123', role='manager',
        )
        self.product = Product.objects.create(
            code='MATCH-001',
            name='다이브체커 프리미엄',
            product_type=Product.ProductType.FINISHED,
            unit_price=Decimal('89000'),
        )

    def test_exact_match(self):
        """정확한 상품명 매칭"""
        from apps.marketplace.sync_service import _match_product
        result = _match_product('다이브체커 프리미엄')
        self.assertEqual(result['match_type'], 'exact')
        self.assertEqual(result['product'], self.product)

    def test_saved_mapping_match(self):
        """저장된 매핑 규칙으로 매칭"""
        from apps.marketplace.sync_service import _match_product
        ProductMapping.objects.create(
            store_product_name='Divechecker Premium',
            product=self.product,
            created_by=self.user,
        )
        result = _match_product('Divechecker Premium')
        self.assertEqual(result['match_type'], 'saved')
        self.assertEqual(result['product'], self.product)

    def test_partial_match(self):
        """부분 매칭"""
        from apps.marketplace.sync_service import _match_product
        result = _match_product('다이브체커 스탠다드 에디션')
        self.assertEqual(result['match_type'], 'partial')
        self.assertIn(self.product, result['suggested'])

    def test_no_match(self):
        """매칭 실패"""
        from apps.marketplace.sync_service import _match_product
        result = _match_product('완전히다른상품명')
        self.assertEqual(result['match_type'], 'none')
        self.assertIsNone(result['product'])

    def test_customer_matching_existing(self):
        """기존 고객 매칭"""
        from apps.sales.models import Customer
        from apps.marketplace.sync_service import _match_customer
        Customer.objects.create(name='김테스트', phone='010-0000-0000', created_by=self.user)
        result = _match_customer('김테스트')
        self.assertFalse(result['is_new_customer'])

    def test_customer_matching_new(self):
        """신규 고객 매칭"""
        from apps.marketplace.sync_service import _match_customer
        result = _match_customer('없는고객')
        self.assertTrue(result['is_new_customer'])


class ImportWithMappingTest(TestCase):
    """매칭 정보 포함 가져오기 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='impmapuser', password='testpass123', role='manager',
        )
        self.product = Product.objects.create(
            code='IMP-MAP-001',
            name='임포트매핑상품',
            product_type=Product.ProductType.FINISHED,
            unit_price=Decimal('50000'),
        )
        self.now = timezone.now()

    def test_import_with_matched_product_creates_quotation(self):
        """matched_product_id가 있으면 직접 견적서 생성"""
        from apps.marketplace.sync_service import import_selected_orders

        orders_data = [{
            'store_order_id': 'IMP-MATCH-001',
            'product_name': '스토어에서는 다른 이름',
            'quantity': 2,
            'price': 100000,
            'buyer_name': '매핑구매자',
            'buyer_phone': '010-1111-2222',
            'receiver_name': '수취인',
            'receiver_phone': '',
            'receiver_address': '서울시',
            'status': 'NEW',
            'ordered_at': self.now.isoformat(),
            'matched_product_id': self.product.pk,
        }]

        sync_log = import_selected_orders(orders_data=orders_data, user=self.user)
        self.assertEqual(sync_log.success_count, 1)

        order = MarketplaceOrder.objects.get(store_order_id='IMP-MATCH-001')
        order.refresh_from_db()
        self.assertIsNotNone(order.erp_quotation)
        item = order.erp_quotation.quote_items.first()
        self.assertEqual(item.product, self.product)

    def test_import_skip_signal_when_matched(self):
        """matched_product_id가 있으면 시그널이 아닌 직접 생성 경로 사용"""
        from apps.marketplace.sync_service import import_selected_orders

        orders_data = [{
            'store_order_id': 'IMP-SKIP-001',
            'product_name': '없는상품이름',
            'quantity': 1,
            'price': 50000,
            'buyer_name': '스킵구매자',
            'buyer_phone': '',
            'receiver_name': '수취인',
            'receiver_phone': '',
            'receiver_address': '',
            'status': 'NEW',
            'ordered_at': self.now.isoformat(),
            'matched_product_id': self.product.pk,
        }]

        sync_log = import_selected_orders(orders_data=orders_data, user=self.user)
        self.assertEqual(sync_log.success_count, 1)

        order = MarketplaceOrder.objects.get(store_order_id='IMP-SKIP-001')
        order.refresh_from_db()
        # 시그널은 '없는상품이름'으로 매칭 실패했겠지만,
        # 직접 생성 경로에서 product_id로 견적 생성됨
        self.assertIsNotNone(order.erp_quotation)


class ImportMappingRuleSaveViewTest(TestCase):
    """가져오기 시 매핑 규칙 저장 뷰 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='rulesaveuser', password='testpass123', role='manager',
        )
        self.product = Product.objects.create(
            code='RULE-001',
            name='규칙저장상품',
            product_type=Product.ProductType.FINISHED,
            unit_price=Decimal('30000'),
        )
        self.client.force_login(self.user)
        self.now = timezone.now()

    def test_save_rule_on_import(self):
        """가져오기 시 규칙 저장 체크하면 ProductMapping 생성"""
        from django.urls import reverse

        session = self.client.session
        session['sync_preview_orders'] = [{
            'store_order_id': 'RULE-001',
            'product_name': 'Store Product Name',
            'option_name': 'Color Red',
            'quantity': 1,
            'price': 30000,
            'buyer_name': '규칙구매자',
            'buyer_phone': '',
            'receiver_name': '수취인',
            'receiver_phone': '',
            'receiver_address': '',
            'status': 'NEW',
            'ordered_at': self.now.isoformat(),
            'already_imported': False,
            'matched_product_id': self.product.pk,
        }]
        session.save()

        response = self.client.post(
            reverse('marketplace:import_selected'),
            {
                'selected_orders': ['RULE-001'],
                f'product_for_RULE-001': str(self.product.pk),
                f'save_rule_RULE-001': 'on',
            },
        )
        self.assertEqual(response.status_code, 302)

        # ProductMapping이 생성되었는지 확인
        self.assertTrue(
            ProductMapping.objects.filter(
                store_product_name='Store Product Name',
                store_option_name='Color Red',
                product=self.product,
            ).exists()
        )


class ImportTemplateModelTest(TestCase):
    """가져오기 템플릿 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='tmpluser', password='testpass123', role='manager',
        )

    def test_template_creation(self):
        """템플릿 생성"""
        tmpl = ImportTemplate.objects.create(
            name='네이버 기본',
            store_type=ImportTemplate.StoreType.NAVER,
            default_period=7,
            created_by=self.user,
        )
        self.assertEqual(tmpl.name, '네이버 기본')
        self.assertEqual(tmpl.store_type, 'NAVER')
        self.assertTrue(tmpl.auto_confirm)

    def test_template_str(self):
        """템플릿 문자열 표현"""
        tmpl = ImportTemplate.objects.create(
            name='쿠팡 테스트',
            store_type=ImportTemplate.StoreType.COUPANG,
            created_by=self.user,
        )
        self.assertIn('쿠팡 테스트', str(tmpl))
        self.assertIn('쿠팡', str(tmpl))

    def test_template_with_mappings(self):
        """템플릿에 매핑 연결"""
        product = Product.objects.create(
            code='TMPL-PRD-001', name='템플릿제품',
            product_type=Product.ProductType.FINISHED,
            unit_price=Decimal('50000'),
        )
        tmpl = ImportTemplate.objects.create(
            name='매핑 포함 템플릿',
            store_type=ImportTemplate.StoreType.NAVER,
            created_by=self.user,
        )
        ProductMapping.objects.create(
            template=tmpl,
            store_product_name='스토어상품A',
            product=product,
            created_by=self.user,
        )
        self.assertEqual(tmpl.mappings.count(), 1)

    def test_mapping_unique_with_template(self):
        """같은 템플릿 내 같은 상품명+옵션 중복 불가"""
        product = Product.objects.create(
            code='TMPL-UNQ-001', name='유니크제품',
            product_type=Product.ProductType.FINISHED,
            unit_price=Decimal('10000'),
        )
        tmpl = ImportTemplate.objects.create(
            name='유니크 테스트',
            store_type=ImportTemplate.StoreType.OTHER,
            created_by=self.user,
        )
        ProductMapping.objects.create(
            template=tmpl,
            store_product_name='동일상품',
            store_option_name='동일옵션',
            product=product,
            created_by=self.user,
        )
        with self.assertRaises(IntegrityError):
            ProductMapping.objects.create(
                template=tmpl,
                store_product_name='동일상품',
                store_option_name='동일옵션',
                product=product,
                created_by=self.user,
            )

    def test_different_templates_same_mapping(self):
        """다른 템플릿에서 같은 상품명+옵션 허용"""
        product = Product.objects.create(
            code='TMPL-DIFF-001', name='다른템플릿제품',
            product_type=Product.ProductType.FINISHED,
            unit_price=Decimal('20000'),
        )
        tmpl1 = ImportTemplate.objects.create(
            name='템플릿1', store_type='NAVER', created_by=self.user,
        )
        tmpl2 = ImportTemplate.objects.create(
            name='템플릿2', store_type='COUPANG', created_by=self.user,
        )
        m1 = ProductMapping.objects.create(
            template=tmpl1,
            store_product_name='공통상품',
            product=product,
            created_by=self.user,
        )
        m2 = ProductMapping.objects.create(
            template=tmpl2,
            store_product_name='공통상품',
            product=product,
            created_by=self.user,
        )
        self.assertNotEqual(m1.pk, m2.pk)


class TemplateMatchingTest(TestCase):
    """템플릿 기반 매칭 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='tmplmatchuser', password='testpass123', role='manager',
        )
        self.product_a = Product.objects.create(
            code='TM-A', name='제품A',
            product_type=Product.ProductType.FINISHED,
            unit_price=Decimal('10000'),
        )
        self.product_b = Product.objects.create(
            code='TM-B', name='제품B',
            product_type=Product.ProductType.FINISHED,
            unit_price=Decimal('20000'),
        )
        self.template = ImportTemplate.objects.create(
            name='테스트 템플릿',
            store_type='NAVER',
            created_by=self.user,
        )
        # 템플릿 매핑: 스토어상품X → 제품A
        ProductMapping.objects.create(
            template=self.template,
            store_product_name='스토어상품X',
            product=self.product_a,
            created_by=self.user,
        )
        # 전역 매핑: 스토어상품X → 제품B
        ProductMapping.objects.create(
            template=None,
            store_product_name='스토어상품X',
            product=self.product_b,
            created_by=self.user,
        )

    def test_template_mapping_takes_priority(self):
        """템플릿 매핑이 전역 매핑보다 우선"""
        from apps.marketplace.sync_service import _match_product
        result = _match_product('스토어상품X', template_id=self.template.pk)
        self.assertEqual(result['match_type'], 'saved')
        self.assertEqual(result['product'], self.product_a)

    def test_global_mapping_fallback(self):
        """템플릿에 매핑 없으면 전역 매핑 사용"""
        from apps.marketplace.sync_service import _match_product
        result = _match_product('스토어상품X', template_id=99999)
        self.assertEqual(result['match_type'], 'saved')
        self.assertEqual(result['product'], self.product_b)

    def test_no_template_uses_any_mapping(self):
        """template_id 없으면 첫 번째 매핑 사용"""
        from apps.marketplace.sync_service import _match_product
        result = _match_product('스토어상품X')
        self.assertEqual(result['match_type'], 'saved')
        self.assertIn(result['product'], [self.product_a, self.product_b])


class SaveTemplateViewTest(TestCase):
    """템플릿 저장 뷰 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='savetmpluser', password='testpass123', role='manager',
        )
        self.product = Product.objects.create(
            code='SAVE-TMPL-001', name='템플릿저장제품',
            product_type=Product.ProductType.FINISHED,
            unit_price=Decimal('30000'),
        )
        self.client.force_login(self.user)

    def test_save_template_creates_template_and_mappings(self):
        """결과 페이지에서 템플릿 저장 시 ImportTemplate + ProductMapping 생성"""
        from django.urls import reverse

        session = self.client.session
        session['import_result'] = {
            'success_count': 2,
            'error_count': 0,
            'mapping_pairs': [
                {
                    'store_product_name': '스토어A',
                    'store_option_name': '',
                    'product_id': self.product.pk,
                },
                {
                    'store_product_name': '스토어B',
                    'store_option_name': '옵션1',
                    'product_id': self.product.pk,
                },
            ],
            'template_id': None,
        }
        session.save()

        response = self.client.post(
            reverse('marketplace:save_template'),
            {
                'template_name': '새 네이버 템플릿',
                'store_type': 'NAVER',
                'default_period': '30',
            },
        )
        self.assertEqual(response.status_code, 302)

        tmpl = ImportTemplate.objects.get(name='새 네이버 템플릿')
        self.assertEqual(tmpl.store_type, 'NAVER')
        self.assertEqual(tmpl.default_period, 30)
        self.assertEqual(tmpl.mappings.count(), 2)

    def test_save_template_updates_existing(self):
        """기존 템플릿 ID가 있으면 업데이트"""
        from django.urls import reverse

        existing = ImportTemplate.objects.create(
            name='기존 템플릿',
            store_type='COUPANG',
            default_period=7,
            created_by=self.user,
        )

        session = self.client.session
        session['import_result'] = {
            'success_count': 1,
            'error_count': 0,
            'mapping_pairs': [
                {
                    'store_product_name': '추가상품',
                    'store_option_name': '',
                    'product_id': self.product.pk,
                },
            ],
            'template_id': existing.pk,
        }
        session.save()

        response = self.client.post(
            reverse('marketplace:save_template'),
            {
                'template_name': '업데이트된 템플릿',
                'store_type': 'NAVER',
                'default_period': '14',
            },
        )
        self.assertEqual(response.status_code, 302)

        existing.refresh_from_db()
        self.assertEqual(existing.name, '업데이트된 템플릿')
        self.assertEqual(existing.store_type, 'NAVER')
        self.assertEqual(existing.default_period, 14)
        self.assertEqual(existing.mappings.count(), 1)

    def test_import_result_page_accessible(self):
        """결과 페이지 접근 가능"""
        from django.urls import reverse

        session = self.client.session
        session['import_result'] = {
            'success_count': 3,
            'error_count': 0,
            'mapping_pairs': [],
            'template_id': None,
        }
        session.save()

        response = self.client.get(reverse('marketplace:import_result'))
        self.assertEqual(response.status_code, 200)

    def test_import_result_redirects_without_data(self):
        """세션 데이터 없으면 대시보드로 리다이렉트"""
        from django.urls import reverse
        response = self.client.get(reverse('marketplace:import_result'))
        self.assertEqual(response.status_code, 302)


class SettlementReconciliationModelTest(TestCase):
    """정산 대사 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='reconuser', password='testpass123', role='manager',
        )

    def test_reconciliation_creation(self):
        """정산 대사 레코드 생성"""
        from datetime import date
        recon = SettlementReconciliation.objects.create(
            store_module='NAVER',
            settlement_date=date(2026, 4, 1),
            expected_amount=100000,
            actual_amount=100000,
            difference=0,
            status=SettlementReconciliation.Status.MATCHED,
            created_by=self.user,
        )
        self.assertEqual(recon.store_module, 'NAVER')
        self.assertEqual(recon.status, 'MATCHED')
        self.assertEqual(recon.difference, 0)

    def test_reconciliation_str(self):
        """문자열 표현"""
        from datetime import date
        recon = SettlementReconciliation.objects.create(
            store_module='COUPANG',
            settlement_date=date(2026, 4, 1),
            expected_amount=50000,
            actual_amount=50005,
            difference=5,
            status=SettlementReconciliation.Status.MATCHED,
            created_by=self.user,
        )
        self.assertIn('COUPANG', str(recon))
        self.assertIn('일치', str(recon))

    def test_reconciliation_soft_delete(self):
        """soft delete"""
        from datetime import date
        recon = SettlementReconciliation.objects.create(
            store_module='NAVER',
            settlement_date=date(2026, 4, 1),
            expected_amount=100000,
            actual_amount=0,
            difference=-100000,
            status=SettlementReconciliation.Status.PENDING,
            created_by=self.user,
        )
        recon.is_active = False
        recon.save()
        self.assertFalse(
            SettlementReconciliation.objects.filter(
                pk=recon.pk, is_active=True,
            ).exists(),
        )

    def test_reconciliation_ordering(self):
        """최근 정산일 기준 정렬"""
        from datetime import date
        r1 = SettlementReconciliation.objects.create(
            store_module='NAVER',
            settlement_date=date(2026, 3, 1),
            created_by=self.user,
        )
        r2 = SettlementReconciliation.objects.create(
            store_module='NAVER',
            settlement_date=date(2026, 4, 1),
            created_by=self.user,
        )
        qs = list(SettlementReconciliation.objects.all())
        self.assertEqual(qs[0], r2)
        self.assertEqual(qs[1], r1)


class ReconciliationServiceTest(TestCase):
    """정산 대사 서비스 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='svcuser', password='testpass123', role='manager',
        )
        from apps.sales.models import Partner
        self.partner = Partner.objects.create(
            name='테스트 거래처',
            partner_type='customer',
            created_by=self.user,
        )

    def test_reconcile_manual_mode(self):
        """API 미지원 스토어 — 수동처리 모드"""
        from datetime import date
        from apps.accounting.models import Payment
        Payment.objects.create(
            payment_type=Payment.PaymentType.RECEIPT,
            partner=self.partner,
            amount=50000,
            payment_date=date(2026, 4, 1),
            created_by=self.user,
        )
        from apps.marketplace.reconciliation_service import reconcile_settlements
        results = reconcile_settlements('NONEXISTENT', date(2026, 4, 1), date(2026, 4, 30))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, SettlementReconciliation.Status.MANUAL)
        self.assertEqual(results[0].actual_amount, 50000)
        self.assertEqual(results[0].expected_amount, 0)

    def test_reconcile_no_payments(self):
        """입금 내역 없으면 빈 결과"""
        from datetime import date
        from apps.marketplace.reconciliation_service import reconcile_settlements
        results = reconcile_settlements('NONEXISTENT', date(2026, 4, 1), date(2026, 4, 30))
        self.assertEqual(len(results), 0)


class ReconciliationViewTest(TestCase):
    """정산 대사 뷰 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='viewuser', password='testpass123', role='manager',
        )
        self.client.force_login(self.user)

    def test_reconciliation_list_accessible(self):
        """대사 목록 접근 가능"""
        from django.urls import reverse
        response = self.client.get(reverse('marketplace:reconciliation_list'))
        self.assertEqual(response.status_code, 200)

    def test_reconciliation_run_get(self):
        """대사 실행 폼 GET"""
        from django.urls import reverse
        response = self.client.get(reverse('marketplace:reconciliation_run'))
        self.assertEqual(response.status_code, 200)

    def test_reconciliation_list_filter_status(self):
        """상태 필터링"""
        from datetime import date
        from django.urls import reverse
        SettlementReconciliation.objects.create(
            store_module='NAVER',
            settlement_date=date(2026, 4, 1),
            status=SettlementReconciliation.Status.MATCHED,
            created_by=self.user,
        )
        SettlementReconciliation.objects.create(
            store_module='NAVER',
            settlement_date=date(2026, 4, 2),
            status=SettlementReconciliation.Status.MISMATCHED,
            created_by=self.user,
        )
        response = self.client.get(
            reverse('marketplace:reconciliation_list'), {'status': 'MATCHED'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['reconciliations']), 1)

    def test_reconciliation_list_staff_denied(self):
        """staff 권한으로 접근 거부"""
        from django.urls import reverse
        staff = User.objects.create_user(
            username='staffuser', password='testpass123', role='staff',
        )
        self.client.force_login(staff)
        response = self.client.get(reverse('marketplace:reconciliation_list'))
        self.assertEqual(response.status_code, 403)


class ReverseSyncServiceTest(TestCase):
    """역동기화 서비스 테스트 (push_shipping_info, push_return_info)"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='pushuser', password='testpass123', role='manager',
        )
        self.now = timezone.now()

    def test_push_shipping_info_missing_tracking(self):
        """운송장번호 없으면 False 반환"""
        from apps.marketplace.sync_service import push_shipping_info
        order = MarketplaceOrder.objects.create(
            store_order_id='PUSH-NO-TRACK-001',
            product_name='테스트 상품',
            quantity=1,
            price=Decimal('50000'),
            buyer_name='구매자',
            receiver_name='수취인',
            ordered_at=self.now,
            delivery_company='CJ대한통운',
            tracking_number='',
            platform_product_order_id='PPO-001',
            created_by=self.user,
        )
        self.assertFalse(push_shipping_info(order))

    def test_push_shipping_info_missing_platform_id(self):
        """플랫폼 주문번호 없으면 False 반환"""
        from apps.marketplace.sync_service import push_shipping_info
        order = MarketplaceOrder.objects.create(
            store_order_id='PUSH-NO-PID-001',
            product_name='테스트 상품',
            quantity=1,
            price=Decimal('50000'),
            buyer_name='구매자',
            receiver_name='수취인',
            ordered_at=self.now,
            delivery_company='CJ대한통운',
            tracking_number='1234567890',
            platform_product_order_id='',
            created_by=self.user,
        )
        self.assertFalse(push_shipping_info(order))

    def test_push_return_info_missing_platform_id(self):
        """플랫폼 주문번호 없으면 반품 전송 False"""
        from apps.marketplace.sync_service import push_return_info
        order = MarketplaceOrder.objects.create(
            store_order_id='PUSH-RET-NO-PID-001',
            product_name='테스트 상품',
            quantity=1,
            price=Decimal('50000'),
            buyer_name='구매자',
            receiver_name='수취인',
            ordered_at=self.now,
            platform_product_order_id='',
            created_by=self.user,
        )
        self.assertFalse(push_return_info(order))

    def test_push_shipping_no_modules(self):
        """API 모듈 없으면 False + SyncLog 에러"""
        from apps.marketplace.sync_service import push_shipping_info
        order = MarketplaceOrder.objects.create(
            store_order_id='PUSH-NO-MOD-001',
            product_name='테스트 상품',
            quantity=1,
            price=Decimal('50000'),
            buyer_name='구매자',
            receiver_name='수취인',
            ordered_at=self.now,
            delivery_company='CJ대한통운',
            tracking_number='9999999999',
            platform_product_order_id='PPO-002',
            created_by=self.user,
        )
        result = push_shipping_info(order)
        # API 키 미설정이므로 모듈 클라이언트가 없어 False
        self.assertFalse(result)


class ReverseSyncViewTest(TestCase):
    """역동기화 뷰 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='pushviewuser', password='testpass123', role='manager',
        )
        self.client.force_login(self.user)
        self.now = timezone.now()
        self.order = MarketplaceOrder.objects.create(
            store_order_id='VIEW-PUSH-001',
            product_name='역동기 뷰 테스트',
            quantity=1,
            price=Decimal('30000'),
            buyer_name='구매자',
            receiver_name='수취인',
            ordered_at=self.now,
            delivery_company='CJ대한통운',
            tracking_number='1234567890',
            platform_product_order_id='PPO-VIEW-001',
            status=MarketplaceOrder.Status.CONFIRMED,
            created_by=self.user,
        )

    def test_push_shipment_view_post(self):
        """배송정보 전송 뷰 POST"""
        from django.urls import reverse
        response = self.client.post(
            reverse('marketplace:push_shipment', kwargs={'slug': self.order.store_order_id}),
        )
        # API 키 미설정이므로 실패 메시지가 나오지만 리다이렉트는 됨
        self.assertEqual(response.status_code, 302)

    def test_push_shipment_missing_tracking_redirects(self):
        """운송장 미입력 시 에러 메시지와 리다이렉트"""
        from django.urls import reverse
        self.order.tracking_number = ''
        self.order.save(update_fields=['tracking_number'])
        response = self.client.post(
            reverse('marketplace:push_shipment', kwargs={'slug': self.order.store_order_id}),
        )
        self.assertEqual(response.status_code, 302)

    def test_push_return_view_post(self):
        """반품정보 전송 뷰 POST"""
        from django.urls import reverse
        response = self.client.post(
            reverse('marketplace:push_return', kwargs={'slug': self.order.store_order_id}),
            {'reason': '고객 변심'},
        )
        self.assertEqual(response.status_code, 302)

    def test_push_shipment_nonexistent_order(self):
        """존재하지 않는 주문 → 에러 메시지"""
        from django.urls import reverse
        response = self.client.post(
            reverse('marketplace:push_shipment', kwargs={'slug': 'NONEXIST-999'}),
        )
        self.assertEqual(response.status_code, 302)

    def test_push_shipment_staff_denied(self):
        """staff 권한 접근 거부"""
        from django.urls import reverse
        staff = User.objects.create_user(
            username='pushstaff', password='testpass123', role='staff',
        )
        self.client.force_login(staff)
        response = self.client.post(
            reverse('marketplace:push_shipment', kwargs={'slug': self.order.store_order_id}),
        )
        self.assertEqual(response.status_code, 403)


class PushShippingRetryTaskTest(TestCase):
    """push_shipping_async 재시도/최종 실패 알림 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='retryadmin', password='testpass123', role='admin',
        )
        self.now = timezone.now()
        self.order = MarketplaceOrder.objects.create(
            store_order_id='RETRY-001',
            product_name='재시도 테스트',
            quantity=1,
            price=Decimal('10000'),
            buyer_name='구매자',
            receiver_name='수취인',
            ordered_at=self.now,
            delivery_company='CJ대한통운',
            tracking_number='RETRY-TRACK-001',
            platform_product_order_id='RETRY-PPO-001',
            created_by=self.user,
        )

    def test_push_shipping_retry_on_failure_then_notify(self):
        """일시 실패 시 retry 시도 → 한도 초과 시 운영자 Notification 생성"""
        from unittest.mock import patch, MagicMock
        from celery.exceptions import MaxRetriesExceededError
        from apps.core.notification import Notification
        from apps.marketplace.sync_service import PushShippingError
        from apps.marketplace import tasks as mp_tasks

        # 1) push_shipping_info가 PushShippingError 발생 → retry 시도 → 한도 초과
        with patch(
            'apps.marketplace.sync_service.push_shipping_info',
            side_effect=PushShippingError('일시 API 오류'),
        ):
            with patch.object(
                mp_tasks.push_shipping_async, 'retry',
                side_effect=MaxRetriesExceededError('retry limit'),
            ) as mock_retry:
                result = mp_tasks.push_shipping_async.apply(
                    args=[self.order.pk]
                ).result

        self.assertFalse(result)
        # retry는 최소 한 번은 호출되었어야 함
        self.assertGreaterEqual(mock_retry.call_count, 1)
        # 최종 실패 알림 1건 이상 생성 (admin 역할 사용자에게)
        self.assertTrue(
            Notification.objects.filter(
                title='마켓플레이스 배송정보 전송 최종 실패',
            ).exists()
        )

    def test_push_shipping_retry_increments_synclog_count(self):
        """retry 호출 시 가장 최근 PUSH SyncLog의 retry_count 증가 + last_retry_at 갱신"""
        from unittest.mock import patch
        from celery.exceptions import MaxRetriesExceededError
        from apps.marketplace.sync_service import PushShippingError
        from apps.marketplace import tasks as mp_tasks

        # 사전에 PUSH SyncLog 1건 생성 (push_shipping_info가 만든다고 가정)
        push_log = SyncLog.objects.create(
            direction=SyncLog.Direction.PUSH,
            started_at=timezone.now(),
            total_count=1,
        )
        self.assertEqual(push_log.retry_count, 0)
        self.assertIsNone(push_log.last_retry_at)

        with patch(
            'apps.marketplace.sync_service.push_shipping_info',
            side_effect=PushShippingError('일시 API 오류'),
        ):
            with patch.object(
                mp_tasks.push_shipping_async, 'retry',
                side_effect=MaxRetriesExceededError('retry limit'),
            ):
                mp_tasks.push_shipping_async.apply(args=[self.order.pk])

        push_log.refresh_from_db()
        self.assertEqual(push_log.retry_count, 1)
        self.assertIsNotNone(push_log.last_retry_at)
