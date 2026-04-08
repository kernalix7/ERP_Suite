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
