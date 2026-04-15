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
            if len(text) > 5000:
                await self.send_json({'type': 'error', 'message': '메시지가 너무 깁니다. (최대 5000자)'})
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

        elif msg_type == 'read_receipt':
            message_id = content.get('message_id')
            if message_id:
                await self.create_read_receipt(message_id)
                await self.channel_layer.group_send(
                    self.room_group,
                    {
                        'type': 'chat_read_receipt',
                        'message_id': message_id,
                        'user_id': self.user.pk,
                        'user_name': self.user.name or self.user.username,
                    },
                )

        elif msg_type == 'typing':
            is_typing = content.get('is_typing', False)
            await self.channel_layer.group_send(
                self.room_group,
                {
                    'type': 'chat_typing',
                    'user_id': self.user.pk,
                    'user_name': self.user.name or self.user.username,
                    'is_typing': is_typing,
                },
            )

    async def chat_message(self, event):
        """그룹 메시지 수신 -> 클라이언트 전송"""
        await self.send_json({
            'type': 'message',
            'data': event['data'],
        })

    async def chat_read_receipt(self, event):
        """읽음 영수증 브로드캐스트 -> 클라이언트 전송"""
        await self.send_json({
            'type': 'read_receipt',
            'message_id': event['message_id'],
            'user_id': event['user_id'],
            'user_name': event['user_name'],
        })

    async def chat_typing(self, event):
        """타이핑 표시 브로드캐스트 -> 클라이언트 전송 (본인 제외)"""
        if event['user_id'] == self.user.pk:
            return
        await self.send_json({
            'type': 'typing',
            'user_id': event['user_id'],
            'user_name': event['user_name'],
            'is_typing': event['is_typing'],
        })

    @database_sync_to_async
    def check_participant(self):
        from apps.messenger.models import ChatParticipant
        return ChatParticipant.objects.filter(
            room_id=self.room_id, user=self.user
        ).exists()

    @database_sync_to_async
    def save_message(self, text):
        import re
        from apps.messenger.models import Message, ChatRoom
        from apps.accounts.models import User
        from apps.core.notification import create_notification

        room = ChatRoom.objects.get(pk=self.room_id)
        msg = Message.objects.create(
            room=room,
            sender=self.user,
            content=text,
            message_type='text',
            created_by=self.user,
        )
        # 대화방 updated_at 갱신 (목록 정렬용)
        room.save(update_fields=['updated_at'])

        # @멘션 파싱 → 알림 생성
        mentioned_usernames = re.findall(r'@(\w+)', text)
        if mentioned_usernames:
            mentioned_users = list(
                User.objects.filter(
                    username__in=mentioned_usernames,
                    is_active=True,
                ).exclude(pk=self.user.pk)
            )
            if mentioned_users:
                sender_name = self.user.name or self.user.username
                create_notification(
                    mentioned_users,
                    '메신저 멘션',
                    f'{sender_name}님이 메시지에서 당신을 언급했습니다.',
                    noti_type='SYSTEM',
                    link=f'/messenger/{self.room_id}/',
                )

        return {
            'id': msg.pk,
            'sender_id': self.user.pk,
            'sender_name': self.user.name or self.user.username,
            'content': msg.content,
            'message_type': msg.message_type,
            'sent_at': msg.sent_at.strftime('%Y-%m-%d %H:%M'),
        }

    @database_sync_to_async
    def create_read_receipt(self, message_id):
        from apps.messenger.models import ReadReceipt, Message
        try:
            message = Message.objects.get(pk=message_id, room_id=self.room_id)
            ReadReceipt.objects.get_or_create(
                message=message,
                user=self.user,
                defaults={'created_by': self.user},
            )
        except Message.DoesNotExist:
            pass

    @database_sync_to_async
    def update_last_read(self):
        from apps.messenger.models import ChatParticipant
        ChatParticipant.objects.filter(
            room_id=self.room_id, user=self.user
        ).update(last_read_at=timezone.now())
