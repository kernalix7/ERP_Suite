import logging

from celery import shared_task
from django.db import models

logger = logging.getLogger(__name__)


@shared_task
def check_safety_stock():
    """안전재고 미달 제품 알림 -- 매일 오전 7시 실행"""
    from apps.inventory.models import Product
    from apps.core.notification import create_notification

    below_safety = Product.objects.filter(
        is_active=True,
        current_stock__lt=models.F('safety_stock'),
        safety_stock__gt=0,
    ).exclude(product_type__in=['SERVICE', 'INTANGIBLE'])

    alerts = []
    for product in below_safety:
        alerts.append(
            f'{product.code} {product.name}: '
            f'현재 {product.current_stock} / 안전재고 {product.safety_stock}'
        )

    if alerts:
        logger.warning('Safety stock alerts:\n%s', '\n'.join(alerts))
        create_notification(
            users='admin',
            title=f'안전재고 미달 {len(alerts)}건',
            message='\n'.join(alerts[:20]),
            noti_type='STOCK_LOW',
        )

    return f'{len(alerts)} products below safety stock'


@shared_task
def check_reorder_point():
    """재주문점 미달 제품 알림 -- 매일 오전 8시 실행"""
    from apps.inventory.models import Product
    from apps.core.notification import create_notification

    below_reorder = Product.objects.filter(
        is_active=True,
        reorder_point__gt=0,
        current_stock__lte=models.F('reorder_point'),
    ).exclude(product_type__in=['SERVICE', 'INTANGIBLE'])

    alerts = []
    for product in below_reorder:
        alerts.append(
            f'{product.code} {product.name}: '
            f'현재 {product.current_stock} / 재주문점 {product.reorder_point} '
            f'(리드타임 {product.lead_time_days}일)'
        )

    if alerts:
        logger.warning('Reorder point alerts:\n%s', '\n'.join(alerts))
        create_notification(
            users='manager',
            title=f'재주문점 미달 {len(alerts)}건 — 발주 검토 필요',
            message='\n'.join(alerts[:20]),
            noti_type='STOCK_LOW',
        )

    return f'{len(alerts)} products below reorder point'
