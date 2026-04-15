from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class Report(BaseModel):
    """BI 리포트"""

    class ReportType(models.TextChoices):
        CHART = 'CHART', '차트'
        TABLE = 'TABLE', '테이블'
        PIVOT = 'PIVOT', '피벗'
        KPI = 'KPI', 'KPI'

    class DataSource(models.TextChoices):
        ORDER = 'ORDER', '주문'
        PRODUCT = 'PRODUCT', '제품'
        PARTNER = 'PARTNER', '거래처'
        VOUCHER = 'VOUCHER', '전표'
        INVENTORY = 'INVENTORY', '재고'
        PRODUCTION = 'PRODUCTION', '생산'
        HR = 'HR', '인사'
        CUSTOM = 'CUSTOM', '사용자정의'

    name = models.CharField('리포트명', max_length=200)
    description = models.TextField('설명', blank=True)
    report_type = models.CharField(
        '리포트유형', max_length=10, choices=ReportType.choices, default=ReportType.CHART,
    )
    data_source = models.CharField(
        '데이터소스', max_length=20, choices=DataSource.choices, default=DataSource.ORDER,
    )
    query_config = models.JSONField(
        '쿼리설정', default=dict, blank=True,
        help_text='filters, groupby, aggregations, sort',
    )
    chart_config = models.JSONField(
        '차트설정', default=dict, blank=True,
        help_text='chart_type (bar/line/pie/donut/scatter/heatmap), colors, axes',
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='bi_reports', verbose_name='소유자',
    )
    is_public = models.BooleanField('공개여부', default=False)
    is_favorite = models.BooleanField('즐겨찾기', default=False)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '리포트'
        verbose_name_plural = verbose_name
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


class ReportSchedule(BaseModel):
    """리포트 자동 발송 스케줄"""

    class Frequency(models.TextChoices):
        DAILY = 'DAILY', '매일'
        WEEKLY = 'WEEKLY', '매주'
        MONTHLY = 'MONTHLY', '매월'

    class Format(models.TextChoices):
        PDF = 'PDF', 'PDF'
        EXCEL = 'EXCEL', 'Excel'
        EMAIL = 'EMAIL', '이메일'

    report = models.ForeignKey(
        Report, on_delete=models.CASCADE,
        related_name='schedules', verbose_name='리포트',
    )
    frequency = models.CharField(
        '발송주기', max_length=10, choices=Frequency.choices, default=Frequency.WEEKLY,
    )
    recipients = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name='bi_subscriptions',
        verbose_name='수신자', blank=True,
    )
    format = models.CharField(
        '형식', max_length=10, choices=Format.choices, default=Format.PDF,
    )
    last_sent = models.DateTimeField('최근발송일', null=True, blank=True)
    next_send = models.DateTimeField('다음발송일', null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '리포트스케줄'
        verbose_name_plural = verbose_name
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.report.name} - {self.get_frequency_display()}'


class Dashboard(BaseModel):
    """BI 대시보드"""

    name = models.CharField('대시보드명', max_length=200)
    description = models.TextField('설명', blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='bi_dashboards', verbose_name='소유자',
    )
    is_default = models.BooleanField('기본대시보드', default=False)
    layout = models.JSONField('레이아웃설정', default=dict, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '대시보드'
        verbose_name_plural = verbose_name
        ordering = ['-is_default', '-updated_at']

    def __str__(self):
        return self.name


class DashboardPanel(BaseModel):
    """대시보드 패널"""

    dashboard = models.ForeignKey(
        Dashboard, on_delete=models.CASCADE,
        related_name='panels', verbose_name='대시보드',
    )
    report = models.ForeignKey(
        Report, on_delete=models.CASCADE,
        related_name='panels', verbose_name='리포트',
    )
    position_x = models.IntegerField('X 위치', default=0)
    position_y = models.IntegerField('Y 위치', default=0)
    width = models.IntegerField('너비', default=6)
    height = models.IntegerField('높이', default=4)
    refresh_interval_minutes = models.IntegerField('갱신주기(분)', default=5)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '대시보드패널'
        verbose_name_plural = verbose_name
        ordering = ['position_y', 'position_x']

    def __str__(self):
        return f'{self.dashboard.name} - {self.report.name}'


class SavedFilter(BaseModel):
    """저장된 필터"""

    name = models.CharField('필터명', max_length=200)
    data_source = models.CharField(
        '데이터소스', max_length=20, choices=Report.DataSource.choices,
    )
    filter_config = models.JSONField('필터설정', default=dict, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='bi_saved_filters', verbose_name='소유자',
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '저장필터'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name
