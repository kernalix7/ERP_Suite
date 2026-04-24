"""카드매출전표(CardSalesSlip) — 국세청 3대 증빙 중 현금영수증·세금계산서와 나란히.

신용카드 승인분 중 별도 매출전표가 필요한 경우 (오프라인 POS, 수기 승인 등).
TaxInvoice/CashReceipt과 대비되는 별도 증빙 엔티티로 분리한다.
"""
from django.core.validators import MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class CardSalesSlip(BaseModel):
    """카드매출전표 (신용/체크카드 승인분 매출 증빙)."""

    BUSINESS_KEY_FIELD = 'slip_number'

    class Status(models.TextChoices):
        APPROVED = 'APPROVED', '승인'
        CANCELLED = 'CANCELLED', '취소'

    class CardBrand(models.TextChoices):
        VISA = 'VISA', 'VISA'
        MASTER = 'MASTER', 'Mastercard'
        AMEX = 'AMEX', 'American Express'
        JCB = 'JCB', 'JCB'
        UNION = 'UNION', 'UnionPay'
        DOMESTIC = 'DOMESTIC', '국내카드'
        OTHER = 'OTHER', '기타'

    slip_number = models.CharField(
        '매출전표번호', max_length=30, unique=True, blank=True,
    )
    approved_at = models.DateTimeField('승인일시')
    approval_code = models.CharField(
        '카드승인번호', max_length=32,
        help_text='카드사 승인 시 발급되는 고유 번호',
    )
    card_brand = models.CharField(
        '카드사', max_length=16,
        choices=CardBrand.choices, default=CardBrand.DOMESTIC,
    )
    card_number_masked = models.CharField(
        '카드번호(마스킹)', max_length=32,
        help_text='4-****-****-1234 포맷. 평문 저장 금지.',
    )
    merchant_number = models.CharField(
        '가맹점번호', max_length=32, blank=True,
    )
    supply_amount = models.DecimalField(
        '공급가액', max_digits=15, decimal_places=0,
        default=0, validators=[MinValueValidator(0)],
    )
    vat = models.DecimalField(
        '부가세', max_digits=15, decimal_places=0,
        default=0, validators=[MinValueValidator(0)],
    )
    total_amount = models.DecimalField(
        '총금액', max_digits=15, decimal_places=0,
        default=0, validators=[MinValueValidator(0)],
    )
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.APPROVED,
    )
    cancelled_at = models.DateTimeField('취소일시', null=True, blank=True)
    cancel_reason = models.CharField('취소사유', max_length=200, blank=True)

    order = models.ForeignKey(
        'sales.Order', verbose_name='주문',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='card_sales_slips',
    )
    partner = models.ForeignKey(
        'sales.Partner', verbose_name='거래처',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='card_sales_slips',
    )
    card_transaction = models.ForeignKey(
        'accounting.CardTransaction', verbose_name='카드거래',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='sales_slips',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '카드매출전표'
        verbose_name_plural = '카드매출전표'
        ordering = ['-approved_at']
        indexes = [
            models.Index(fields=['approved_at'], name='idx_cardslip_approved'),
            models.Index(fields=['approval_code'], name='idx_cardslip_approval'),
            models.Index(fields=['status'], name='idx_cardslip_status'),
        ]

    def __str__(self):
        return f'{self.slip_number} ({self.card_brand}) {self.total_amount:,}원'

    def save(self, *args, **kwargs):
        if not self.slip_number:
            from apps.core.utils import generate_document_number
            self.slip_number = generate_document_number(
                CardSalesSlip, 'slip_number', 'CS',
            )
        if self.supply_amount is not None and self.vat is not None:
            self.total_amount = self.supply_amount + self.vat
        super().save(*args, **kwargs)
