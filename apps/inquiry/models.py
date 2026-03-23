from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class InquiryChannel(BaseModel):
    name = models.CharField('채널명', max_length=50)
    icon = models.CharField('아이콘', max_length=50, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '문의채널'
        verbose_name_plural = '문의채널'

    def __str__(self):
        return self.name


class Inquiry(BaseModel):
    class Status(models.TextChoices):
        RECEIVED = 'RECEIVED', '접수'
        WAITING = 'WAITING', '답변대기'
        REPLIED = 'REPLIED', '답변완료'
        CLOSED = 'CLOSED', '종료'

    class Priority(models.TextChoices):
        LOW = 'LOW', '낮음'
        NORMAL = 'NORMAL', '보통'
        HIGH = 'HIGH', '높음'
        URGENT = 'URGENT', '긴급'

    channel = models.ForeignKey(
        InquiryChannel, verbose_name='채널',
        on_delete=models.PROTECT,
    )
    customer_name = models.CharField('고객명', max_length=100)
    customer_contact = models.CharField('연락처', max_length=100, blank=True)
    subject = models.CharField('제목', max_length=200)
    content = models.TextField('문의내용')
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.RECEIVED,
    )
    priority = models.CharField(
        '우선순위', max_length=10,
        choices=Priority.choices, default=Priority.NORMAL,
    )
    received_date = models.DateTimeField('접수일시')
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='담당자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='assigned_inquiries',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '문의'
        verbose_name_plural = '문의'
        ordering = ['-pk']
        indexes = [
            models.Index(fields=['status'], name='idx_inquiry_status'),
            models.Index(
                fields=['priority'], name='idx_inquiry_priority',
            ),
        ]

    def __str__(self):
        return f'[{self.get_status_display()}] {self.subject}'


class InquiryReply(BaseModel):
    inquiry = models.ForeignKey(
        Inquiry, verbose_name='문의',
        on_delete=models.CASCADE, related_name='replies',
    )
    content = models.TextField('답변내용')
    is_llm_generated = models.BooleanField('AI생성여부', default=False)
    replied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='답변자',
        null=True, on_delete=models.SET_NULL,
    )
    replied_at = models.DateTimeField('답변일시', auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '답변'
        verbose_name_plural = '답변'
        ordering = ['replied_at']

    def __str__(self):
        return f'{self.inquiry.subject} 답변'


class ReplyTemplate(BaseModel):
    category = models.CharField('카테고리', max_length=50)
    title = models.CharField('제목', max_length=200)
    content = models.TextField('답변내용')
    use_count = models.PositiveIntegerField('사용횟수', default=0)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '답변템플릿'
        verbose_name_plural = '답변템플릿'
        ordering = ['-use_count']

    def __str__(self):
        return f'[{self.category}] {self.title}'
