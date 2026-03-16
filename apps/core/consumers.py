import logging

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """실시간 알림 WebSocket 컨슈머"""

    async def connect(self):
        self.user = self.scope['user']
        if self.user.is_anonymous:
            await self.close()
            return

        self.user_group = f'user_{self.user.id}'
        self.broadcast_group = 'broadcast'

        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.channel_layer.group_add(self.broadcast_group, self.channel_name)
        await self.accept()

        # 접속 시 읽지 않은 알림 개수 전송
        unread_count = await self.get_unread_count()
        await self.send_json({
            'type': 'unread_count',
            'count': unread_count,
        })

    async def disconnect(self, close_code):
        if hasattr(self, 'user_group'):
            await self.channel_layer.group_discard(self.user_group, self.channel_name)
            await self.channel_layer.group_discard(self.broadcast_group, self.channel_name)

    async def receive_json(self, content):
        """클라이언트 메시지 처리 (읽음 처리 등)"""
        action = content.get('action')

        if action == 'mark_read':
            notification_id = content.get('id')
            if notification_id:
                await self.mark_notification_read(notification_id)
                unread_count = await self.get_unread_count()
                await self.send_json({
                    'type': 'unread_count',
                    'count': unread_count,
                })

        elif action == 'mark_all_read':
            await self.mark_all_notifications_read()
            await self.send_json({
                'type': 'unread_count',
                'count': 0,
            })

    async def send_notification(self, event):
        """그룹 메시지 수신 → 클라이언트 전송"""
        await self.send_json({
            'type': 'notification',
            'data': event['data'],
        })

    @database_sync_to_async
    def get_unread_count(self):
        from apps.core.notification import Notification
        return Notification.objects.filter(
            user=self.user, is_read=False
        ).count()

    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        from apps.core.notification import Notification
        Notification.objects.filter(
            id=notification_id, user=self.user
        ).update(is_read=True)

    @database_sync_to_async
    def mark_all_notifications_read(self):
        from apps.core.notification import Notification
        Notification.objects.filter(
            user=self.user, is_read=False
        ).update(is_read=True)
