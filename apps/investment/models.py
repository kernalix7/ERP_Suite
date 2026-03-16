from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class Investor(BaseModel):
    name = models.CharField('투자자명', max_length=100)
    company = models.CharField('소속회사', max_length=200, blank=True)
    contact_person = models.CharField('담당자', max_length=50, blank=True)
    phone = models.CharField('연락처', max_length=20, blank=True)
    email = models.EmailField('이메일', blank=True)
    address = models.TextField('주소', blank=True)
    registration_date = models.DateField('등록일')
    history = HistoricalRecords()

    class Meta:
        verbose_name = '투자자'
        verbose_name_plural = '투자자'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def total_invested(self):
        return self.investments.aggregate(
            total=models.Sum('amount')
        )['total'] or 0

    @property
    def current_share(self):
        latest = self.equity_changes.order_by('-change_date', '-pk').first()
        if latest:
            return latest.after_percentage
        inv = self.investments.order_by('-investment_date').first()
        return inv.share_percentage if inv else 0

    @property
    def total_distributed(self):
        return self.distributions.filter(
            status='PAID'
        ).aggregate(total=models.Sum('amount'))['total'] or 0


class InvestmentRound(BaseModel):
    class RoundType(models.TextChoices):
        SEED = 'SEED', '시드'
        PRE_A = 'PRE_A', '프리시리즈A'
        SERIES_A = 'SERIES_A', '시리즈A'
        SERIES_B = 'SERIES_B', '시리즈B'
        SERIES_C = 'SERIES_C', '시리즈C'
        BRIDGE = 'BRIDGE', '브릿지'
        OTHER = 'OTHER', '기타'

    name = models.CharField('라운드명', max_length=100)
    round_type = models.CharField('라운드유형', max_length=20, choices=RoundType.choices)
    target_amount = models.DecimalField('목표금액', max_digits=15, decimal_places=0, default=0)
    raised_amount = models.DecimalField('모집금액', max_digits=15, decimal_places=0, default=0)
    round_date = models.DateField('투자일')
    pre_valuation = models.DecimalField('투자전 기업가치', max_digits=15, decimal_places=0, default=0)
    post_valuation = models.DecimalField('투자후 기업가치', max_digits=15, decimal_places=0, default=0)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '투자라운드'
        verbose_name_plural = '투자라운드'
        ordering = ['-round_date']

    def __str__(self):
        return f'{self.name} ({self.get_round_type_display()})'

    @property
    def total_invested(self):
        return self.investments.aggregate(
            total=models.Sum('amount')
        )['total'] or 0

    @property
    def investor_count(self):
        return self.investments.count()


class Investment(BaseModel):
    investor = models.ForeignKey(
        Investor, verbose_name='투자자',
        on_delete=models.PROTECT, related_name='investments',
    )
    round = models.ForeignKey(
        InvestmentRound, verbose_name='투자라운드',
        on_delete=models.PROTECT, related_name='investments',
    )
    amount = models.DecimalField('투자금액', max_digits=15, decimal_places=0)
    share_percentage = models.DecimalField('지분율(%)', max_digits=6, decimal_places=3)
    investment_date = models.DateField('투자일')
    history = HistoricalRecords()

    class Meta:
        verbose_name = '투자내역'
        verbose_name_plural = '투자내역'
        ordering = ['-investment_date']
        unique_together = ['investor', 'round']

    def __str__(self):
        return f'{self.investor.name} - {self.round.name} ({self.amount:,}원)'


class EquityChange(BaseModel):
    class ChangeType(models.TextChoices):
        INVESTMENT = 'INVESTMENT', '신규투자'
        DILUTION = 'DILUTION', '희석'
        TRANSFER = 'TRANSFER', '지분양도'
        BUYBACK = 'BUYBACK', '자사주매입'

    investor = models.ForeignKey(
        Investor, verbose_name='투자자',
        on_delete=models.PROTECT, related_name='equity_changes',
    )
    change_type = models.CharField('변동유형', max_length=20, choices=ChangeType.choices)
    change_date = models.DateField('변동일')
    before_percentage = models.DecimalField('변동전 지분율(%)', max_digits=6, decimal_places=3)
    after_percentage = models.DecimalField('변동후 지분율(%)', max_digits=6, decimal_places=3)
    related_round = models.ForeignKey(
        InvestmentRound, verbose_name='관련라운드',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '지분변동'
        verbose_name_plural = '지분변동'
        ordering = ['-change_date', '-pk']

    def __str__(self):
        return f'{self.investor.name} {self.before_percentage}% → {self.after_percentage}%'


class Distribution(BaseModel):
    class DistributionType(models.TextChoices):
        DIVIDEND = 'DIVIDEND', '배당'
        PROFIT_SHARE = 'PROFIT_SHARE', '수익분배'
        INTERIM = 'INTERIM', '중간배당'

    class PaymentStatus(models.TextChoices):
        SCHEDULED = 'SCHEDULED', '예정'
        PENDING = 'PENDING', '대기'
        PAID = 'PAID', '지급완료'
        CANCELLED = 'CANCELLED', '취소'

    investor = models.ForeignKey(
        Investor, verbose_name='투자자',
        on_delete=models.PROTECT, related_name='distributions',
    )
    distribution_type = models.CharField('분배유형', max_length=20, choices=DistributionType.choices)
    amount = models.DecimalField('분배금액', max_digits=15, decimal_places=0)
    scheduled_date = models.DateField('예정일')
    paid_date = models.DateField('지급일', null=True, blank=True)
    status = models.CharField(
        '상태', max_length=20,
        choices=PaymentStatus.choices, default=PaymentStatus.SCHEDULED,
    )
    fiscal_year = models.PositiveIntegerField('회계연도')
    history = HistoricalRecords()

    class Meta:
        verbose_name = '배당/분배'
        verbose_name_plural = '배당/분배'
        ordering = ['-scheduled_date']

    def __str__(self):
        return f'{self.investor.name} - {self.get_distribution_type_display()} ({self.fiscal_year})'
