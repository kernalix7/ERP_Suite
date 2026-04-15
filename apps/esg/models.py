from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel
from apps.core.utils import generate_document_number


class ESGCategory(BaseModel):
    """ESG 카테고리"""

    class CategoryType(models.TextChoices):
        ENVIRONMENTAL = 'ENVIRONMENTAL', '환경'
        SOCIAL = 'SOCIAL', '사회'
        GOVERNANCE = 'GOVERNANCE', '지배구조'

    name = models.CharField('카테고리명', max_length=100)
    code = models.CharField('코드', max_length=20, unique=True)
    category_type = models.CharField(
        'ESG 구분', max_length=20,
        choices=CategoryType.choices,
    )
    parent = models.ForeignKey(
        'self', verbose_name='상위 카테고리',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='children',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'ESG 카테고리'
        verbose_name_plural = 'ESG 카테고리'
        ordering = ['category_type', 'code']

    def __str__(self):
        return f'[{self.code}] {self.name}'


class ESGMetric(BaseModel):
    """ESG 지표"""

    class Frequency(models.TextChoices):
        DAILY = 'DAILY', '일간'
        WEEKLY = 'WEEKLY', '주간'
        MONTHLY = 'MONTHLY', '월간'
        QUARTERLY = 'QUARTERLY', '분기'
        YEARLY = 'YEARLY', '연간'

    category = models.ForeignKey(
        ESGCategory, verbose_name='카테고리',
        on_delete=models.PROTECT, related_name='metrics',
    )
    name = models.CharField('지표명', max_length=100)
    code = models.CharField('코드', max_length=20, unique=True)
    unit = models.CharField('단위', max_length=20, blank=True)
    target_value = models.DecimalField(
        '목표값', max_digits=15, decimal_places=2,
        null=True, blank=True,
    )
    measurement_frequency = models.CharField(
        '측정 주기', max_length=20,
        choices=Frequency.choices, default=Frequency.MONTHLY,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'ESG 지표'
        verbose_name_plural = 'ESG 지표'
        ordering = ['category', 'code']

    def __str__(self):
        return f'{self.name} ({self.unit})'


class ESGRecord(BaseModel):
    """ESG 실적 기록"""
    metric = models.ForeignKey(
        ESGMetric, verbose_name='지표',
        on_delete=models.PROTECT, related_name='records',
    )
    period_start = models.DateField('기간 시작')
    period_end = models.DateField('기간 종료')
    value = models.DecimalField('측정값', max_digits=15, decimal_places=2)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='기록자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='esg_records',
    )
    verified = models.BooleanField('검증완료', default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='검증자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='verified_esg_records',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'ESG 실적'
        verbose_name_plural = 'ESG 실적'
        ordering = ['-period_end']

    def __str__(self):
        return f'{self.metric.name}: {self.value} ({self.period_start}~{self.period_end})'


class CarbonEmission(BaseModel):
    """탄소 배출"""

    class Scope(models.TextChoices):
        SCOPE1 = 'SCOPE1', 'Scope 1 (직접배출)'
        SCOPE2 = 'SCOPE2', 'Scope 2 (간접배출-전력)'
        SCOPE3 = 'SCOPE3', 'Scope 3 (기타간접)'

    source = models.CharField('배출원', max_length=100)
    scope = models.CharField(
        '범위', max_length=10,
        choices=Scope.choices,
    )
    emission_type = models.CharField('배출유형', max_length=50, blank=True)
    amount_kg = models.DecimalField(
        '배출량(kg)', max_digits=15, decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    period = models.DateField('기간')
    facility = models.CharField('시설', max_length=100, blank=True)
    calculation_method = models.CharField('산정방법', max_length=100, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '탄소 배출'
        verbose_name_plural = '탄소 배출'
        ordering = ['-period']

    def __str__(self):
        return f'{self.source} {self.amount_kg}kg ({self.get_scope_display()})'


class SafetyIncident(BaseModel):
    """안전 사고"""
    BUSINESS_KEY_FIELD = 'incident_number'

    class Severity(models.TextChoices):
        NEAR_MISS = 'NEAR_MISS', '아차사고'
        MINOR = 'MINOR', '경미'
        MAJOR = 'MAJOR', '중대'
        CRITICAL = 'CRITICAL', '치명적'

    class Status(models.TextChoices):
        REPORTED = 'REPORTED', '보고'
        INVESTIGATING = 'INVESTIGATING', '조사중'
        RESOLVED = 'RESOLVED', '해결'
        CLOSED = 'CLOSED', '종결'

    incident_number = models.CharField('사고번호', max_length=20, unique=True, blank=True)
    date = models.DateField('발생일')
    location = models.CharField('발생장소', max_length=200)
    severity = models.CharField(
        '심각도', max_length=20,
        choices=Severity.choices,
    )
    description = models.TextField('사고 내용')
    injured_count = models.PositiveIntegerField('부상자 수', default=0)
    root_cause = models.TextField('원인 분석', blank=True)
    corrective_action = models.TextField('시정 조치', blank=True)
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.REPORTED,
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='보고자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='reported_incidents',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '안전 사고'
        verbose_name_plural = '안전 사고'
        ordering = ['-date', '-pk']
        indexes = [
            models.Index(fields=['severity'], name='idx_incident_severity'),
            models.Index(fields=['status'], name='idx_incident_status'),
        ]

    def __str__(self):
        return f'{self.incident_number} - {self.get_severity_display()}'

    def save(self, *args, **kwargs):
        if not self.incident_number:
            self.incident_number = generate_document_number(
                SafetyIncident, 'incident_number', 'SI',
            )
        super().save(*args, **kwargs)


class ComplianceRequirement(BaseModel):
    """컴플라이언스 요구사항"""

    class Status(models.TextChoices):
        PENDING = 'PENDING', '대기'
        IN_PROGRESS = 'IN_PROGRESS', '진행중'
        COMPLIANT = 'COMPLIANT', '준수'
        NON_COMPLIANT = 'NON_COMPLIANT', '미준수'

    name = models.CharField('요구사항명', max_length=200)
    regulation = models.CharField('관련 법규', max_length=200)
    description = models.TextField('설명', blank=True)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='담당자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='compliance_requirements',
    )
    due_date = models.DateField('기한', null=True, blank=True)
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.PENDING,
    )
    evidence_file = models.FileField('증빙자료', upload_to='compliance/%Y/%m/', blank=True)
    last_review = models.DateField('최근 검토일', null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '컴플라이언스'
        verbose_name_plural = '컴플라이언스'
        ordering = ['due_date']

    def __str__(self):
        return f'{self.name} ({self.get_status_display()})'


class ESGReport(BaseModel):
    """ESG 보고서"""

    class ReportType(models.TextChoices):
        ANNUAL = 'ANNUAL', '연간'
        QUARTERLY = 'QUARTERLY', '분기'
        CUSTOM = 'CUSTOM', '사용자정의'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '초안'
        REVIEW = 'REVIEW', '검토중'
        PUBLISHED = 'PUBLISHED', '발행'

    title = models.CharField('보고서명', max_length=200)
    report_type = models.CharField(
        '보고서 유형', max_length=20,
        choices=ReportType.choices,
    )
    period_start = models.DateField('기간 시작')
    period_end = models.DateField('기간 종료')
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.DRAFT,
    )
    data = models.JSONField('보고서 데이터', default=dict, blank=True)
    generated_at = models.DateTimeField('생성일시', null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'ESG 보고서'
        verbose_name_plural = 'ESG 보고서'
        ordering = ['-period_end']

    def __str__(self):
        return f'{self.title} ({self.period_start}~{self.period_end})'
