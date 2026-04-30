"""마켓플레이스 비동기 태스크 — 배송정보 PUSH 재시도 등."""
import logging

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def push_shipping_async(self, marketplace_order_id: int) -> bool:
    """배송정보 PUSH를 비동기로 실행하고 일시 실패 시 지수 백오프로 재시도.

    재시도 간격: 60s → 120s → 240s. 3회 재시도 후 최종 실패하면 운영자에게 알림.
    """
    from .models import MarketplaceOrder
    from .sync_service import push_shipping_info, PushShippingError

    order = MarketplaceOrder.all_objects.filter(
        pk=marketplace_order_id, is_active=True,
    ).first()
    if not order:
        logger.warning('push_shipping_async: 주문 없음 (id=%s)', marketplace_order_id)
        return False

    try:
        success = push_shipping_info(order, raise_on_failure=True)
    except PushShippingError as exc:
        retries = self.request.retries
        try:
            countdown = 60 * (2 ** retries)
            raise self.retry(exc=exc, countdown=countdown)
        except MaxRetriesExceededError:
            logger.error(
                '배송정보 PUSH 최종 실패: %s (재시도 %d회 모두 실패) — %s',
                order.store_order_id, self.max_retries, exc,
            )
            _notify_push_shipping_failure(order, str(exc))
            return False

    if success:
        from .models import MarketplaceOrder as _MO
        _MO.objects.filter(pk=order.pk).update(status=_MO.Status.SHIPPED)
    return success


def _notify_push_shipping_failure(marketplace_order, reason: str) -> None:
    """관리자/매니저에게 배송정보 PUSH 최종 실패 알림 발송."""
    try:
        from apps.core.notification import create_notification
        title = '마켓플레이스 배송정보 전송 최종 실패'
        message = (
            f'주문번호 {marketplace_order.store_order_id} '
            f'({marketplace_order.platform_product_order_id}) '
            f'재시도 모두 실패: {reason}'
        )
        create_notification(
            users='admin', title=title, message=message, noti_type='SYSTEM',
        )
        create_notification(
            users='manager', title=title, message=message, noti_type='SYSTEM',
        )
    except Exception:
        logger.exception('push_shipping 최종 실패 알림 생성 실패')
