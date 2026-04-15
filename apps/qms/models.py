from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class NonConformance(BaseModel):
    """부적합"""

    BUSINESS_KEY_FIELD = 'nc_number'

    class Source(models.TextChoices):
        INTERNAL = 'INTERNAL', '내부'
        SUPPLIER = 'SUPPLIER', '공급처'
        CUSTOMER = 'CUSTOMER', '고객'

    class Severity(models.TextChoices):
        MINOR = 'MINOR', '경미'
        MAJOR = 'MAJOR', '중대'
        CRITICAL = 'CRITICAL', '심각'

    class Status(models.TextChoices):
        OPEN = 'OPEN', '접수'
        INVESTIGATING = 'INVESTIGATING', '조사중'
        RESOLVED = 'RESOLVED', '해결'
        CLOSED = 'CLOSED', '종결'

    nc_number = models.CharField('부적합번호', max_length=20, unique=True, blank=True)
    title = models.CharField('제목', max_length=200)
    description = models.TextField('설명')
    source = models.CharField(
        '발생원', max_length=20,
        choices=Source.choices, default=Source.INTERNAL,
    )
    severity = models.CharField(
        '심각도', max_length=20,
        choices=Severity.choices, default=Severity.MINOR,
    )
    product = models.ForeignKey(
        'inventory.Product',
        verbose_name='관련품목',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='non_conformances',
    )
    detected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='발견자',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='detected_ncs',
    )
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.OPEN,
    )
    root_cause = models.TextField('근본원인', blank=True)
    corrective_action = models.TextField('시정조치', blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '부적합'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at'], name='idx_nc_status_date'),
            models.Index(fields=['severity', 'status'], name='idx_nc_severity_status'),
        ]

    def __str__(self):
        return f'[{self.nc_number}] {self.title}'

    def save(self, *args, **kwargs):
        if not self.nc_number:
            from apps.core.utils import generate_document_number
            self.nc_number = generate_document_number(
                NonConformance, 'nc_number', 'NC',
            )
        super().save(*args, **kwargs)


class CAPA(BaseModel):
    """시정/예방조치 (CAPA)"""

    BUSINESS_KEY_FIELD = 'capa_number'

    class Type(models.TextChoices):
        CORRECTIVE = 'CORRECTIVE', '시정조치'
        PREVENTIVE = 'PREVENTIVE', '예방조치'

    class Status(models.TextChoices):
        OPEN = 'OPEN', '접수'
        IN_PROGRESS = 'IN_PROGRESS', '진행중'
        VERIFIED = 'VERIFIED', '검증완료'
        CLOSED = 'CLOSED', '종결'

    capa_number = models.CharField('CAPA번호', max_length=20, unique=True, blank=True)
    nc = models.ForeignKey(
        NonConformance,
        verbose_name='관련 부적합',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='capas',
    )
    type = models.CharField(
        '유형', max_length=20,
        choices=Type.choices, default=Type.CORRECTIVE,
    )
    description = models.TextField('조치내용')
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='담당자',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_capas',
    )
    due_date = models.DateField('기한', null=True, blank=True)
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.OPEN,
    )
    effectiveness_check = models.TextField('유효성검증', blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'CAPA'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'due_date'], name='idx_capa_status_due'),
            models.Index(fields=['type', 'status'], name='idx_capa_type_status'),
        ]

    def __str__(self):
        return f'[{self.capa_number}] {self.get_type_display()}'

    def save(self, *args, **kwargs):
        if not self.capa_number:
            from apps.core.utils import generate_document_number
            self.capa_number = generate_document_number(
                CAPA, 'capa_number', 'CAPA',
            )
        super().save(*args, **kwargs)


class InternalAudit(BaseModel):
    """내부감사"""

    BUSINESS_KEY_FIELD = 'audit_number'

    class AuditType(models.TextChoices):
        SYSTEM = 'SYSTEM', '시스템감사'
        PROCESS = 'PROCESS', '프로세스감사'
        PRODUCT = 'PRODUCT', '제품감사'

    class Status(models.TextChoices):
        PLANNED = 'PLANNED', '계획'
        IN_PROGRESS = 'IN_PROGRESS', '진행중'
        COMPLETED = 'COMPLETED', '완료'

    audit_number = models.CharField('감사번호', max_length=20, unique=True, blank=True)
    title = models.CharField('제목', max_length=200)
    audit_type = models.CharField(
        '감사유형', max_length=20,
        choices=AuditType.choices, default=AuditType.PROCESS,
    )
    scope = models.TextField('감사범위', blank=True)
    auditor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='감사원',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audits_conducted',
    )
    audit_date = models.DateField('감사일', null=True, blank=True)
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.PLANNED,
    )
    findings = models.TextField('감사결과', blank=True)
    conclusion = models.TextField('결론', blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '내부감사'
        verbose_name_plural = verbose_name
        ordering = ['-audit_date']
        indexes = [
            models.Index(fields=['status', 'audit_date'], name='idx_audit_status_date'),
        ]

    def __str__(self):
        return f'[{self.audit_number}] {self.title}'

    def save(self, *args, **kwargs):
        if not self.audit_number:
            from apps.core.utils import generate_document_number
            self.audit_number = generate_document_number(
                InternalAudit, 'audit_number', 'AUD',
            )
        super().save(*args, **kwargs)


class AuditFinding(BaseModel):
    """감사 발견사항"""

    class FindingType(models.TextChoices):
        OBSERVATION = 'OBSERVATION', '관찰사항'
        MINOR_NC = 'MINOR_NC', '경미부적합'
        MAJOR_NC = 'MAJOR_NC', '중대부적합'
        OPPORTUNITY = 'OPPORTUNITY', '개선기회'

    audit = models.ForeignKey(
        InternalAudit,
        verbose_name='감사',
        on_delete=models.PROTECT,
        related_name='audit_findings',
    )
    finding_type = models.CharField(
        '유형', max_length=20,
        choices=FindingType.choices,
    )
    description = models.TextField('설명')
    capa = models.ForeignKey(
        CAPA,
        verbose_name='연결 CAPA',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_findings',
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '감사발견사항'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.audit.audit_number} - {self.get_finding_type_display()}'


class ISODocument(BaseModel):
    """ISO 문서"""

    BUSINESS_KEY_FIELD = 'document_number'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '초안'
        ACTIVE = 'ACTIVE', '유효'
        OBSOLETE = 'OBSOLETE', '폐기'

    document_number = models.CharField('문서번호', max_length=50, unique=True)
    title = models.CharField('제목', max_length=200)
    category = models.CharField('분류', max_length=100, blank=True)
    revision = models.CharField('리비전', max_length=10, default='1')
    effective_date = models.DateField('유효일', null=True, blank=True)
    review_date = models.DateField('검토예정일', null=True, blank=True)
    content = models.TextField('내용', blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='승인자',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_iso_docs',
    )
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.DRAFT,
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'ISO 문서'
        verbose_name_plural = verbose_name
        ordering = ['document_number']
        indexes = [
            models.Index(fields=['status', 'effective_date'], name='idx_isodoc_status_date'),
        ]

    def __str__(self):
        return f'[{self.document_number}] {self.title}'
