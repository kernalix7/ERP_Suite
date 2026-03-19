import logging

from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)


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


def create_notification(users, title, message, noti_type='SYSTEM', link=''):
    """여러 사용자에게 알림 생성 + 실시간 WebSocket 전송"""
    from apps.accounts.models import User
    if isinstance(users, str) and users == 'all':
        users = User.objects.filter(is_active=True)
    elif isinstance(users, str):
        users = User.objects.filter(role__in=[users], is_active=True)

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
