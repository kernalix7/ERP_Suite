from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class CommissionRate(BaseModel):
    partner = models.ForeignKey(
        'sales.Partner', verbose_name='거래처',
        on_delete=models.PROTECT, related_name='commission_rates',
    )
    product = models.ForeignKey(
        'inventory.Product', verbose_name='제품',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='commission_rates',
    )
    rate = models.DecimalField('수수료율(%)', max_digits=5, decimal_places=2)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '수수료율'
        verbose_name_plural = '수수료율'
        unique_together = ['partner', 'product']

    def __str__(self):
        if self.product:
            return f'{self.partner.name} - {self.product.name}: {self.rate}%'
        return f'{self.partner.name}: {self.rate}%'


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
    commission_rate = models.DecimalField('수수료율(%)', max_digits=5, decimal_places=2)
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
