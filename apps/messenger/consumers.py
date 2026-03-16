import logging

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """실시간 채팅 WebSocket 컨슈머"""

    async def connect(self):
        self.user = self.scope['user']
        if self.user.is_anonymous:
            await self.close()
            return

        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group = f'chat_{self.room_id}'

        # 참여자 검증
        is_participant = await self.check_participant()
        if not is_participant:
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

        # 접속 시 읽음 시간 갱신
        await self.update_last_read()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group'):
            await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive_json(self, content):
        """클라이언트 메시지 처리"""
        msg_type = content.get('type')

        if msg_type == 'message':
            text = content.get('content', '').strip()
            if not text:
                return

            # DB에 메시지 저장
            message_data = await self.save_message(text)

            # 읽음 시간 갱신
            await self.update_last_read()

            # 그룹에 브로드캐스트
            await self.channel_layer.group_send(
                self.room_group,
                {
                    'type': 'chat_message',
                    'data': message_data,
                },
            )

        elif msg_type == 'read':
            await self.update_last_read()

    async def chat_message(self, event):
        """그룹 메시지 수신 -> 클라이언트 전송"""
        await self.send_json({
            'type': 'message',
            'data': event['data'],
        })

    @database_sync_to_async
    def check_participant(self):
        from apps.messenger.models import ChatParticipant
        return ChatParticipant.objects.filter(
            room_id=self.room_id, user=self.user
        ).exists()

    @database_sync_to_async
    def save_message(self, text):
        from apps.messenger.models import Message, ChatRoom
        room = ChatRoom.objects.get(pk=self.room_id)
        msg = Message.objects.create(
            room=room,
            sender=self.user,
            content=text,
            message_type='text',
        )
        # 대화방 updated_at 갱신 (목록 정렬용)
        room.save(update_fields=['updated_at'])

        return {
            'id': msg.pk,
            'sender_id': self.user.pk,
            'sender_name': self.user.name or self.user.username,
            'content': msg.content,
            'message_type': msg.message_type,
            'sent_at': msg.sent_at.strftime('%Y-%m-%d %H:%M'),
        }

    @database_sync_to_async
    def update_last_read(self):
        from apps.messenger.models import ChatParticipant
        ChatParticipant.objects.filter(
            room_id=self.room_id, user=self.user
        ).update(last_read_at=timezone.now())
