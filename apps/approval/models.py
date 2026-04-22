from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel
from apps.core.storage import hashed_upload_path
from apps.core.utils import generate_document_number


class ApprovalRequest(BaseModel):
    """결재/품의 요청 — 그룹웨어 공용"""
    BUSINESS_KEY_FIELD = 'request_number'

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
        ASSET_DISPOSAL = 'ASSET_DISPOSAL', '자산처분'

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

    class ApprovalType(models.TextChoices):
        SEQUENTIAL = 'SEQUENTIAL', '직렬'
        PARALLEL_ALL = 'PARALLEL_ALL', '병렬(전원합의)'
        PARALLEL_ANY = 'PARALLEL_ANY', '병렬(1인결재)'

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
    approval_type = models.CharField(
        '결재방식', max_length=20,
        choices=ApprovalType.choices, default=ApprovalType.SEQUENTIAL,
        help_text='직렬 / 병렬(전원합의) / 병렬(1인결재)',
    )

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
        SKIPPED = 'SKIPPED', '건너뜀'

    class ParallelMode(models.TextChoices):
        SEQUENTIAL = 'SEQUENTIAL', '직렬'
        ALL = 'ALL', '전원합의'
        ANY = 'ANY', '1인결재'

    request = models.ForeignKey(
        ApprovalRequest, verbose_name='결재요청',
        on_delete=models.CASCADE, related_name='steps',
    )
    step_order = models.PositiveIntegerField('단계순서')
    approver = models.ForeignKey(
        'accounts.User', verbose_name='결재자',
        on_delete=models.PROTECT, related_name='approval_steps',
    )
    parallel_mode = models.CharField(
        '병렬모드', max_length=20,
        choices=ParallelMode.choices, default=ParallelMode.SEQUENTIAL,
        help_text='같은 단계에 다중 결재자일 때의 합의 방식',
    )
    delegated_from = models.ForeignKey(
        'accounts.User', verbose_name='원결재자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='steps_delegated_to_me',
        help_text='위임으로 치환된 경우 원래 결재자',
    )
    delegation = models.ForeignKey(
        'approval.ApprovalDelegation', verbose_name='위임정보',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='steps_created',
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
        ordering = ['step_order', 'pk']

    def __str__(self):
        return f'{self.request.request_number} - {self.step_order}단계 ({self.approver})'


class ApprovalLineTemplate(BaseModel):
    """결재선 템플릿 — 자주 사용하는 결재 흐름을 미리 저장"""
    name = models.CharField('템플릿명', max_length=100)
    description = models.TextField('설명', blank=True)
    # steps 예시:
    # [{"approver_id": 1, "role": "팀장", "order": 1, "mode": "SEQUENTIAL"},
    #  {"approver_id": 5, "order": 2, "mode": "ALL"},
    #  {"approver_id": 7, "order": 2, "mode": "ALL"}]
    steps = models.JSONField('결재 단계', default=list)
    is_default = models.BooleanField('기본 템플릿', default=False)
    # 조건부 자동 적용 규칙:
    # {"category": ["PURCHASE","EXPENSE"], "amount_min": 0, "amount_max": 999999,
    #  "department_ids": [3,4]}
    condition = models.JSONField('자동적용 조건', default=dict, blank=True)
    auto_apply = models.BooleanField(
        '자동적용', default=False,
        help_text='기안 생성 시 condition 매칭 템플릿을 자동 적용',
    )
    priority = models.PositiveIntegerField(
        '우선순위', default=0,
        help_text='높을수록 우선. 여러 템플릿이 매칭되면 우선순위 높은 것부터 1건 사용',
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '결재선 템플릿'
        verbose_name_plural = '결재선 템플릿'
        ordering = ['-priority', '-is_default', 'name']

    def __str__(self):
        return self.name


class ApprovalDelegation(BaseModel):
    """결재 위임 — 부재 시 대리자에게 결재권 위임"""
    delegator = models.ForeignKey(
        'accounts.User', verbose_name='위임자',
        on_delete=models.PROTECT, related_name='delegations_given',
    )
    delegate = models.ForeignKey(
        'accounts.User', verbose_name='대리자',
        on_delete=models.PROTECT, related_name='delegations_received',
    )
    start_date = models.DateField('위임 시작일')
    end_date = models.DateField('위임 종료일')
    reason = models.TextField('위임 사유', blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '결재 위임'
        verbose_name_plural = '결재 위임'
        ordering = ['-start_date']

    def __str__(self):
        return f'{self.delegator} → {self.delegate} ({self.start_date}~{self.end_date})'

    @classmethod
    def get_active_delegate(cls, user, date=None):
        """특정 날짜 기준 활성 대리자 반환 (없으면 None)"""
        from django.utils import timezone
        if date is None:
            date = timezone.localdate()
        delegation = cls.objects.filter(
            delegator=user,
            is_active=True,
            start_date__lte=date,
            end_date__gte=date,
        ).first()
        return delegation.delegate if delegation else None


class ApprovalAttachment(BaseModel):
    """결재 첨부파일"""
    request = models.ForeignKey(
        ApprovalRequest, verbose_name='결재요청',
        on_delete=models.CASCADE, related_name='attachments',
    )
    file = models.FileField('파일', upload_to=hashed_upload_path('approval/attachments'))
    original_name = models.CharField('원본파일명', max_length=255)

    class Meta:
        verbose_name = '결재 첨부파일'
        verbose_name_plural = '결재 첨부파일'
        ordering = ['pk']

    def __str__(self):
        return self.original_name
