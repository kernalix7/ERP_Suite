from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class ChatRoom(BaseModel):
    class RoomType(models.TextChoices):
        DIRECT = 'direct', '1:1 대화'
        GROUP = 'group', '그룹 대화'

    name = models.CharField('대화방 이름', max_length=100, blank=True)
    room_type = models.CharField(
        '유형',
        max_length=10,
        choices=RoomType.choices,
        default=RoomType.DIRECT,
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='ChatParticipant',
        related_name='chat_rooms',
        verbose_name='참여자',
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '대화방'
        verbose_name_plural = '대화방'
        ordering = ['-updated_at']

    def __str__(self):
        if self.name:
            return self.name
        names = self.participants.values_list('name', flat=True)
        return ', '.join(n or '(이름없음)' for n in names[:3]) or f'대화방 #{self.pk}'

    def get_display_name(self, user):
        """현재 사용자 기준으로 대화방 이름 반환"""
        if self.name:
            return self.name
        if self.room_type == self.RoomType.DIRECT:
            other = self.participants.exclude(pk=user.pk).first()
            return str(other) if other else '(알 수 없음)'
        names = list(
            self.participants.exclude(pk=user.pk)
            .values_list('name', flat=True)[:3]
        )
        return ', '.join(n or '(이름없음)' for n in names) or f'그룹 #{self.pk}'

    def get_last_message(self):
        return self.messages.order_by('-sent_at').first()

    def get_unread_count(self, user):
        participant = self.chatparticipant_set.filter(user=user).first()
        if not participant or not participant.last_read_at:
            return self.messages.count()
        return self.messages.filter(sent_at__gt=participant.last_read_at).count()


class ChatParticipant(models.Model):
    room = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        verbose_name='대화방',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='사용자',
    )
    joined_at = models.DateTimeField('참여일', auto_now_add=True)
    last_read_at = models.DateTimeField('마지막 읽은 시간', null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '대화 참여자'
        verbose_name_plural = '대화 참여자'
        unique_together = ['room', 'user']

    def __str__(self):
        return f'{self.user} @ {self.room}'


class Message(models.Model):
    class MessageType(models.TextChoices):
        TEXT = 'text', '텍스트'
        FILE = 'file', '파일'
        IMAGE = 'image', '이미지'

    room = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='대화방',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='sent_messages',
        verbose_name='보낸 사람',
    )
    content = models.TextField('내용')
    message_type = models.CharField(
        '메시지 유형',
        max_length=10,
        choices=MessageType.choices,
        default=MessageType.TEXT,
    )
    file = models.FileField(
        '첨부파일',
        upload_to='messenger/',
        null=True,
        blank=True,
    )
    sent_at = models.DateTimeField('전송 시간', auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '메시지'
        verbose_name_plural = '메시지'
        ordering = ['sent_at']

    def __str__(self):
        return f'{self.sender}: {self.content[:30]}'
