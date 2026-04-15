import logging

from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)

_EMAIL_NOTIFY_TYPES_DEFAULT = 'APPROVAL,OVERDUE,STOCK_LOW,SLA_BREACH'


class Notification(models.Model):
    class NotiType(models.TextChoices):
        STOCK_LOW = 'STOCK_LOW', '재고부족'
        ORDER_NEW = 'ORDER_NEW', '신규주문'
        SERVICE_DUE = 'SERVICE_DUE', 'AS기한초과'
        PRODUCTION = 'PRODUCTION', '생산완료'
        SYSTEM = 'SYSTEM', '시스템'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notifications', verbose_name='사용자',
    )
    title = models.CharField('제목', max_length=200)
    message = models.TextField('내용')
    noti_type = models.CharField('유형', max_length=20, choices=NotiType.choices, default=NotiType.SYSTEM)
    is_read = models.BooleanField('읽음', default=False)
    link = models.CharField('링크', max_length=500, blank=True)
    created_at = models.DateTimeField('생성일', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '알림'
        verbose_name_plural = '알림'

    def __str__(self):
        return self.title


def _get_email_notify_types():
    """SystemConfig에서 이메일 발송 대상 알림 유형 목록 조회"""
    try:
        from apps.core.system_config import SystemConfig
        raw = SystemConfig.get_value('EMAIL', 'EMAIL_NOTIFY_TYPES', _EMAIL_NOTIFY_TYPES_DEFAULT)
        return [t.strip() for t in raw.split(',') if t.strip()]
    except Exception:
        return [t.strip() for t in _EMAIL_NOTIFY_TYPES_DEFAULT.split(',')]


def create_notification(users, title, message, noti_type='SYSTEM', link=''):
    """여러 사용자에게 알림 생성 + 실시간 WebSocket 전송 + 이메일 알림"""
    from apps.accounts.models import User
    if isinstance(users, str) and users == 'all':
        users = User.objects.filter(is_active=True)
    elif isinstance(users, str):
        users = User.objects.filter(role__in=[users], is_active=True)

    # QuerySet을 list로 평가 (이메일 루프에서 재사용하기 위함)
    users = list(users)

    notifications = []
    for user in users:
        notifications.append(Notification(
            user=user, title=title, message=message,
            noti_type=noti_type, link=link,
        ))
    Notification.objects.bulk_create(notifications)

    # 실시간 WebSocket 알림 전송
    notification_data = {
        'title': title,
        'message': message,
        'noti_type': noti_type,
        'link': link,
    }
    for user in users:
        send_realtime_notification(user.id, notification_data)

    # 이메일 알림 전송 (해당 유형이 EMAIL_NOTIFY_TYPES에 포함된 경우)
    email_notify_types = _get_email_notify_types()
    if noti_type in email_notify_types:
        _send_email_notifications(users, title, message)


def _send_email_notifications(users, title, message):
    """이메일 알림 일괄 발송 — 실패 시 예외 전파 금지"""
    try:
        from apps.core.email import send_notification_email
        for user in users:
            if not getattr(user, 'email', None):
                continue
            try:
                send_notification_email(user=user, subject=title, message=message)
            except Exception:
                logger.warning('이메일 알림 발송 실패 (user=%s)', getattr(user, 'username', user), exc_info=True)
    except Exception:
        logger.warning('이메일 알림 모듈 로딩 실패', exc_info=True)


def send_realtime_notification(user_id, notification_data):
    """특정 사용자에게 실시간 WebSocket 알림 전송"""
    try:
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            f'user_{user_id}',
            {
                'type': 'send_notification',
                'data': notification_data,
            }
        )
    except (OSError, ConnectionError, RuntimeError):
        logger.warning('실시간 알림 전송 실패 (user_id=%s)', user_id, exc_info=True)


def send_broadcast_notification(notification_data):
    """모든 접속 사용자에게 실시간 WebSocket 알림 전송"""
    try:
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            'broadcast',
            {
                'type': 'send_notification',
                'data': notification_data,
            }
        )
    except (OSError, ConnectionError, RuntimeError):
        logger.warning('브로드캐스트 알림 전송 실패', exc_info=True)
