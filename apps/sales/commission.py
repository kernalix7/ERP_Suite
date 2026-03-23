from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class CommissionRate(BaseModel):
    class CalcType(models.TextChoices):
        PERCENT = 'PERCENT', '정률(%)'
        FIXED = 'FIXED', '정액(원)'

    partner = models.ForeignKey(
        'sales.Partner', verbose_name='거래처',
        on_delete=models.PROTECT, related_name='commission_rates',
    )
    product = models.ForeignKey(
        'inventory.Product', verbose_name='제품',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='commission_rates',
    )
    name = models.CharField(
        '항목명', max_length=100, default='기본 수수료',
        help_text='예: 판매수수료, 결제수수료, 배송대행비 등',
    )
    calc_type = models.CharField(
        '계산방식', max_length=10,
        choices=CalcType.choices, default=CalcType.PERCENT,
    )
    rate = models.DecimalField(
        '수수료율(%)', max_digits=6, decimal_places=3,
        default=0,
        help_text='정률(%) 방식일 때 적용',
    )
    fixed_amount = models.DecimalField(
        '고정금액(원)', max_digits=15, decimal_places=0,
        default=0,
        help_text='정액(원) 방식일 때 적용',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '수수료 항목'
        verbose_name_plural = '수수료 항목'
        ordering = ['partner', 'name']

    def __str__(self):
        if self.calc_type == self.CalcType.FIXED:
            return f'{self.partner.name} - {self.name}: {self.fixed_amount:,}원'
        return f'{self.partner.name} - {self.name}: {self.rate}%'

    def calculate(self, base_amount):
        """base_amount 기준 수수료 계산"""
        if self.calc_type == self.CalcType.FIXED:
            return int(self.fixed_amount)
        return round(base_amount * self.rate / 100)


class CommissionRecord(BaseModel):
    class Status(models.TextChoices):
        PENDING = 'PENDING', '미정산'
        SETTLED = 'SETTLED', '정산완료'

    partner = models.ForeignKey(
        'sales.Partner', verbose_name='거래처',
        on_delete=models.PROTECT, related_name='commission_records',
    )
    order = models.ForeignKey(
        'sales.Order', verbose_name='주문',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='commission_records',
    )
    order_amount = models.DecimalField('주문금액', max_digits=15, decimal_places=0)
    commission_rate = models.DecimalField('수수료율(%)', max_digits=6, decimal_places=3)
    commission_amount = models.DecimalField('수수료금액', max_digits=15, decimal_places=0)
    status = models.CharField(
        '정산상태', max_length=10,
        choices=Status.choices, default=Status.PENDING,
    )
    settled_date = models.DateField('정산일', null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '수수료내역'
        verbose_name_plural = '수수료내역'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.partner.name} - {self.commission_amount}원 ({self.get_status_display()})'
