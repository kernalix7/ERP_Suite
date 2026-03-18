from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class AdPlatform(BaseModel):
    """광고 플랫폼"""

    PLATFORM_TYPE_CHOICES = [
        ('SEARCH', '검색광고'),
        ('DISPLAY', '디스플레이'),
        ('SOCIAL', '소셜미디어'),
        ('VIDEO', '동영상'),
        ('OTHER', '기타'),
    ]

    name = models.CharField('플랫폼명', max_length=100)
    platform_type = models.CharField(
        '유형', max_length=20,
        choices=PLATFORM_TYPE_CHOICES, default='SEARCH'
    )
    api_key = models.CharField(
        'API 키', max_length=255, blank=True
    )
    api_secret = models.CharField(
        'API 시크릿', max_length=255, blank=True
    )
    account_id = models.CharField(
        '계정 ID', max_length=100, blank=True
    )
    is_connected = models.BooleanField('연동 상태', default=False)
    website_url = models.URLField(
        '플랫폼 URL', blank=True
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '광고 플랫폼'
        verbose_name_plural = '광고 플랫폼'
        ordering = ['name']

    def __str__(self):
        return self.name


class AdCampaign(BaseModel):
    """광고 캠페인"""

    CAMPAIGN_TYPE_CHOICES = [
        ('BRAND', '브랜드'),
        ('PRODUCT', '제품'),
        ('RETARGETING', '리타겟팅'),
        ('SEASONAL', '시즌'),
        ('PROMOTION', '프로모션'),
    ]

    STATUS_CHOICES = [
        ('DRAFT', '초안'),
        ('ACTIVE', '진행중'),
        ('PAUSED', '일시정지'),
        ('COMPLETED', '완료'),
        ('ARCHIVED', '보관'),
    ]

    platform = models.ForeignKey(
        AdPlatform, on_delete=models.PROTECT,
        related_name='campaigns', verbose_name='플랫폼'
    )
    name = models.CharField('캠페인명', max_length=200)
    campaign_type = models.CharField(
        '유형', max_length=20,
        choices=CAMPAIGN_TYPE_CHOICES, default='PRODUCT'
    )
    status = models.CharField(
        '상태', max_length=20,
        choices=STATUS_CHOICES, default='DRAFT'
    )
    budget = models.DecimalField(
        '예산', max_digits=15, decimal_places=0, default=0
    )
    spent = models.DecimalField(
        '집행액', max_digits=15, decimal_places=0, default=0
    )
    start_date = models.DateField('시작일')
    end_date = models.DateField('종료일')
    target_audience = models.TextField(
        '타겟 오디언스', blank=True
    )
    description = models.TextField('설명', blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '광고 캠페인'
        verbose_name_plural = '광고 캠페인'
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    @property
    def budget_utilization(self):
        if self.budget == 0:
            return 0
        return round(float(self.spent) / float(self.budget) * 100, 1)


class AdCreative(BaseModel):
    """광고 소재"""

    CREATIVE_TYPE_CHOICES = [
        ('IMAGE', '이미지'),
        ('VIDEO', '동영상'),
        ('TEXT', '텍스트'),
        ('CAROUSEL', '캐러셀'),
        ('RESPONSIVE', '반응형'),
    ]

    STATUS_CHOICES = [
        ('DRAFT', '초안'),
        ('ACTIVE', '활성'),
        ('PAUSED', '일시정지'),
        ('REJECTED', '반려'),
    ]

    campaign = models.ForeignKey(
        AdCampaign, on_delete=models.CASCADE,
        related_name='creatives', verbose_name='캠페인'
    )
    name = models.CharField('소재명', max_length=200)
    creative_type = models.CharField(
        '유형', max_length=20,
        choices=CREATIVE_TYPE_CHOICES, default='IMAGE'
    )
    headline = models.CharField('제목', max_length=200)
    description = models.TextField('설명', blank=True)
    landing_url = models.URLField('랜딩 URL', blank=True)
    image = models.ImageField(
        '이미지', upload_to='advertising/creatives/',
        blank=True
    )
    status = models.CharField(
        '상태', max_length=20,
        choices=STATUS_CHOICES, default='DRAFT'
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '광고 소재'
        verbose_name_plural = '광고 소재'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class AdPerformance(BaseModel):
    """광고 성과"""

    campaign = models.ForeignKey(
        AdCampaign, on_delete=models.CASCADE,
        related_name='performances', verbose_name='캠페인'
    )
    creative = models.ForeignKey(
        AdCreative, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='performances', verbose_name='소재'
    )
    date = models.DateField('날짜')
    impressions = models.IntegerField('노출수', default=0)
    clicks = models.IntegerField('클릭수', default=0)
    conversions = models.IntegerField('전환수', default=0)
    cost = models.DecimalField(
        '비용', max_digits=15, decimal_places=0, default=0
    )
    revenue = models.DecimalField(
        '매출', max_digits=15, decimal_places=0, default=0
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '광고 성과'
        verbose_name_plural = '광고 성과'
        ordering = ['-date']
        indexes = [
            models.Index(
                fields=['campaign', 'date'],
                name='idx_adperf_campaign_date'
            ),
        ]

    def __str__(self):
        return f"{self.campaign.name} - {self.date}"

    @property
    def ctr(self):
        if self.impressions == 0:
            return 0
        return round(self.clicks / self.impressions * 100, 2)

    @property
    def cpc(self):
        if self.clicks == 0:
            return 0
        return round(float(self.cost) / self.clicks, 0)

    @property
    def roas(self):
        if self.cost == 0:
            return 0
        return round(float(self.revenue) / float(self.cost) * 100, 1)

    @property
    def conversion_rate(self):
        if self.clicks == 0:
            return 0
        return round(self.conversions / self.clicks * 100, 2)


class AdBudget(BaseModel):
    """광고 예산"""

    year = models.IntegerField('연도')
    month = models.PositiveSmallIntegerField(
        '월', choices=[(i, f'{i}월') for i in range(1, 13)]
    )
    platform = models.ForeignKey(
        AdPlatform, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='budgets', verbose_name='플랫폼'
    )
    planned_budget = models.DecimalField(
        '계획 예산', max_digits=15, decimal_places=0, default=0
    )
    actual_spent = models.DecimalField(
        '실제 집행', max_digits=15, decimal_places=0, default=0
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '광고 예산'
        verbose_name_plural = '광고 예산'
        unique_together = ['year', 'month', 'platform']
        ordering = ['-year', '-month']

    def __str__(self):
        platform = self.platform.name if self.platform else '전체'
        return f"{self.year}-{self.month:02d} {platform}"

    @property
    def utilization_rate(self):
        if self.planned_budget == 0:
            return 0
        return round(
            float(self.actual_spent)
            / float(self.planned_budget) * 100, 1
        )
