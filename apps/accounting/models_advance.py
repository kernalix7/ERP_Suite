from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class AdvanceStatus(models.TextChoices):
    UNAPPLIED = 'UNAPPLIED', '미적용'
    PARTIAL = 'PARTIAL', '부분적용'
    APPLIED = 'APPLIED', '전액적용'


class AdvanceReceived(BaseModel):
    """선수금 — 주문 전에 받은 돈(계약금 등)"""
    partner = models.ForeignKey(
        'sales.Partner', null=True, blank=True,
        on_delete=models.PROTECT, verbose_name='거래처',
        related_name='advance_received_set',
    )
    customer = models.ForeignKey(
        'sales.Customer', null=True, blank=True,
        on_delete=models.PROTECT, verbose_name='고객',
        related_name='advance_received_set',
    )
    amount = models.DecimalField(max_digits=15, decimal_places=0, verbose_name='선수금액')
    received_date = models.DateField(verbose_name='수령일')
    received_voucher = models.ForeignKey(
        'accounting.Voucher', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='advance_receipts',
        verbose_name='수령전표',
    )
    applied_to_order = models.ForeignKey(
        'sales.Order', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='applied_advances',
        verbose_name='적용주문',
    )
    applied_amount = models.DecimalField(
        max_digits=15, decimal_places=0, default=0, verbose_name='적용금액',
    )
    status = models.CharField(
        max_length=16, choices=AdvanceStatus.choices,
        default=AdvanceStatus.UNAPPLIED, verbose_name='상태',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '선수금'
        verbose_name_plural = '선수금 목록'
        ordering = ['-received_date']

    def __str__(self):
        return f'선수금 {self.amount:,}원 ({self.received_date})'

    @property
    def remaining_amount(self):
        return self.amount - self.applied_amount


class AdvancePaid(BaseModel):
    """선급금 — 물품 수령 전 지급한 돈(계약금 등)"""
    partner = models.ForeignKey(
        'sales.Partner', null=True, blank=True,
        on_delete=models.PROTECT, verbose_name='거래처',
        related_name='advance_paid_set',
        limit_choices_to={'partner_type__in': ['SUPPLIER', 'BOTH']},
    )
    amount = models.DecimalField(max_digits=15, decimal_places=0, verbose_name='선급금액')
    paid_date = models.DateField(verbose_name='지급일')
    paid_voucher = models.ForeignKey(
        'accounting.Voucher', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='advance_payments',
        verbose_name='지급전표',
    )
    applied_to_po = models.ForeignKey(
        'purchase.PurchaseOrder', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='applied_advance_payments',
        verbose_name='적용발주서',
    )
    applied_amount = models.DecimalField(
        max_digits=15, decimal_places=0, default=0, verbose_name='적용금액',
    )
    status = models.CharField(
        max_length=16, choices=AdvanceStatus.choices,
        default=AdvanceStatus.UNAPPLIED, verbose_name='상태',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '선급금'
        verbose_name_plural = '선급금 목록'
        ordering = ['-paid_date']

    def __str__(self):
        return f'선급금 {self.amount:,}원 ({self.paid_date})'

    @property
    def remaining_amount(self):
        return self.amount - self.applied_amount
