from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class AgingBucket(models.TextChoices):
    DAYS_30 = '30', '30일 연체'
    DAYS_60 = '60', '60일 연체'
    DAYS_90 = '90', '90일 연체'
    DAYS_180 = '180', '180일 연체'
    DAYS_365 = '365', '1년 이상'


class BadDebtAllowance(BaseModel):
    """대손충당금 — 연체 AR에 대해 충당률을 적용하여 대손상각비 계상"""

    receivable = models.ForeignKey(
        'accounting.AccountReceivable',
        on_delete=models.PROTECT,
        related_name='bad_debt_allowances',
        verbose_name='매출채권',
    )
    estimated_date = models.DateField('추정일')
    allowance_amount = models.DecimalField('충당금액', max_digits=15, decimal_places=0)
    allowance_rate = models.DecimalField('충당률(%)', max_digits=5, decimal_places=2)
    aging_bucket = models.CharField(
        '연체구간', max_length=8, choices=AgingBucket.choices,
    )
    voucher = models.ForeignKey(
        'accounting.Voucher',
        null=True,
        on_delete=models.SET_NULL,
        related_name='bad_debt_allowances',
        verbose_name='전표',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '대손충당금'
        verbose_name_plural = '대손충당금 목록'
        ordering = ['-estimated_date']
        indexes = [
            models.Index(fields=['estimated_date'], name='idx_bda_estimated_date'),
            models.Index(fields=['aging_bucket'], name='idx_bda_aging_bucket'),
        ]

    def __str__(self):
        return (
            f'{self.receivable} — {self.aging_bucket}일 연체 '
            f'{self.allowance_rate}% ({self.allowance_amount:,}원)'
        )
