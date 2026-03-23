from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords
from apps.core.models import BaseModel


class AssetCategory(BaseModel):
    """자산 분류"""
    name = models.CharField('분류명', max_length=100)
    code = models.CharField('분류코드', max_length=20, unique=True)
    useful_life_years = models.PositiveIntegerField('내용연수(년)', default=5)
    depreciation_method = models.CharField('감가상각법', max_length=10, choices=[
        ('STRAIGHT', '정액법'),
        ('DECLINING', '정률법'),
    ], default='STRAIGHT')
    history = HistoricalRecords()

    class Meta:
        verbose_name = '자산분류'
        verbose_name_plural = '자산분류'
        ordering = ['code']

    def __str__(self):
        return f'[{self.code}] {self.name}'


class FixedAsset(BaseModel):
    """고정자산 대장"""
    asset_number = models.CharField('자산번호', max_length=30, unique=True)
    name = models.CharField('자산명', max_length=200)
    category = models.ForeignKey(AssetCategory, on_delete=models.PROTECT, related_name='assets', verbose_name='분류')

    # 취득 정보
    acquisition_date = models.DateField('취득일')
    acquisition_cost = models.DecimalField('취득원가', max_digits=15, decimal_places=0)
    residual_value = models.DecimalField('잔존가치', max_digits=15, decimal_places=0, default=0)

    # 감가상각 설정
    useful_life_years = models.PositiveIntegerField('내용연수(년)')
    depreciation_method = models.CharField('감가상각법', max_length=10, choices=[
        ('STRAIGHT', '정액법'),
        ('DECLINING', '정률법'),
    ], default='STRAIGHT')

    # 현재 상태
    accumulated_depreciation = models.DecimalField('감가상각 누계액', max_digits=15, decimal_places=0, default=0)
    book_value = models.DecimalField('장부가액', max_digits=15, decimal_places=0, default=0)

    # 관리 정보
    department = models.ForeignKey('hr.Department', null=True, blank=True, on_delete=models.SET_NULL, verbose_name='사용부서')
    location = models.CharField('위치', max_length=200, blank=True)
    responsible_person = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='managed_assets', verbose_name='관리자')

    # 처분
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', '사용중'
        DISPOSED = 'DISPOSED', '처분'
        SCRAPPED = 'SCRAPPED', '폐기'

    status = models.CharField('상태', max_length=10, choices=Status.choices, default=Status.ACTIVE)
    disposal_date = models.DateField('처분일', null=True, blank=True)
    disposal_amount = models.DecimalField('처분금액', max_digits=15, decimal_places=0, default=0)
    disposal_reason = models.TextField('처분사유', blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '고정자산'
        verbose_name_plural = '고정자산'
        ordering = ['-acquisition_date']

    def __str__(self):
        return f'[{self.asset_number}] {self.name}'

    def save(self, *args, **kwargs):
        self.book_value = self.acquisition_cost - self.accumulated_depreciation
        super().save(*args, **kwargs)

    @property
    def monthly_depreciation(self):
        """월 감가상각비 계산"""
        if self.depreciation_method == 'STRAIGHT':
            depreciable = self.acquisition_cost - self.residual_value
            return int(depreciable / (self.useful_life_years * 12))
        else:  # DECLINING (정률법)
            if self.useful_life_years <= 0:
                return 0
            rate = 1 - (float(self.residual_value) / float(self.acquisition_cost)) ** (1.0 / self.useful_life_years) if self.acquisition_cost > 0 else 0
            return int(self.book_value * rate / 12)

    @property
    def is_fully_depreciated(self):
        return self.book_value <= self.residual_value


class DepreciationRecord(BaseModel):
    """감가상각 내역"""
    asset = models.ForeignKey(FixedAsset, on_delete=models.PROTECT, related_name='depreciation_records')
    year = models.PositiveIntegerField('년도')
    month = models.PositiveIntegerField('월')
    depreciation_amount = models.DecimalField('감가상각비', max_digits=15, decimal_places=0)
    accumulated_amount = models.DecimalField('누계액', max_digits=15, decimal_places=0)
    book_value_after = models.DecimalField('상각후 장부가', max_digits=15, decimal_places=0)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '감가상각 내역'
        verbose_name_plural = '감가상각 내역'
        ordering = ['-year', '-month']
        constraints = [
            models.UniqueConstraint(fields=['asset', 'year', 'month'], name='uq_depreciation_asset_period'),
        ]

    def __str__(self):
        return f'{self.asset.asset_number} - {self.year}/{self.month}'
