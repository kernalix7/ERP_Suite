from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class Equipment(BaseModel):
    """설비"""

    BUSINESS_KEY_FIELD = 'code'

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', '가동중'
        MAINTENANCE = 'MAINTENANCE', '보전중'
        RETIRED = 'RETIRED', '폐기'

    name = models.CharField('설비명', max_length=200)
    code = models.CharField('설비코드', max_length=30, unique=True)
    category = models.CharField('분류', max_length=100, blank=True)
    location = models.CharField('위치', max_length=200, blank=True)
    manufacturer = models.CharField('제조사', max_length=200, blank=True)
    model_number = models.CharField('모델번호', max_length=100, blank=True)
    serial_number = models.CharField('시리얼번호', max_length=100, blank=True)
    purchase_date = models.DateField('구입일', null=True, blank=True)
    purchase_cost = models.DecimalField(
        '구입비용', max_digits=15, decimal_places=0,
        null=True, blank=True,
    )
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.ACTIVE,
    )
    department = models.ForeignKey(
        'hr.Department',
        verbose_name='관리부서',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='equipment_set',
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '설비'
        verbose_name_plural = verbose_name
        ordering = ['code']
        indexes = [
            models.Index(fields=['status', 'is_active'], name='idx_equip_status_active'),
        ]

    def __str__(self):
        return f'[{self.code}] {self.name}'


class MaintenanceSchedule(BaseModel):
    """보전 스케줄"""

    class MaintenanceType(models.TextChoices):
        PREVENTIVE = 'PREVENTIVE', '예방보전'
        CORRECTIVE = 'CORRECTIVE', '사후보전'
        PREDICTIVE = 'PREDICTIVE', '예지보전'

    equipment = models.ForeignKey(
        Equipment,
        verbose_name='설비',
        on_delete=models.PROTECT,
        related_name='schedules',
    )
    maintenance_type = models.CharField(
        '보전유형', max_length=20,
        choices=MaintenanceType.choices, default=MaintenanceType.PREVENTIVE,
    )
    title = models.CharField('제목', max_length=200)
    frequency_days = models.PositiveIntegerField('주기(일)', default=30)
    last_performed = models.DateField('최근수행일', null=True, blank=True)
    next_due = models.DateField('다음예정일', null=True, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='담당자',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='maintenance_schedules',
    )
    instructions = models.TextField('작업지침', blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '보전스케줄'
        verbose_name_plural = verbose_name
        ordering = ['next_due']
        indexes = [
            models.Index(fields=['equipment', 'next_due'], name='idx_ms_equip_due'),
            models.Index(fields=['next_due'], name='idx_ms_next_due'),
        ]

    def __str__(self):
        return f'{self.equipment.code} - {self.title}'


class MaintenanceWorkOrder(BaseModel):
    """보전 작업지시서"""

    BUSINESS_KEY_FIELD = 'wo_number'

    class Status(models.TextChoices):
        OPEN = 'OPEN', '접수'
        IN_PROGRESS = 'IN_PROGRESS', '진행중'
        COMPLETED = 'COMPLETED', '완료'
        CANCELLED = 'CANCELLED', '취소'

    class Priority(models.TextChoices):
        LOW = 'LOW', '낮음'
        NORMAL = 'NORMAL', '보통'
        HIGH = 'HIGH', '높음'
        EMERGENCY = 'EMERGENCY', '긴급'

    wo_number = models.CharField('작업지시번호', max_length=20, unique=True, blank=True)
    schedule = models.ForeignKey(
        MaintenanceSchedule,
        verbose_name='보전스케줄',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='work_orders',
    )
    equipment = models.ForeignKey(
        Equipment,
        verbose_name='설비',
        on_delete=models.PROTECT,
        related_name='work_orders',
    )
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.OPEN,
    )
    priority = models.CharField(
        '우선순위', max_length=20,
        choices=Priority.choices, default=Priority.NORMAL,
    )
    description = models.TextField('작업내용', blank=True)
    started_at = models.DateTimeField('시작시각', null=True, blank=True)
    completed_at = models.DateTimeField('완료시각', null=True, blank=True)
    cost = models.DecimalField(
        '비용', max_digits=15, decimal_places=0,
        default=0,
    )
    findings = models.TextField('점검결과', blank=True)
    parts_used = models.TextField('사용부품', blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='담당자',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='maintenance_work_orders',
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '보전작업지시'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at'], name='idx_mwo_status_date'),
            models.Index(fields=['equipment', 'status'], name='idx_mwo_equip_status'),
        ]

    def __str__(self):
        return self.wo_number

    def save(self, *args, **kwargs):
        if not self.wo_number:
            from apps.core.utils import generate_document_number
            self.wo_number = generate_document_number(
                MaintenanceWorkOrder, 'wo_number', 'MWO',
            )
        super().save(*args, **kwargs)


class SparePart(BaseModel):
    """예비부품"""

    BUSINESS_KEY_FIELD = 'code'

    name = models.CharField('부품명', max_length=200)
    code = models.CharField('부품코드', max_length=30, unique=True)
    equipment_types = models.ManyToManyField(
        Equipment,
        verbose_name='적용설비',
        blank=True,
        related_name='spare_parts',
    )
    current_stock = models.DecimalField(
        '현재재고', max_digits=15, decimal_places=3, default=0,
    )
    min_stock = models.DecimalField(
        '최소재고', max_digits=15, decimal_places=3, default=0,
    )
    unit_cost = models.DecimalField(
        '단가', max_digits=15, decimal_places=0, default=0,
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '예비부품'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'[{self.code}] {self.name}'

    @property
    def is_below_min(self):
        return self.current_stock < self.min_stock


class EquipmentDowntime(BaseModel):
    """설비 비가동 기록"""

    equipment = models.ForeignKey(
        Equipment,
        verbose_name='설비',
        on_delete=models.PROTECT,
        related_name='downtimes',
    )
    start_time = models.DateTimeField('시작시각')
    end_time = models.DateTimeField('종료시각', null=True, blank=True)
    reason = models.TextField('사유')
    work_order = models.ForeignKey(
        MaintenanceWorkOrder,
        verbose_name='작업지시',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='downtimes',
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '비가동기록'
        verbose_name_plural = verbose_name
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['equipment', 'start_time'], name='idx_dt_equip_time'),
        ]

    def __str__(self):
        return f'{self.equipment.code} 비가동 ({self.start_time:%Y-%m-%d %H:%M})'

    @property
    def duration_hours(self):
        if self.end_time and self.start_time:
            delta = self.end_time - self.start_time
            return round(delta.total_seconds() / 3600, 2)
        return None
