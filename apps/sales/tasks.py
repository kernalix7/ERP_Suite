import logging
from datetime import date

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def expire_quotations():
    """만료된 견적서를 EXPIRED 상태로 일괄 전환

    매일 실행하여 valid_until < today인 DRAFT/SENT/ACCEPTED 견적을 EXPIRED로 변경.
    """
    from apps.sales.models import Quotation

    today = date.today()
    expired_qs = Quotation.objects.filter(
        valid_until__lt=today,
        status__in=['DRAFT', 'SENT', 'ACCEPTED'],
        is_active=True,
    )
    count = 0
    for quote in expired_qs:
        quote.status = Quotation.Status.EXPIRED
        quote.save(update_fields=['status', 'updated_at'])
        count += 1

    if count:
        logger.info('Expired %d quotations (valid_until < %s)', count, today)
    return count


@shared_task
def auto_settle_marketplace_orders():
    """플랫폼 정산주기 도래분을 SalesSettlement 자동 생성.

    PlatformFinancialConfig.settlement_cycle_days 기준 — 주문일 + cycle_days 가 오늘 이전
    이고 아직 정산 안 된 주문을 플랫폼별로 묶어서 배치 처리.

    매주 월요일 04:00 실행 (config/celery.py BEAT 등록).
    """
    from datetime import timedelta
    from django.db import transaction
    from apps.sales.models import Order
    from apps.accounting.models import (
        SalesSettlement, SalesSettlementOrder, PlatformFinancialConfig,
    )

    today = date.today()
    settled_count = 0

    configs = PlatformFinancialConfig.objects.filter(
        is_enabled=True, is_active=True,
    ).exclude(settlement_cycle_days=0)

    for cfg in configs:
        due_before = today - timedelta(days=cfg.settlement_cycle_days)
        due_orders = list(Order.objects.filter(
            sales_channel=cfg.code,
            is_settled=False,
            is_active=True,
            order_date__lte=due_before,
            status__in=['DELIVERED', 'CLOSED'],
        ).exclude(
            settlement_items__is_active=True,
        ))
        if not due_orders:
            continue

        with transaction.atomic():
            settlement = SalesSettlement.objects.create(
                settlement_date=today,
                description=f'{cfg.name} 자동정산 ({due_before} 이전 주문)',
                total_revenue=sum(o.total_amount or 0 for o in due_orders),
                total_tax=sum(o.tax_total or 0 for o in due_orders),
                total_shipping=sum(o.shipping_charged or 0 for o in due_orders),
                total_platform_commission=sum(
                    o.platform_commission or 0 for o in due_orders
                ),
            )
            settlement.total_profit = (
                settlement.total_revenue - settlement.total_platform_commission
            )
            settlement.save(update_fields=['total_profit', 'updated_at'])

            for order in due_orders:
                SalesSettlementOrder.objects.create(
                    settlement=settlement,
                    order=order,
                    revenue=order.total_amount or 0,
                    tax=order.tax_total or 0,
                    shipping=order.shipping_charged or 0,
                    platform_commission=order.platform_commission or 0,
                )
                settled_count += 1

            Order.objects.filter(
                pk__in=[o.pk for o in due_orders],
            ).update(is_settled=True)

    if settled_count:
        logger.info(
            'Auto-settled %d marketplace orders (cycle-based batch)',
            settled_count,
        )
    return settled_count
