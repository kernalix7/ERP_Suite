from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel
from apps.core.utils import generate_document_number


class ApprovalRequest(BaseModel):
    """결재/품의 요청 — 그룹웨어 공용"""

    class DocCategory(models.TextChoices):
        PURCHASE = 'PURCHASE', '구매품의'
        EXPENSE = 'EXPENSE', '지출품의'
        BUDGET = 'BUDGET', '예산신청'
        CONTRACT = 'CONTRACT', '계약체결'
        GENERAL = 'GENERAL', '일반결재'
        LEAVE = 'LEAVE', '휴가신청'
        OVERTIME = 'OVERTIME', '초과근무'
        TRAVEL = 'TRAVEL', '출장신청'
        IT_REQUEST = 'IT_REQUEST', 'IT요청'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '작성중'
        SUBMITTED = 'SUBMITTED', '결재요청'
        APPROVED = 'APPROVED', '승인'
        REJECTED = 'REJECTED', '반려'
        CANCELLED = 'CANCELLED', '취소'

    class Urgency(models.TextChoices):
        NORMAL = 'NORMAL', '일반'
        URGENT = 'URGENT', '긴급'
        CRITICAL = 'CRITICAL', '특급'

    request_number = models.CharField('결재번호', max_length=30, unique=True, blank=True)
    category = models.CharField('문서종류', max_length=20, choices=DocCategory.choices)
    urgency = models.CharField(
        '긴급도', max_length=10,
        choices=Urgency.choices, default=Urgency.NORMAL,
    )
    title = models.CharField('제목', max_length=200)
    department = models.ForeignKey(
        'hr.Department', verbose_name='기안부서',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    purpose = models.TextField('품의목적/사유', blank=True, help_text='품의를 올리는 목적 또는 사유')
    content = models.TextField('세부내용')
    amount = models.DecimalField(
        '금액', max_digits=15, decimal_places=0,
        default=0, validators=[MinValueValidator(0)],
    )
    expected_date = models.DateField('희망일자', null=True, blank=True, help_text='집행/납품 희망일')
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.DRAFT,
    )
    requester = models.ForeignKey(
        'accounts.User', verbose_name='기안자',
        on_delete=models.PROTECT, related_name='approval_requests',
    )
    approver = models.ForeignKey(
        'accounts.User', verbose_name='결재자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='approval_assigned',
    )
    cooperator = models.ForeignKey(
        'accounts.User', verbose_name='협조자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='approval_cooperated',
    )
    submitted_at = models.DateTimeField('제출일', null=True, blank=True)
    approved_at = models.DateTimeField('결재일', null=True, blank=True)
    reject_reason = models.TextField('반려사유', blank=True)
    current_step = models.PositiveIntegerField('현재 결재단계', default=1)

    # GenericForeignKey — 결재 대상 문서 연결 (선택)
    content_type = models.ForeignKey(
        ContentType, verbose_name='문서유형',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    object_id = models.PositiveIntegerField('문서ID', null=True, blank=True)
    related_document = GenericForeignKey('content_type', 'object_id')

    history = HistoricalRecords()

    class Meta:
        verbose_name = '결재/품의'
        verbose_name_plural = '결재/품의'
        ordering = ['-request_number']
        indexes = [
            models.Index(fields=['status'], name='idx_appr_status'),
            models.Index(
                fields=['content_type', 'object_id'],
                name='idx_appr_gfk',
            ),
        ]

    def __str__(self):
        return f'{self.request_number} - {self.title}'

    def save(self, *args, **kwargs):
        if not self.request_number:
            self.request_number = generate_document_number(ApprovalRequest, 'request_number', 'AR')
        super().save(*args, **kwargs)


class ApprovalStep(BaseModel):
    """결재 단계"""

    class Status(models.TextChoices):
        PENDING = 'PENDING', '대기'
        APPROVED = 'APPROVED', '승인'
        REJECTED = 'REJECTED', '반려'

    request = models.ForeignKey(
        ApprovalRequest, verbose_name='결재요청',
        on_delete=models.CASCADE, related_name='steps',
    )
    step_order = models.PositiveIntegerField('단계순서')
    approver = models.ForeignKey(
        'accounts.User', verbose_name='결재자',
        on_delete=models.PROTECT, related_name='approval_steps',
    )
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.PENDING,
    )
    comment = models.TextField('의견', blank=True)
    acted_at = models.DateTimeField('처리일시', null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '결재단계'
        verbose_name_plural = '결재단계'
        ordering = ['step_order']
        unique_together = [['request', 'step_order']]

    def __str__(self):
        return f'{self.request.request_number} - {self.step_order}단계 ({self.approver})'


class ApprovalAttachment(BaseModel):
    """결재 첨부파일"""
    request = models.ForeignKey(
        ApprovalRequest, verbose_name='결재요청',
        on_delete=models.CASCADE, related_name='attachments',
    )
    file = models.FileField('파일', upload_to='approval/attachments/%Y/%m/')
    original_name = models.CharField('원본파일명', max_length=255)

    class Meta:
        verbose_name = '결재 첨부파일'
        verbose_name_plural = '결재 첨부파일'
        ordering = ['pk']

    def __str__(self):
        return self.original_name
