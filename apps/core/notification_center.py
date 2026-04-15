"""알림센터 확장 모델 — 멀티채널 알림 + 사용자 설정"""
from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class NotificationChannel(BaseModel):
    """알림 채널"""

    class ChannelType(models.TextChoices):
        EMAIL = 'EMAIL', '이메일'
        SMS = 'SMS', 'SMS'
        KAKAO = 'KAKAO', '카카오톡'
        PUSH = 'PUSH', '푸시알림'
        WEBHOOK = 'WEBHOOK', '웹훅'

    name = models.CharField('채널명', max_length=100)
    channel_type = models.CharField(
        '채널유형', max_length=10, choices=ChannelType.choices,
    )
    config = models.JSONField(
        '채널설정', default=dict, blank=True,
        help_text='api_key, sender, template 등',
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '알림채널'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.name} ({self.get_channel_type_display()})'


class NotificationTemplate(BaseModel):
    """알림 템플릿"""

    name = models.CharField('템플릿명', max_length=200)
    code = models.CharField('템플릿코드', max_length=100, unique=True)
    channel = models.ForeignKey(
        NotificationChannel, on_delete=models.CASCADE,
        related_name='templates', verbose_name='채널',
    )
    subject_template = models.CharField('제목 템플릿', max_length=500, blank=True)
    body_template = models.TextField('본문 템플릿')
    variables = models.JSONField(
        '변수목록', default=list, blank=True,
        help_text='템플릿에서 사용 가능한 변수 목록',
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '알림템플릿'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name

    def render(self, context=None):
        """변수 치환하여 제목/본문 생성"""
        ctx = context or {}
        subject = self.subject_template
        body = self.body_template
        for key, value in ctx.items():
            placeholder = '{' + key + '}'
            subject = subject.replace(placeholder, str(value))
            body = body.replace(placeholder, str(value))
        return subject, body


class NotificationPreference(BaseModel):
    """사용자별 알림 설정"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notification_preferences', verbose_name='사용자',
    )
    channel = models.ForeignKey(
        NotificationChannel, on_delete=models.CASCADE,
        related_name='preferences', verbose_name='채널',
    )
    event_type = models.CharField('이벤트유형', max_length=50)
    is_enabled = models.BooleanField('활성', default=True)
    quiet_hours_start = models.TimeField('방해금지 시작', null=True, blank=True)
    quiet_hours_end = models.TimeField('방해금지 종료', null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '알림설정'
        verbose_name_plural = verbose_name
        unique_together = ['user', 'channel', 'event_type']

    def __str__(self):
        return f'{self.user} - {self.channel} - {self.event_type}'


class NotificationLog(BaseModel):
    """알림 발송 로그"""

    class Status(models.TextChoices):
        PENDING = 'PENDING', '대기'
        SENT = 'SENT', '발송'
        DELIVERED = 'DELIVERED', '전달'
        FAILED = 'FAILED', '실패'
        READ = 'READ', '읽음'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notification_logs', verbose_name='사용자',
    )
    channel = models.ForeignKey(
        NotificationChannel, on_delete=models.SET_NULL,
        null=True, related_name='logs', verbose_name='채널',
    )
    template = models.ForeignKey(
        NotificationTemplate, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='logs', verbose_name='템플릿',
    )
    status = models.CharField(
        '상태', max_length=10, choices=Status.choices, default=Status.PENDING,
    )
    subject = models.CharField('제목', max_length=500, blank=True)
    body = models.TextField('본문', blank=True)
    sent_at = models.DateTimeField('발송일', null=True, blank=True)
    delivered_at = models.DateTimeField('전달일', null=True, blank=True)
    read_at = models.DateTimeField('읽음일', null=True, blank=True)
    error_message = models.TextField('오류메시지', blank=True)
    retry_count = models.IntegerField('재시도횟수', default=0)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '알림로그'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} - {self.get_status_display()} - {self.subject[:30]}'


class PushSubscription(BaseModel):
    """웹 푸시 구독 정보 (VAPID)"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='push_subscriptions', verbose_name='사용자',
    )
    endpoint = models.URLField('엔드포인트', max_length=500)
    p256dh_key = models.CharField('P256DH 키', max_length=200)
    auth_key = models.CharField('Auth 키', max_length=200)
    user_agent = models.CharField('브라우저', max_length=300, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '푸시구독'
        verbose_name_plural = verbose_name
        unique_together = ['user', 'endpoint']

    def __str__(self):
        return f'{self.user} - {self.endpoint[:50]}'
