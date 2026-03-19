"""
마켓플레이스 주문 동기화 서비스

API 클라이언트에서 조회한 원본 데이터를 MarketplaceOrder로 변환·저장합니다.
"""
import logging
from datetime import datetime

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .api_client import get_client
from .models import MarketplaceConfig, MarketplaceOrder, SyncLog

logger = logging.getLogger(__name__)


def sync_orders(config: MarketplaceConfig, user=None,
                from_date: datetime = None, to_date: datetime = None) -> SyncLog:
    """
    마켓플레이스 주문을 동기화합니다.

    Args:
        config: MarketplaceConfig instance
        user: 실행한 사용자
        from_date: 조회 시작일
        to_date: 조회 종료일

    Returns:
        SyncLog: 동기화 결과 로그
    """
    sync_log = SyncLog(
        direction=SyncLog.Direction.PULL,
        started_at=timezone.now(),
        created_by=user,
    )
    sync_log.save()

    client = get_client(config)
    if not client:
        sync_log.error_message = f'지원하지 않는 마켓플레이스: {config.shop_name}'
        sync_log.completed_at = timezone.now()
        sync_log.save(update_fields=['error_message', 'completed_at', 'updated_at'])
        return sync_log

    try:
        raw_orders = client.get_orders(from_date=from_date, to_date=to_date)
        sync_log.total_count = len(raw_orders)
        success = 0
        errors = 0
        error_messages = []

        for raw_order in raw_orders:
            try:
                normalized = client.normalize_order(raw_order)
                _upsert_order(normalized, config, user)
                success += 1
            except (ValueError, KeyError, TypeError) as e:
                errors += 1
                order_id = raw_order.get('store_order_id', 'unknown')
                error_messages.append(f'{order_id}: {str(e)}')
                logger.error('주문 동기화 실패 (%s): %s', order_id, e)

        sync_log.success_count = success
        sync_log.error_count = errors
        sync_log.error_message = '\n'.join(error_messages[:50])

    except (ConnectionError, OSError, ValueError) as e:
        sync_log.error_count = 1
        sync_log.error_message = f'동기화 중 오류 발생: {str(e)}'
        logger.exception('마켓플레이스 동기화 실패')

    sync_log.completed_at = timezone.now()
    sync_log.save(update_fields=[
        'total_count', 'success_count', 'error_count',
        'error_message', 'completed_at', 'updated_at',
    ])
    return sync_log


@transaction.atomic
def _upsert_order(data: dict, config: MarketplaceConfig, user=None):
    """주문 데이터를 생성하거나 업데이트합니다."""
    store_order_id = data.pop('store_order_id')
    ordered_at = data.pop('ordered_at', '')

    if isinstance(ordered_at, str) and ordered_at:
        ordered_at = parse_datetime(ordered_at) or timezone.now()
    elif not ordered_at:
        ordered_at = timezone.now()

    defaults = {
        **data,
        'ordered_at': ordered_at,
        'synced_at': timezone.now(),
    }

    order, created = MarketplaceOrder.all_objects.update_or_create(
        store_order_id=store_order_id,
        defaults=defaults,
    )

    if created and user:
        order.created_by = user
        order.save(update_fields=['created_by'])

    return order
