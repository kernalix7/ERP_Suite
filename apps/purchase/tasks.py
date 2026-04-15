import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(soft_time_limit=300, time_limit=360)
def check_overdue_purchase_orders():
    """입고 예정일 경과 PO 알림 -- 매일 오전 7시 30분 실행"""
    from django.utils import timezone

    from apps.core.notification import create_notification
    from apps.purchase.models import PurchaseOrder

    today = timezone.now().date()

    overdue_pos = PurchaseOrder.objects.filter(
        is_active=True,
        status__in=['CONFIRMED', 'PARTIAL_RECEIVED'],
        expected_date__lt=today,
    ).select_related('partner')

    alerts = []
    for po in overdue_pos:
        days_late = (today - po.expected_date).days
        alerts.append(
            f'{po.po_number} ({po.partner.name}): '
            f'{days_late}일 지연 (예정일: {po.expected_date})'
        )
        logger.warning(
            'PO %s is %d days late (expected: %s)',
            po.po_number, days_late, po.expected_date,
        )

    if alerts:
        create_notification(
            users='admin',
            title=f'입고 지연 발주 {len(alerts)}건',
            message='\n'.join(alerts[:20]),
            noti_type='OVERDUE',
        )

    return f'{len(alerts)} overdue POs'
