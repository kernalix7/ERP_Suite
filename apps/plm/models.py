from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class ProductVersion(BaseModel):
    """제품 버전"""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '초안'
        REVIEW = 'REVIEW', '검토중'
        APPROVED = 'APPROVED', '승인'
        OBSOLETE = 'OBSOLETE', '폐기'

    product = models.ForeignKey(
        'inventory.Product',
        verbose_name='제품',
        on_delete=models.PROTECT,
        related_name='versions',
    )
    version_number = models.CharField('버전번호', max_length=20)
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.DRAFT,
    )
    effective_date = models.DateField('유효일', null=True, blank=True)
    description = models.TextField('설명', blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '제품버전'
        verbose_name_plural = verbose_name
        ordering = ['product', '-version_number']
        unique_together = [('product', 'version_number')]
        indexes = [
            models.Index(fields=['status', 'created_at'], name='idx_pv_status_date'),
        ]

    def __str__(self):
        return f'{self.product} v{self.version_number}'


class BOMRevision(BaseModel):
    """BOM 리비전"""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '초안'
        REVIEW = 'REVIEW', '검토중'
        APPROVED = 'APPROVED', '승인'
        OBSOLETE = 'OBSOLETE', '폐기'

    bom = models.ForeignKey(
        'production.BOM',
        verbose_name='BOM',
        on_delete=models.PROTECT,
        related_name='revisions',
    )
    revision_number = models.CharField('리비전번호', max_length=20)
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.DRAFT,
    )
    change_reason = models.TextField('변경사유', blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='승인자',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_bom_revisions',
    )
    approved_at = models.DateTimeField('승인일시', null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'BOM 리비전'
        verbose_name_plural = verbose_name
        ordering = ['bom', '-revision_number']
        unique_together = [('bom', 'revision_number')]

    def __str__(self):
        return f'{self.bom} Rev.{self.revision_number}'


class EngineeringChangeNotice(BaseModel):
    """설계변경통지서 (ECN)"""

    BUSINESS_KEY_FIELD = 'ecn_number'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '초안'
        REVIEW = 'REVIEW', '검토중'
        APPROVED = 'APPROVED', '승인'
        IMPLEMENTED = 'IMPLEMENTED', '시행'
        CLOSED = 'CLOSED', '종결'

    class Priority(models.TextChoices):
        LOW = 'LOW', '낮음'
        NORMAL = 'NORMAL', '보통'
        HIGH = 'HIGH', '높음'
        CRITICAL = 'CRITICAL', '긴급'

    ecn_number = models.CharField('ECN번호', max_length=20, unique=True, blank=True)
    title = models.CharField('제목', max_length=200)
    description = models.TextField('설명')
    priority = models.CharField(
        '우선순위', max_length=20,
        choices=Priority.choices, default=Priority.NORMAL,
    )
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.DRAFT,
    )
    affected_products = models.ManyToManyField(
        'inventory.Product',
        verbose_name='영향 제품',
        blank=True,
        related_name='ecns',
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='요청자',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='requested_ecns',
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='승인자',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_ecns',
    )
    target_date = models.DateField('목표일', null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '설계변경통지'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at'], name='idx_ecn_status_date'),
            models.Index(fields=['priority', 'status'], name='idx_ecn_priority_status'),
        ]

    def __str__(self):
        return f'[{self.ecn_number}] {self.title}'

    def save(self, *args, **kwargs):
        if not self.ecn_number:
            from apps.core.utils import generate_document_number
            self.ecn_number = generate_document_number(
                EngineeringChangeNotice, 'ecn_number', 'ECN',
            )
        super().save(*args, **kwargs)


class ECNItem(BaseModel):
    """ECN 항목"""

    class ChangeType(models.TextChoices):
        ADD = 'ADD', '추가'
        MODIFY = 'MODIFY', '변경'
        REMOVE = 'REMOVE', '삭제'

    ecn = models.ForeignKey(
        EngineeringChangeNotice,
        verbose_name='ECN',
        on_delete=models.PROTECT,
        related_name='items',
    )
    change_type = models.CharField(
        '변경유형', max_length=10,
        choices=ChangeType.choices,
    )
    product = models.ForeignKey(
        'inventory.Product',
        verbose_name='대상품목',
        on_delete=models.PROTECT,
        related_name='ecn_items',
        null=True, blank=True,
    )
    description = models.TextField('변경내용')
    before_spec = models.TextField('변경전 사양', blank=True)
    after_spec = models.TextField('변경후 사양', blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'ECN 항목'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.ecn.ecn_number} - {self.get_change_type_display()}'


class Drawing(BaseModel):
    """도면"""

    product = models.ForeignKey(
        'inventory.Product',
        verbose_name='제품',
        on_delete=models.PROTECT,
        related_name='drawings',
    )
    version = models.ForeignKey(
        ProductVersion,
        verbose_name='버전',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='drawings',
    )
    file = models.FileField('파일', upload_to='plm/drawings/%Y/%m/')
    drawing_number = models.CharField('도면번호', max_length=50, unique=True)
    revision = models.CharField('리비전', max_length=10, default='A')
    description = models.TextField('설명', blank=True)
    format = models.CharField('포맷', max_length=20, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '도면'
        verbose_name_plural = verbose_name
        ordering = ['product', 'drawing_number']

    def __str__(self):
        return f'{self.drawing_number} Rev.{self.revision}'
