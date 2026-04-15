from decimal import Decimal

from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class ForecastParameter(BaseModel):
    """예측 파라미터"""

    class Method(models.TextChoices):
        MOVING_AVG = 'MOVING_AVG', '이동평균'
        WEIGHTED_AVG = 'WEIGHTED_AVG', '가중평균'
        EXPONENTIAL = 'EXPONENTIAL', '지수평활'
        MANUAL = 'MANUAL', '수동입력'

    product = models.ForeignKey(
        'inventory.Product',
        verbose_name='제품',
        on_delete=models.PROTECT,
        related_name='forecast_parameters',
    )
    method = models.CharField(
        '예측방법', max_length=20,
        choices=Method.choices, default=Method.MOVING_AVG,
    )
    lookback_months = models.PositiveIntegerField('조회기간(월)', default=6)
    weight_recent = models.DecimalField(
        '최근가중치', max_digits=5, decimal_places=2, default=Decimal('0.50'),
    )
    smoothing_factor = models.DecimalField(
        '평활계수(alpha)', max_digits=5, decimal_places=2, default=Decimal('0.30'),
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '예측파라미터'
        verbose_name_plural = verbose_name
        unique_together = [('product', 'method')]

    def __str__(self):
        return f'{self.product} - {self.get_method_display()}'


class DemandForecast(BaseModel):
    """수요예측"""

    class Method(models.TextChoices):
        MOVING_AVG = 'MOVING_AVG', '이동평균'
        WEIGHTED_AVG = 'WEIGHTED_AVG', '가중평균'
        EXPONENTIAL = 'EXPONENTIAL', '지수평활'
        MANUAL = 'MANUAL', '수동입력'

    product = models.ForeignKey(
        'inventory.Product',
        verbose_name='제품',
        on_delete=models.PROTECT,
        related_name='demand_forecasts',
    )
    period_start = models.DateField('기간시작')
    period_end = models.DateField('기간종료')
    forecast_method = models.CharField(
        '예측방법', max_length=20,
        choices=Method.choices, default=Method.MOVING_AVG,
    )
    forecast_qty = models.DecimalField(
        '예측수량', max_digits=15, decimal_places=3, default=0,
    )
    actual_qty = models.DecimalField(
        '실제수량', max_digits=15, decimal_places=3, default=0,
    )
    accuracy_pct = models.DecimalField(
        '정확도(%)', max_digits=6, decimal_places=2,
        null=True, blank=True,
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '수요예측'
        verbose_name_plural = verbose_name
        ordering = ['-period_start']
        indexes = [
            models.Index(fields=['product', 'period_start'], name='idx_forecast_product_period'),
            models.Index(fields=['forecast_method', 'period_start'], name='idx_forecast_method_period'),
        ]

    def __str__(self):
        return f'{self.product} ({self.period_start} ~ {self.period_end})'

    def calculate_accuracy(self):
        if self.forecast_qty and self.actual_qty:
            error = abs(self.forecast_qty - self.actual_qty)
            if self.actual_qty != 0:
                self.accuracy_pct = max(
                    Decimal('0'),
                    Decimal('100') - (error / self.actual_qty * Decimal('100')),
                )
            else:
                self.accuracy_pct = Decimal('0') if self.forecast_qty else Decimal('100')


class SOPMeeting(BaseModel):
    """S&OP 회의"""

    class Status(models.TextChoices):
        PLANNED = 'PLANNED', '계획'
        IN_PROGRESS = 'IN_PROGRESS', '진행중'
        APPROVED = 'APPROVED', '승인'

    title = models.CharField('제목', max_length=200)
    meeting_date = models.DateField('회의일')
    period = models.CharField('대상기간', max_length=50)
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.PLANNED,
    )
    attendees = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name='참석자',
        blank=True,
        related_name='sop_meetings',
    )
    minutes = models.TextField('회의록', blank=True)
    decisions = models.TextField('의사결정', blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'S&OP 회의'
        verbose_name_plural = verbose_name
        ordering = ['-meeting_date']
        indexes = [
            models.Index(fields=['status', 'meeting_date'], name='idx_sop_status_date'),
        ]

    def __str__(self):
        return f'{self.title} ({self.meeting_date})'


class SOPScenario(BaseModel):
    """S&OP 시나리오"""

    meeting = models.ForeignKey(
        SOPMeeting,
        verbose_name='회의',
        on_delete=models.PROTECT,
        related_name='scenarios',
    )
    name = models.CharField('시나리오명', max_length=100)
    description = models.TextField('설명', blank=True)
    assumptions = models.TextField('가정', blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'S&OP 시나리오'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.meeting} - {self.name}'


class SOPLineItem(BaseModel):
    """S&OP 항목"""

    scenario = models.ForeignKey(
        SOPScenario,
        verbose_name='시나리오',
        on_delete=models.PROTECT,
        related_name='line_items',
    )
    product = models.ForeignKey(
        'inventory.Product',
        verbose_name='제품',
        on_delete=models.PROTECT,
        related_name='sop_line_items',
    )
    forecast_qty = models.DecimalField(
        '예측수량', max_digits=15, decimal_places=3, default=0,
    )
    planned_production = models.DecimalField(
        '계획생산', max_digits=15, decimal_places=3, default=0,
    )
    planned_purchase = models.DecimalField(
        '계획구매', max_digits=15, decimal_places=3, default=0,
    )
    planned_inventory = models.DecimalField(
        '계획재고', max_digits=15, decimal_places=3, default=0,
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'S&OP 항목'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.scenario.name} - {self.product}'
