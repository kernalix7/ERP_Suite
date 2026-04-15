from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel
from apps.core.utils import generate_document_number


class SLA(BaseModel):
    """서비스 수준 협약"""
    name = models.CharField('SLA명', max_length=100)
    response_time_hours = models.PositiveIntegerField('응답 시간(시간)', default=4)
    resolution_time_hours = models.PositiveIntegerField('해결 시간(시간)', default=24)
    escalation_time_hours = models.PositiveIntegerField('에스컬레이션 시간(시간)', default=8)

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'SLA'
        verbose_name_plural = 'SLA'
        ordering = ['name']

    def __str__(self):
        return self.name


class TicketCategory(BaseModel):
    """티켓 분류"""
    name = models.CharField('분류명', max_length=100)
    description = models.TextField('설명', blank=True)
    parent = models.ForeignKey(
        'self', verbose_name='상위 분류',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='children',
    )
    default_priority = models.CharField(
        '기본 우선순위', max_length=10,
        choices=[
            ('LOW', '낮음'),
            ('MEDIUM', '보통'),
            ('HIGH', '높음'),
            ('URGENT', '긴급'),
        ],
        default='MEDIUM',
    )
    default_sla = models.ForeignKey(
        SLA, verbose_name='기본 SLA',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='categories',
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '티켓 분류'
        verbose_name_plural = '티켓 분류'
        ordering = ['name']

    def __str__(self):
        return self.name


class Ticket(BaseModel):
    """헬프데스크 티켓"""
    BUSINESS_KEY_FIELD = 'ticket_number'

    class Priority(models.TextChoices):
        LOW = 'LOW', '낮음'
        MEDIUM = 'MEDIUM', '보통'
        HIGH = 'HIGH', '높음'
        URGENT = 'URGENT', '긴급'

    class Status(models.TextChoices):
        OPEN = 'OPEN', '접수'
        ASSIGNED = 'ASSIGNED', '배정'
        IN_PROGRESS = 'IN_PROGRESS', '처리중'
        WAITING = 'WAITING', '대기'
        RESOLVED = 'RESOLVED', '해결'
        CLOSED = 'CLOSED', '종료'

    class Channel(models.TextChoices):
        EMAIL = 'EMAIL', '이메일'
        PHONE = 'PHONE', '전화'
        WEB = 'WEB', '웹'
        CHAT = 'CHAT', '채팅'

    ticket_number = models.CharField('티켓번호', max_length=20, unique=True, blank=True)
    title = models.CharField('제목', max_length=200)
    description = models.TextField('내용')
    category = models.ForeignKey(
        TicketCategory, verbose_name='분류',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='tickets',
    )
    priority = models.CharField(
        '우선순위', max_length=10,
        choices=Priority.choices, default=Priority.MEDIUM,
    )
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.OPEN,
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='신고자',
        on_delete=models.PROTECT, related_name='reported_tickets',
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='담당자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='assigned_tickets',
    )
    sla = models.ForeignKey(
        SLA, verbose_name='SLA',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='tickets',
    )
    sla_response_due = models.DateTimeField('SLA 응답 기한', null=True, blank=True)
    sla_resolution_due = models.DateTimeField('SLA 해결 기한', null=True, blank=True)
    # TODO: SLA 위반 자동감지 — Celery 주기적 태스크로 sla_response_due/sla_resolution_due 초과 티켓 자동 마킹
    sla_breached = models.BooleanField('SLA 위반', default=False)
    channel = models.CharField(
        '접수 채널', max_length=10,
        choices=Channel.choices, default=Channel.WEB,
    )
    related_service = models.ForeignKey(
        'service.ServiceRequest', verbose_name='관련 AS',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='helpdesk_tickets',
    )
    related_order = models.ForeignKey(
        'sales.Order', verbose_name='관련 주문',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='helpdesk_tickets',
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '티켓'
        verbose_name_plural = '티켓'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status'], name='idx_ticket_status'),
            models.Index(fields=['priority'], name='idx_ticket_priority'),
            models.Index(fields=['assigned_to'], name='idx_ticket_assigned'),
        ]

    def __str__(self):
        return f'{self.ticket_number} - {self.title}'

    STATUS_TRANSITIONS = {
        'OPEN': ['ASSIGNED', 'IN_PROGRESS', 'CLOSED'],
        'ASSIGNED': ['IN_PROGRESS', 'WAITING', 'OPEN'],
        'IN_PROGRESS': ['WAITING', 'RESOLVED', 'OPEN'],
        'WAITING': ['IN_PROGRESS', 'RESOLVED'],
        'RESOLVED': ['CLOSED', 'IN_PROGRESS'],
        'CLOSED': [],
    }

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        if self.pk:
            old_status = Ticket.objects.filter(pk=self.pk).values_list('status', flat=True).first()
            if old_status and old_status != self.status:
                allowed = self.STATUS_TRANSITIONS.get(old_status, [])
                if self.status not in allowed:
                    old_label = dict(self.Status.choices).get(old_status, old_status)
                    new_label = dict(self.Status.choices).get(self.status, self.status)
                    raise ValidationError(
                        f'{old_label}에서 {new_label}(으)로 전이할 수 없습니다.'
                    )

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            self.ticket_number = generate_document_number(Ticket, 'ticket_number', 'TK')
        if not self.pk and self.category:
            if not self.sla:
                self.sla = self.category.default_sla
            if self.priority == self.Priority.MEDIUM and self.category.default_priority != self.Priority.MEDIUM:
                self.priority = self.category.default_priority
        super().save(*args, **kwargs)


class TicketComment(BaseModel):
    """티켓 코멘트"""
    ticket = models.ForeignKey(
        Ticket, verbose_name='티켓',
        on_delete=models.PROTECT, related_name='comments',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='작성자',
        on_delete=models.PROTECT, related_name='+',
    )
    content = models.TextField('내용')
    is_internal = models.BooleanField('내부 메모', default=False)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '티켓 코멘트'
        verbose_name_plural = '티켓 코멘트'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.ticket.ticket_number} 코멘트 #{self.pk}'


class TicketAttachment(BaseModel):
    """티켓 첨부파일"""
    ticket = models.ForeignKey(
        Ticket, verbose_name='티켓',
        on_delete=models.PROTECT, related_name='attachments',
    )
    file = models.FileField('첨부파일', upload_to='helpdesk/attachments/%Y/%m/')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='업로더',
        on_delete=models.PROTECT, related_name='+',
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '티켓 첨부파일'
        verbose_name_plural = '티켓 첨부파일'

    def __str__(self):
        return f'{self.ticket.ticket_number} - {self.file.name}'


class SLABreach(BaseModel):
    """SLA 위반 기록"""

    class BreachType(models.TextChoices):
        RESPONSE = 'RESPONSE', '응답시간 초과'
        RESOLUTION = 'RESOLUTION', '해결시간 초과'

    ticket = models.ForeignKey(
        Ticket, verbose_name='티켓',
        on_delete=models.PROTECT, related_name='sla_breaches',
    )
    sla = models.ForeignKey(
        SLA, verbose_name='SLA',
        on_delete=models.PROTECT, related_name='breaches',
    )
    breach_type = models.CharField(
        '위반 유형', max_length=10,
        choices=BreachType.choices,
    )
    breached_at = models.DateTimeField('위반 시각', auto_now_add=True)
    notified = models.BooleanField('알림 발송', default=False)

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'SLA 위반'
        verbose_name_plural = 'SLA 위반'
        ordering = ['-breached_at']
        unique_together = ['ticket', 'breach_type']

    def __str__(self):
        return f'{self.ticket.ticket_number} - {self.get_breach_type_display()}'


class EscalationRule(BaseModel):
    """에스컬레이션 규칙"""

    class ConditionType(models.TextChoices):
        RESPONSE_OVERDUE = 'RESPONSE_OVERDUE', '응답 지연'
        RESOLUTION_OVERDUE = 'RESOLUTION_OVERDUE', '해결 지연'

    category = models.ForeignKey(
        TicketCategory, verbose_name='분류',
        on_delete=models.PROTECT, related_name='escalation_rules',
    )
    condition_type = models.CharField(
        '조건', max_length=20,
        choices=ConditionType.choices,
    )
    escalate_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='에스컬레이션 대상',
        on_delete=models.PROTECT, related_name='+',
    )
    notify_method = models.CharField(
        '알림 방법', max_length=20,
        choices=[('EMAIL', '이메일'), ('NOTIFICATION', '시스템 알림'), ('BOTH', '이메일+시스템')],
        default='NOTIFICATION',
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '에스컬레이션 규칙'
        verbose_name_plural = '에스컬레이션 규칙'
        unique_together = ['category', 'condition_type']

    def __str__(self):
        return f'{self.category.name} - {self.get_condition_type_display()}'
