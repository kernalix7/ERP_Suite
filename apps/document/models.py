from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel
from apps.core.utils import generate_document_number


class DocumentCategory(BaseModel):
    """문서 카테고리"""
    name = models.CharField('카테고리명', max_length=100)
    code = models.CharField('코드', max_length=20, unique=True)
    description = models.TextField('설명', blank=True)
    retention_years = models.PositiveIntegerField('보존기간(년)', default=5)
    parent = models.ForeignKey(
        'self', verbose_name='상위 카테고리',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='children',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '문서 카테고리'
        verbose_name_plural = '문서 카테고리'
        ordering = ['code']

    def __str__(self):
        return f'[{self.code}] {self.name}'


class Document(BaseModel):
    """전자문서"""
    BUSINESS_KEY_FIELD = 'document_number'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '초안'
        REVIEW = 'REVIEW', '검토중'
        APPROVED = 'APPROVED', '승인'
        PUBLISHED = 'PUBLISHED', '발행'
        ARCHIVED = 'ARCHIVED', '보관'
        OBSOLETE = 'OBSOLETE', '폐기'

    class AccessLevel(models.TextChoices):
        PUBLIC = 'PUBLIC', '공개'
        INTERNAL = 'INTERNAL', '사내'
        CONFIDENTIAL = 'CONFIDENTIAL', '대외비'
        SECRET = 'SECRET', '극비'

    document_number = models.CharField('문서번호', max_length=20, unique=True, blank=True)
    title = models.CharField('제목', max_length=200)
    category = models.ForeignKey(
        DocumentCategory, verbose_name='카테고리',
        on_delete=models.PROTECT, related_name='documents',
    )
    content_file = models.FileField('첨부파일', upload_to='documents/%Y/%m/', blank=True)
    file_type = models.CharField('파일유형', max_length=20, blank=True)
    version = models.PositiveIntegerField('버전', default=1)
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.DRAFT,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='소유자',
        on_delete=models.PROTECT, related_name='owned_documents',
    )
    department = models.ForeignKey(
        'hr.Department', verbose_name='부서',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='documents',
    )
    access_level = models.CharField(
        '접근등급', max_length=20,
        choices=AccessLevel.choices, default=AccessLevel.INTERNAL,
    )
    tags = models.JSONField('태그', default=list, blank=True)
    expiry_date = models.DateField('만료일', null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '전자문서'
        verbose_name_plural = '전자문서'
        ordering = ['-pk']
        indexes = [
            models.Index(fields=['status'], name='idx_document_status'),
            models.Index(fields=['category'], name='idx_document_category'),
        ]

    def __str__(self):
        return f'{self.document_number} - {self.title}'

    def save(self, *args, **kwargs):
        if not self.document_number:
            self.document_number = generate_document_number(
                Document, 'document_number', 'DOC',
            )
        super().save(*args, **kwargs)


class DocumentVersion(BaseModel):
    """문서 버전 이력"""
    document = models.ForeignKey(
        Document, verbose_name='문서',
        on_delete=models.PROTECT, related_name='versions',
    )
    version_number = models.PositiveIntegerField('버전번호')
    file = models.FileField('파일', upload_to='documents/versions/%Y/%m/')
    change_summary = models.TextField('변경 요약', blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '문서 버전'
        verbose_name_plural = '문서 버전'
        ordering = ['-version_number']
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'version_number'],
                name='uq_document_version',
            ),
        ]

    def __str__(self):
        return f'{self.document.title} v{self.version_number}'


class DocumentApproval(BaseModel):
    """문서 결재"""

    class Status(models.TextChoices):
        PENDING = 'PENDING', '대기'
        APPROVED = 'APPROVED', '승인'
        REJECTED = 'REJECTED', '반려'

    document = models.ForeignKey(
        Document, verbose_name='문서',
        on_delete=models.PROTECT, related_name='approvals',
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='결재자',
        on_delete=models.PROTECT, related_name='document_approvals',
    )
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.PENDING,
    )
    comment = models.TextField('의견', blank=True)
    approved_at = models.DateTimeField('결재일시', null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '문서 결재'
        verbose_name_plural = '문서 결재'
        ordering = ['pk']

    def __str__(self):
        return f'{self.document.title} - {self.approver} ({self.get_status_display()})'


class Contract(BaseModel):
    """계약"""
    BUSINESS_KEY_FIELD = 'contract_number'

    class ContractType(models.TextChoices):
        SALES = 'SALES', '매출계약'
        PURCHASE = 'PURCHASE', '매입계약'
        SERVICE = 'SERVICE', '용역계약'
        EMPLOYMENT = 'EMPLOYMENT', '고용계약'
        NDA = 'NDA', '비밀유지계약'
        LEASE = 'LEASE', '임대차계약'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '초안'
        ACTIVE = 'ACTIVE', '유효'
        EXPIRED = 'EXPIRED', '만료'
        TERMINATED = 'TERMINATED', '해지'

    contract_number = models.CharField('계약번호', max_length=20, unique=True, blank=True)
    title = models.CharField('계약명', max_length=200)
    contract_type = models.CharField(
        '계약유형', max_length=20,
        choices=ContractType.choices,
    )
    partner = models.ForeignKey(
        'sales.Partner', verbose_name='거래처',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='contracts',
    )
    start_date = models.DateField('시작일')
    end_date = models.DateField('종료일', null=True, blank=True)
    value = models.DecimalField(
        '계약금액', max_digits=15, decimal_places=0,
        default=0, validators=[MinValueValidator(0)],
    )
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.DRAFT,
    )
    auto_renew = models.BooleanField('자동갱신', default=False)
    renewal_notice_days = models.PositiveIntegerField('갱신 알림 일수', default=30)
    signed_file = models.FileField('계약서 파일', upload_to='contracts/%Y/%m/', blank=True)
    signed_date = models.DateField('체결일', null=True, blank=True)
    signed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='체결자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='signed_contracts',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '계약'
        verbose_name_plural = '계약'
        ordering = ['-pk']
        indexes = [
            models.Index(fields=['status'], name='idx_contract_status'),
            models.Index(fields=['end_date'], name='idx_contract_end_date'),
        ]

    def __str__(self):
        return f'{self.contract_number} - {self.title}'

    def save(self, *args, **kwargs):
        if not self.contract_number:
            self.contract_number = generate_document_number(
                Contract, 'contract_number', 'CT',
            )
        super().save(*args, **kwargs)


class ContractMilestone(BaseModel):
    """계약 마일스톤"""

    class Status(models.TextChoices):
        PENDING = 'PENDING', '예정'
        COMPLETED = 'COMPLETED', '완료'
        OVERDUE = 'OVERDUE', '지연'

    contract = models.ForeignKey(
        Contract, verbose_name='계약',
        on_delete=models.PROTECT, related_name='milestones',
    )
    title = models.CharField('마일스톤명', max_length=200)
    due_date = models.DateField('기한')
    amount = models.DecimalField(
        '금액', max_digits=15, decimal_places=0,
        default=0, validators=[MinValueValidator(0)],
    )
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.PENDING,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '계약 마일스톤'
        verbose_name_plural = '계약 마일스톤'
        ordering = ['due_date']

    def __str__(self):
        return f'{self.contract.title} - {self.title}'
