"""회계 공통 유틸 — 마감기간 검증, silent skip 알림"""
import logging

logger = logging.getLogger(__name__)


def validate_closing_period(target_date, raise_exception=True, notify_user=None, context=''):
    """마감된 회계기간이면 차단하거나 알림 발송

    Args:
        target_date: 검증할 날짜 (date)
        raise_exception: True면 ValidationError raise, False면 False 반환 + Notification
        notify_user: silent skip 시 알림 받을 사용자 (User). None이면 admin 전체에 발송
        context: 알림 본문에 들어갈 문맥 설명

    Returns:
        True — 마감되지 않음 (정상 처리 가능)
        False — 마감됨 + silent skip (notify_user에게 알림 발송)

    Raises:
        ValidationError — raise_exception=True이고 마감된 경우
    """
    from datetime import date, datetime
    from django.core.exceptions import ValidationError
    from apps.accounting.models import ClosingPeriod

    if target_date is None:
        return True

    # 문자열 날짜(ISO 'YYYY-MM-DD' 또는 'YYYY-MM-DDTHH:MM:SS') 또는 datetime 객체 정규화
    if isinstance(target_date, str):
        target_date = date.fromisoformat(target_date[:10])
    elif isinstance(target_date, datetime):
        target_date = target_date.date()

    is_closed = ClosingPeriod.objects.filter(
        year=target_date.year,
        month=target_date.month,
        is_closed=True,
        is_active=True,
    ).exists()
    if not is_closed:
        return True

    if raise_exception:
        raise ValidationError(
            f'{target_date.year}년 {target_date.month:02d}월은 마감된 기간입니다. '
            f'{context} 처리를 진행할 수 없습니다.'
        )

    _notify_silent_skip(target_date, notify_user, context)
    return False


def _notify_silent_skip(target_date, notify_user, context):
    """마감기간 자동처리 누락 알림 — 담당자 또는 관리자에게 전송"""
    try:
        from apps.core.notification import Notification, create_notification
    except Exception:
        logger.warning('Notification 모듈 로딩 실패 — silent skip 알림 스킵', exc_info=True)
        return

    title = f'[마감기간 자동처리 누락] {target_date.year}-{target_date.month:02d}'
    message = (
        f'{context}: {target_date.year}년 {target_date.month:02d}월은 마감되어 '
        f'자동 전표/재무 처리를 건너뛰었습니다. 수동으로 이관 또는 역월 처리 필요.'
    )
    try:
        if notify_user is not None and getattr(notify_user, 'pk', None):
            Notification.objects.create(
                user=notify_user,
                title=title,
                message=message,
                noti_type=Notification.NotiType.SYSTEM,
            )
        else:
            create_notification('admin', title, message, noti_type='SYSTEM')
    except Exception:
        logger.warning(
            'silent skip 알림 발송 실패 (user=%s, context=%s)',
            getattr(notify_user, 'username', None), context,
            exc_info=True,
        )

    logger.warning(
        'ClosingPeriod silent skip — %s (target=%s-%02d)',
        context, target_date.year, target_date.month,
    )
