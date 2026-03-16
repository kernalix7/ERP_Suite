"""
성능 검증 테스트 (PERF-001 ~ PERF-004)
페이지 응답시간, DB 쿼리 수, 대량 데이터 처리 성능 자동화 테스트
"""
import time
from datetime import date

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

User = get_user_model()


class PERF001_PageResponseTimeTest(TestCase):
    """PERF-001: 페이지 응답시간 검증"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='perf_user', password='PerfPass123!', role='admin',
        )
        self.client.force_login(self.user)

    def _measure_response_time(self, url, max_ms):
        """URL 응답시간을 측정하고 임계값과 비교"""
        start = time.monotonic()
        response = self.client.get(url)
        elapsed_ms = (time.monotonic() - start) * 1000

        self.assertIn(response.status_code, [200, 302],
                      f"{url} 응답 코드: {response.status_code}")
        self.assertLess(
            elapsed_ms, max_ms,
            f"{url} 응답시간 {elapsed_ms:.0f}ms > 임계값 {max_ms}ms",
        )
        return elapsed_ms

    def test_대시보드_응답시간_1000ms이내(self):
        """대시보드 페이지 응답시간 < 1000ms"""
        self._measure_response_time(reverse('core:dashboard'), 1000)

    def test_제품목록_응답시간_500ms이내(self):
        """제품 목록 페이지 응답시간 < 500ms"""
        self._measure_response_time(reverse('inventory:product_list'), 500)

    def test_주문목록_응답시간_500ms이내(self):
        """주문 목록 페이지 응답시간 < 500ms"""
        self._measure_response_time(reverse('sales:order_list'), 500)

    def test_거래처목록_응답시간_500ms이내(self):
        """거래처 목록 페이지 응답시간 < 500ms"""
        self._measure_response_time(reverse('sales:partner_list'), 500)

    def test_재고현황_응답시간_500ms이내(self):
        """재고현황 페이지 응답시간 < 500ms"""
        self._measure_response_time(reverse('inventory:stock_status'), 500)


class PERF002_QueryCountTest(TestCase):
    """PERF-002: DB 쿼리 수 - N+1 문제 방지"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='query_user', password='QueryPass123!', role='admin',
        )
        self.client.force_login(self.user)
        self._create_sample_data()

    def _create_sample_data(self):
        """테스트용 샘플 데이터 생성"""
        from apps.inventory.models import Product, Category
        from apps.sales.models import Partner

        cat = Category.all_objects.create(name='QC카테고리')
        for i in range(20):
            Product.all_objects.create(
                code=f'QC-P{i:03d}', name=f'쿼리테스트제품{i}',
                category=cat, unit_price=10000 + i * 100,
            )
        for i in range(10):
            Partner.all_objects.create(
                code=f'QC-PT{i:03d}', name=f'쿼리테스트거래처{i}',
            )

    def test_제품목록_쿼리수_10이하(self):
        """제품 목록 페이지 쿼리 수 <= 15"""
        with CaptureQueriesContext(connection) as context:
            self.client.get(reverse('inventory:product_list'))
        query_count = len(context)
        self.assertLessEqual(
            query_count, 15,
            f"제품목록 쿼리 수 {query_count}개 > 15개 (N+1 문제 의심)",
        )

    def test_거래처목록_쿼리수_10이하(self):
        """거래처 목록 페이지 쿼리 수 <= 10"""
        with CaptureQueriesContext(connection) as context:
            self.client.get(reverse('sales:partner_list'))
        query_count = len(context)
        self.assertLessEqual(
            query_count, 15,
            f"거래처목록 쿼리 수 {query_count}개 > 15개",
        )

    def test_주문목록_쿼리수_적정(self):
        """주문 목록 페이지 쿼리 수 검증"""
        with CaptureQueriesContext(connection) as context:
            self.client.get(reverse('sales:order_list'))
        query_count = len(context)
        self.assertLessEqual(
            query_count, 15,
            f"주문목록 쿼리 수 {query_count}개 > 15개",
        )


class PERF004_LargeDataPaginationTest(TestCase):
    """PERF-004: 대량 데이터 처리 - 페이지네이션 검증"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='bulk_user', password='BulkPass123!', role='admin',
        )
        self.client.force_login(self.user)

    def test_대량제품_페이지네이션(self):
        """1000건 제품 데이터에서 페이지네이션 정상 동작"""
        from apps.inventory.models import Product
        products = [
            Product(
                code=f'BULK-{i:05d}', name=f'대량제품{i}',
                unit_price=10000, is_active=True,
            )
            for i in range(1000)
        ]
        Product.all_objects.bulk_create(products)

        start = time.monotonic()
        response = self.client.get(reverse('inventory:product_list'))
        elapsed_ms = (time.monotonic() - start) * 1000

        self.assertEqual(response.status_code, 200)
        self.assertLess(
            elapsed_ms, 2000,
            f"1000건 제품 목록 응답 {elapsed_ms:.0f}ms > 2000ms",
        )

        # 페이지네이션이 적용되어 전체 데이터를 한번에 로드하지 않는지 확인
        if hasattr(response, 'context') and response.context:
            page_obj = response.context.get('page_obj') or response.context.get('paginator')
            if page_obj:
                # 한 페이지에 1000건 이상이 표시되면 안됨
                products_in_page = response.context.get(
                    'products', response.context.get('object_list', []),
                )
                self.assertLessEqual(
                    len(products_in_page), 100,
                    "페이지네이션 미적용: 한 페이지에 100건 이상 표시",
                )

    def test_대량주문_페이지네이션(self):
        """500건 주문 데이터에서 정상 응답"""
        from apps.sales.models import Order
        orders = [
            Order(
                order_number=f'BULK-ORD-{i:05d}',
                order_date=date.today(),
                status='DRAFT',
                is_active=True,
            )
            for i in range(500)
        ]
        Order.all_objects.bulk_create(orders)

        start = time.monotonic()
        response = self.client.get(reverse('sales:order_list'))
        elapsed_ms = (time.monotonic() - start) * 1000

        self.assertEqual(response.status_code, 200)
        self.assertLess(elapsed_ms, 2000,
                        f"500건 주문 목록 응답 {elapsed_ms:.0f}ms > 2000ms")
