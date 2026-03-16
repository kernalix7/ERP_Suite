"""
보고서 빌더 유틸리티

기간별 매출/생산/재고 비교 분석 보고서를 생성합니다.
"""
from datetime import date, timedelta

from django.db.models import Sum, Count, Avg, Q
from django.db.models.functions import TruncMonth


def get_sales_report(start_date, end_date):
    """기간별 매출 보고서"""
    from apps.sales.models import Order

    orders = Order.objects.filter(
        order_date__gte=start_date,
        order_date__lte=end_date,
        status__in=['CONFIRMED', 'SHIPPED', 'DELIVERED'],
    )

    monthly = (
        orders
        .annotate(month=TruncMonth('order_date'))
        .values('month')
        .annotate(
            count=Count('id'),
            revenue=Sum('total_amount'),
            tax=Sum('tax_total'),
            total=Sum('grand_total'),
        )
        .order_by('month')
    )

    summary = orders.aggregate(
        total_count=Count('id'),
        total_revenue=Sum('total_amount'),
        total_tax=Sum('tax_total'),
        total_grand=Sum('grand_total'),
        avg_order=Avg('total_amount'),
    )

    return {
        'monthly': list(monthly),
        'summary': summary,
        'period': {'start': start_date, 'end': end_date},
    }


def get_production_report(start_date, end_date):
    """기간별 생산 보고서"""
    from apps.production.models import ProductionRecord, ProductionPlan

    records = ProductionRecord.objects.filter(
        record_date__gte=start_date,
        record_date__lte=end_date,
    )

    monthly = (
        records
        .annotate(month=TruncMonth('record_date'))
        .values('month')
        .annotate(
            good_qty=Sum('good_quantity'),
            defect_qty=Sum('defect_quantity'),
        )
        .order_by('month')
    )

    summary = records.aggregate(
        total_good=Sum('good_quantity'),
        total_defect=Sum('defect_quantity'),
    )

    total = (summary['total_good'] or 0) + (summary['total_defect'] or 0)
    summary['defect_rate'] = (
        round((summary['total_defect'] or 0) / total * 100, 1)
        if total > 0 else 0
    )

    plans = ProductionPlan.objects.filter(
        planned_start__gte=start_date,
        planned_start__lte=end_date,
    ).aggregate(
        total_plans=Count('id'),
        completed=Count('id', filter=Q(status='COMPLETED')),
    )
    summary['plan_completion_rate'] = (
        round(plans['completed'] / plans['total_plans'] * 100, 1)
        if plans['total_plans'] > 0 else 0
    )

    return {
        'monthly': list(monthly),
        'summary': summary,
        'period': {'start': start_date, 'end': end_date},
    }


def get_inventory_report():
    """현재 재고 현황 보고서"""
    from apps.inventory.models import Product

    by_type = (
        Product.objects
        .filter(is_active=True)
        .values('product_type')
        .annotate(
            count=Count('id'),
            total_stock=Sum('current_stock'),
            total_value=Sum('current_stock') * Avg('cost_price'),
        )
        .order_by('product_type')
    )

    low_stock = Product.objects.filter(
        is_active=True,
        current_stock__lt=models_F('safety_stock'),
    ).count()

    return {
        'by_type': list(by_type),
        'low_stock_count': low_stock,
    }


def models_F(field):
    """F() expression helper"""
    from django.db.models import F
    return F(field)
