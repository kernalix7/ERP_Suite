import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.db.models import F, Sum, Count, Q, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncMonth
from django.views.generic import TemplateView

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
