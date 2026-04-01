import json
import logging
from datetime import date, timedelta
from decimal import Decimal

import requests
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.db import IntegrityError
from django.db.models import F, Sum, Count, Q, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncMonth
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from apps.core.mixins import AdminRequiredMixin

logger = logging.getLogger(__name__)

DASHBOARD_CHART_CACHE_TTL = 300  # 5분


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()

        # 재고 부족 품목
        from apps.inventory.models import Product
        products = Product.objects.filter(product_type='FINISHED')
        low_stock = products.filter(
            current_stock__lt=F('safety_stock'),
        ).select_related('category')
        context['low_stock_products'] = low_stock
        context['total_products'] = products.count()

        # 금일 주문
        from apps.sales.models import Order, OrderItem, Shipment
        today_orders = Order.objects.filter(order_date=today)
        context['today_order_count'] = today_orders.count()
        context['today_order_amount'] = today_orders.aggregate(
            total=Sum('total_amount')
        )['total'] or 0

        # 진행중 생산
        from apps.production.models import WorkOrder
        context['active_work_orders'] = WorkOrder.objects.filter(
            status__in=['PENDING', 'IN_PROGRESS']
        ).count()

        # 미처리 AS
        from apps.service.models import ServiceRequest
        context['open_service_requests'] = ServiceRequest.objects.filter(
            status__in=['RECEIVED', 'INSPECTING', 'REPAIRING']
        ).count()

        # 최근 주문 5건
        context['recent_orders'] = Order.objects.select_related(
            'partner', 'customer'
        ).all()[:5]

        # 최근 AS 5건
        context['recent_services'] = ServiceRequest.objects.select_related(
            'product', 'customer'
        ).all()[:5]

        # 재무 KPI
        this_month_orders = Order.objects.filter(
            order_date__year=today.year, order_date__month=today.month,
            status__in=['CONFIRMED', 'SHIPPED', 'DELIVERED'],
        )
        context['month_revenue'] = this_month_orders.aggregate(
            total=Sum('total_amount')
        )['total'] or 0

        from apps.accounting.models import FixedCost
        context['month_fixed_cost'] = FixedCost.objects.filter(
            month__year=today.year, month__month=today.month,
        ).aggregate(total=Sum('amount'))['total'] or 0

        from apps.investment.models import Investor, Investment
        context['total_invested'] = Investment.objects.aggregate(
            total=Sum('amount')
        )['total'] or 0
        context['investor_count'] = Investor.objects.count()

        # ── 재고 회전율 KPI ───────────────────────────
        twelve_months_ago = today - timedelta(days=365)
        # COGS: 최근 12개월 출고된 OrderItem의 (quantity * cost_price) 합계
        cogs = OrderItem.objects.filter(
            order__status__in=['SHIPPED', 'DELIVERED'],
            order__order_date__gte=twelve_months_ago,
            is_active=True,
        ).aggregate(
            total=Sum(
                ExpressionWrapper(
                    F('quantity') * F('cost_price'),
                    output_field=DecimalField(max_digits=20, decimal_places=0),
                )
            )
        )['total'] or Decimal('0')

        # 평균재고금액: 활성 제품의 (current_stock * cost_price) 합계
        avg_inventory = Product.objects.filter(
            is_active=True,
        ).aggregate(
            total=Sum(
                ExpressionWrapper(
                    F('current_stock') * F('cost_price'),
                    output_field=DecimalField(max_digits=20, decimal_places=0),
                )
            )
        )['total'] or Decimal('0')

        if avg_inventory > 0:
            context['inventory_turnover'] = round(
                float(cogs) / float(avg_inventory), 2
            )
        else:
            context['inventory_turnover'] = 0

        # ── 납기 준수율 KPI ───────────────────────────
        # 배송 약속일(Order.delivery_date) vs 실제 출고일(Shipment.shipped_date)
        shipped_orders = Shipment.objects.filter(
            is_active=True,
            shipped_date__isnull=False,
            order__delivery_date__isnull=False,
        ).select_related('order')

        total_shipments = shipped_orders.count()
        if total_shipments > 0:
            on_time = shipped_orders.filter(
                shipped_date__lte=F('order__delivery_date')
            ).count()
            context['delivery_compliance_rate'] = round(
                on_time / total_shipments * 100, 1
            )
        else:
            context['delivery_compliance_rate'] = 0
        context['delivery_total_shipments'] = total_shipments

        # ── 계좌 잔액 (대시보드 표시 설정된 계좌) ────────
        from apps.accounting.models import BankAccount
        context['dashboard_accounts'] = BankAccount.objects.filter(
            is_active=True, show_on_dashboard=True,
        ).order_by('-is_default', 'name')
        context['dashboard_accounts_total'] = sum(
            a.balance for a in context['dashboard_accounts']
        )

        # ── Chart data (캐시 적용) ───────────────────────────
        chart_data = cache.get('dashboard_chart_data')
        if chart_data is None:
            chart_data = self._build_chart_data(today, Order, Product)
            cache.set(
                'dashboard_chart_data',
                chart_data,
                DASHBOARD_CHART_CACHE_TTL,
            )
        context.update(chart_data)

        return context

    @staticmethod
    def _build_chart_data(today, Order, Product):
        """차트 데이터 생성 (캐시 미스 시 호출)"""
        data = {}
        six_months_ago = today.replace(day=1) - timedelta(days=150)
        six_months_ago = six_months_ago.replace(day=1)

        # 1) 월별 매출 추이 (6개월)
        monthly_revenue_qs = (
            Order.objects
            .filter(
                order_date__gte=six_months_ago,
                status__in=['CONFIRMED', 'SHIPPED', 'DELIVERED'],
            )
            .annotate(month=TruncMonth('order_date'))
            .values('month')
            .annotate(total=Sum('total_amount'))
            .order_by('month')
        )
        revenue_labels = []
        revenue_data = []
        for row in monthly_revenue_qs:
            revenue_labels.append(row['month'].strftime('%Y-%m'))
            revenue_data.append(int(row['total'] or 0))
        data['chart_revenue_labels'] = json.dumps(revenue_labels)
        data['chart_revenue_data'] = json.dumps(revenue_data)

        # 2) 월별 생산량 추이 (6개월)
        from apps.production.models import ProductionRecord
        monthly_production_qs = (
            ProductionRecord.objects
            .filter(record_date__gte=six_months_ago)
            .annotate(month=TruncMonth('record_date'))
            .values('month')
            .annotate(total=Sum('good_quantity'))
            .order_by('month')
        )
        production_labels = []
        production_data = []
        for row in monthly_production_qs:
            production_labels.append(
                row['month'].strftime('%Y-%m')
            )
            production_data.append(int(row['total'] or 0))
        data['chart_production_labels'] = json.dumps(
            production_labels
        )
        data['chart_production_data'] = json.dumps(production_data)

        # 3) 제품유형별 재고 비율
        stock_by_type = (
            Product.objects
            .filter(is_active=True)
            .values('product_type')
            .annotate(total_stock=Sum('current_stock'))
            .order_by('product_type')
        )
        type_map = {
            'RAW': '원자재',
            'SEMI': '반제품',
            'FINISHED': '완제품',
        }
        stock_labels = []
        stock_data = []
        for row in stock_by_type:
            stock_labels.append(
                type_map.get(row['product_type'], row['product_type'])
            )
            stock_data.append(int(row['total_stock'] or 0))
        data['chart_stock_labels'] = json.dumps(stock_labels)
        data['chart_stock_data'] = json.dumps(stock_data)

        # 4) 주문 상태 분포
        order_status_qs = (
            Order.objects
            .values('status')
            .annotate(count=Count('id'))
            .order_by('status')
        )
        status_display = dict(Order.Status.choices)
        order_status_labels = []
        order_status_data = []
        for row in order_status_qs:
            order_status_labels.append(
                status_display.get(row['status'], row['status'])
            )
            order_status_data.append(row['count'])
        data['chart_order_status_labels'] = json.dumps(
            order_status_labels
        )
        data['chart_order_status_data'] = json.dumps(
            order_status_data
        )

        return data


class SystemSettingsView(AdminRequiredMixin, TemplateView):
    """시스템 설정 통합 관리 화면"""
    template_name = 'core/system_settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.core.system_config import SystemConfig

        # 기본 설정값 초기화 (없는 것만 생성)
        SystemConfig.initialize_defaults()

        configs = SystemConfig.objects.all()

        # 카테고리별 그룹핑
        grouped = {}
        for cat_value, cat_label in SystemConfig.Category.choices:
            grouped[cat_value] = {
                'label': cat_label,
                'configs': list(configs.filter(category=cat_value)),
            }
        context['grouped_configs'] = grouped
        context['categories'] = SystemConfig.Category.choices
        context['value_types'] = SystemConfig.ValueType.choices
        context['active_tab'] = self.request.GET.get('tab', 'NTS')

        # 시스템 상태 정보
        context['system_info'] = self._get_system_info()
        return context

    @staticmethod
    def _get_system_info():
        """서버 상태 정보 수집"""
        import sys
        import django
        import os
        from django.conf import settings

        info = {
            'django_version': django.get_version(),
            'python_version': f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}',
        }

        # DB 크기
        db_path = settings.DATABASES['default'].get('NAME', '')
        if db_path and os.path.exists(str(db_path)):
            size_bytes = os.path.getsize(str(db_path))
            if size_bytes >= 1048576:
                info['db_size'] = f'{size_bytes / 1048576:.1f} MB'
            else:
                info['db_size'] = f'{size_bytes / 1024:.1f} KB'
        else:
            info['db_size'] = '-'

        # 사용자 수
        from apps.accounts.models import User
        info['user_count'] = User.objects.filter(is_active=True).count()

        # 직원 수
        try:
            from apps.hr.models import Employee
            info['employee_count'] = Employee.objects.filter(is_active=True).count()
        except Exception:
            info['employee_count'] = 0

        return info

    def post(self, request, *args, **kwargs):
        from apps.core.system_config import SystemConfig
        from apps.core.forms import SystemConfigForm

        action = request.POST.get('action')

        if action == 'save':
            config_id = request.POST.get('config_id')
            if config_id:
                instance = get_object_or_404(SystemConfig.all_objects, pk=config_id)
                form = SystemConfigForm(request.POST, instance=instance)
            else:
                form = SystemConfigForm(request.POST)

            if form.is_valid():
                config = form.save(commit=False)
                if not config.created_by_id:
                    config.created_by = request.user
                # secret 필드 수정 시 빈 value → 기존 값 유지
                if config_id and instance.is_secret and not request.POST.get('value'):
                    config.value = instance.value
                try:
                    config.save()
                    messages.success(request, f'설정이 저장되었습니다: {config.display_name}')
                except IntegrityError:
                    messages.error(request, '동일한 카테고리/설정키 조합이 이미 존재합니다.')
            else:
                messages.error(request, f'입력값을 확인해주세요: {form.errors.as_text()}')

        elif action == 'delete':
            config_id = request.POST.get('config_id')
            config = get_object_or_404(SystemConfig, pk=config_id)
            config.soft_delete()
            messages.success(request, f'설정이 삭제되었습니다: {config.display_name}')

        tab = request.POST.get('tab', 'NTS')
        return redirect(f"{request.path}?tab={tab}")


class RoleSwitchView(AdminRequiredMixin, View):
    """관리자 뷰 모드 전환 (세션 기반)"""

    def post(self, request, *args, **kwargs):
        view_mode = request.POST.get('view_mode', '')
        if view_mode in ('staff', 'manager', 'admin'):
            request.session['view_mode'] = view_mode
            label = {'staff': '사용자', 'manager': '매니저', 'admin': '관리자'}
            messages.info(request, f'{label[view_mode]} 뷰로 전환했습니다.')
        return redirect(request.META.get('HTTP_REFERER', '/'))


class SystemConfigTestView(AdminRequiredMixin, View):
    """시스템 설정 연결 테스트 API (AJAX)"""

    def post(self, request, *args, **kwargs):
        category = request.POST.get('category')

        if category == 'EMAIL':
            return self._test_email(request)
        elif category == 'NTS':
            return JsonResponse({
                'success': True,
                'message': '국세청 API 연결 테스트는 전자세금계산서 메뉴에서 수행할 수 있습니다.',
            })
        elif category == 'ADDRESS':
            return self._test_address()
        elif category == 'MARKETPLACE':
            return self._test_marketplace()
        elif category == 'SHIPPING':
            return self._test_shipping()
        elif category == 'AI':
            return self._test_ai()
        else:
            return JsonResponse({
                'success': False,
                'message': '해당 카테고리의 테스트는 지원되지 않습니다.',
            })

    @staticmethod
    def _test_email(request):
        from apps.core.system_config import SystemConfig
        host = SystemConfig.get_value('EMAIL', 'smtp_host')
        port = SystemConfig.get_value('EMAIL', 'smtp_port', '587')

        if not host:
            return JsonResponse({
                'success': False,
                'message': 'SMTP 호스트가 설정되지 않았습니다.',
            })

        try:
            import smtplib
            with smtplib.SMTP(host, int(port), timeout=5) as server:
                server.ehlo()
            return JsonResponse({
                'success': True,
                'message': f'SMTP 서버 연결 성공: {host}:{port}',
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'SMTP 연결 실패: {e}',
            })

    @staticmethod
    def _test_address():
        from apps.core.system_config import SystemConfig
        api_key = SystemConfig.get_value('ADDRESS', 'JUSO_API_KEY')
        if not api_key:
            return JsonResponse({
                'success': False,
                'message': '도로명주소 API 키가 설정되지 않았습니다.',
            })
        return JsonResponse({
            'success': True,
            'message': f'도로명주소 팝업 API 키 설정 확인 완료 (키 길이: {len(api_key)}자)',
        })

    @staticmethod
    def _test_marketplace():
        from apps.core.system_config import SystemConfig
        naver_id = SystemConfig.get_value('MARKETPLACE', 'naver_client_id')
        naver_secret = SystemConfig.get_value('MARKETPLACE', 'naver_client_secret')
        coupang_key = SystemConfig.get_value('MARKETPLACE', 'coupang_access_key')
        coupang_secret = SystemConfig.get_value('MARKETPLACE', 'coupang_secret_key')

        has_naver = bool(naver_id and naver_secret)
        has_coupang = bool(coupang_key and coupang_secret)

        if not has_naver and not has_coupang:
            return JsonResponse({
                'success': False,
                'message': '마켓플레이스 API 키가 설정되지 않았습니다. (네이버 또는 쿠팡)',
            })

        configured = []
        if has_naver:
            configured.append('네이버')
        if has_coupang:
            configured.append('쿠팡')

        return JsonResponse({
            'success': True,
            'message': f'마켓플레이스 API 설정 확인: {", ".join(configured)}',
        })

    @staticmethod
    def _test_shipping():
        from apps.core.system_config import SystemConfig
        carrier_key = SystemConfig.get_value('SHIPPING', 'default_carrier_api_key')
        tracking_url = SystemConfig.get_value('SHIPPING', 'tracking_api_url')

        if not carrier_key and not tracking_url:
            return JsonResponse({
                'success': False,
                'message': '배송/택배 API 설정이 되지 않았습니다. (API 키 또는 추적 URL)',
            })

        details = []
        if carrier_key:
            details.append('택배 API 키')
        if tracking_url:
            details.append('배송추적 URL')

        return JsonResponse({
            'success': True,
            'message': f'배송 API 설정 확인: {", ".join(details)}',
        })

    @staticmethod
    def _test_ai():
        from apps.core.system_config import SystemConfig
        api_key = SystemConfig.get_value('AI', 'anthropic_api_key')

        if not api_key:
            return JsonResponse({
                'success': False,
                'message': 'Anthropic API 키가 설정되지 않았습니다.',
            })

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            client.models.list(limit=1)
            return JsonResponse({
                'success': True,
                'message': 'Anthropic API 연결 성공',
            })
        except ImportError:
            return JsonResponse({
                'success': True,
                'message': 'Anthropic API 키 설정 확인 (라이브러리 미설치로 연결 테스트 생략)',
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Anthropic API 연결 실패: {e}',
            })


@method_decorator(csrf_exempt, name='dispatch')
class JusoPopupView(View):
    """도로명주소 팝업 API 중간 페이지

    GET: 인증 필요 (confmKey 노출 방지)
    POST: 인증 불필요 (juso.go.kr 콜백 — SameSite=Lax 쿠키가 cross-site POST에 안 붙음)
    COOP: unsafe-none 필수 — juso.go.kr 경유 후 window.opener 유지를 위해
    """

    def _set_coop(self, response):
        """Cross-Origin-Opener-Policy를 해제하여 window.opener 보존"""
        response['Cross-Origin-Opener-Policy'] = 'unsafe-none'
        return response

    def get(self, request):
        """팝업 최초 호출 -- confmKey 전달하여 juso.go.kr로 리다이렉트"""
        if not request.user.is_authenticated:
            return HttpResponseForbidden()
        from apps.core.system_config import SystemConfig
        confm_key = SystemConfig.get_value('ADDRESS', 'JUSO_API_KEY')
        response = render(request, 'core/juso_popup.html', {
            'confm_key': confm_key,
            'input_yn': 'N',
        })
        return self._set_coop(response)

    def post(self, request):
        """juso.go.kr에서 주소 선택 후 결과를 받는 콜백 (cross-site POST)"""
        response = render(request, 'core/juso_popup.html', {
            'input_yn': request.POST.get('inputYn', 'N'),
            'road_full_addr': request.POST.get('roadFullAddr', ''),
            'road_addr_part1': request.POST.get('roadAddrPart1', ''),
            'road_addr_part2': request.POST.get('roadAddrPart2', ''),
            'addr_detail': request.POST.get('addrDetail', ''),
            'jibun_addr': request.POST.get('jibunAddr', ''),
            'zip_no': request.POST.get('zipNo', ''),
            'bd_nm': request.POST.get('bdNm', ''),
            'si_nm': request.POST.get('siNm', ''),
            'sgg_nm': request.POST.get('sggNm', ''),
            'emd_nm': request.POST.get('emdNm', ''),
        })
        return self._set_coop(response)


class AddressSearchView(LoginRequiredMixin, View):
    """주소검색 프록시 뷰 (CORS 회피 + API키 보호)"""

    def get(self, request):
        query = request.GET.get('q', '').strip()
        search_type = request.GET.get('type', 'domestic')

        if not query or len(query) < 2:
            return JsonResponse({'results': [], 'error': False})

        if search_type == 'domestic':
            return self._search_domestic(query)
        return self._search_international(query)

    def _search_domestic(self, query):
        """행안부 도로명주소 API"""
        from apps.core.api_utils import create_retry_session, circuit_breakers

        cb = circuit_breakers['juso']
        if not cb.is_available:
            return JsonResponse({
                'results': [], 'error': True,
                'message': '주소검색 서비스 일시 중단',
            })

        try:
            from apps.core.system_config import SystemConfig
            api_key = SystemConfig.get_value('ADDRESS', 'JUSO_API_KEY')
        except Exception:
            api_key = ''

        if not api_key:
            return JsonResponse({
                'results': [], 'error': True,
                'message': 'API 키 미설정',
            })

        session = create_retry_session(retries=2, timeout=5)
        try:
            resp = session.get(
                'https://business.juso.go.kr/addrlink/addrLinkApi.do',
                params={
                    'confmKey': api_key,
                    'keyword': query,
                    'resultType': 'json',
                    'currentPage': '1',
                    'countPerPage': '10',
                },
                timeout=5,
            )
            resp.raise_for_status()
            data = resp.json()
            cb.record_success()

            common = data.get('results', {}).get('common', {})
            error_code = common.get('errorCode', '')
            if error_code != '0':
                return JsonResponse({
                    'results': [],
                    'error': True,
                    'message': common.get('errorMessage', '주소 검색 오류'),
                })

            juso_list = data.get('results', {}).get('juso') or []
            results = [
                {
                    'roadAddr': j.get('roadAddr', ''),
                    'jibunAddr': j.get('jibunAddr', ''),
                    'zipNo': j.get('zipNo', ''),
                    'bdNm': j.get('bdNm', ''),
                }
                for j in juso_list
            ]
            return JsonResponse({'results': results, 'error': False})
        except requests.RequestException:
            cb.record_failure()
            return JsonResponse({
                'results': [], 'error': True,
                'message': '주소검색 API 연결 실패',
            })

    def _search_international(self, query):
        """Nominatim (OpenStreetMap) API"""
        from apps.core.api_utils import create_retry_session, circuit_breakers

        cb = circuit_breakers['nominatim']
        if not cb.is_available:
            return JsonResponse({
                'results': [], 'error': True,
                'message': 'Address search temporarily unavailable',
            })

        session = create_retry_session(retries=2, timeout=5)
        try:
            resp = session.get(
                'https://nominatim.openstreetmap.org/search',
                params={
                    'q': query,
                    'format': 'json',
                    'addressdetails': '1',
                    'limit': '5',
                },
                headers={'User-Agent': 'ERP-Suite/1.0 (erp@example.com)'},
                timeout=5,
            )
            resp.raise_for_status()
            data = resp.json()
            cb.record_success()

            results = [
                {
                    'displayName': item.get('display_name', ''),
                    'address': item.get('address', {}),
                }
                for item in data
            ]
            return JsonResponse({'results': results, 'error': False})
        except requests.RequestException:
            cb.record_failure()
            return JsonResponse({
                'results': [], 'error': True,
                'message': 'Address search API connection failed',
            })
