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
