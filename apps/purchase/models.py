from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel
from apps.core.utils import generate_document_number
from apps.inventory.models import Product


class PurchaseOrder(BaseModel):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '작성중'
        CONFIRMED = 'CONFIRMED', '확정'
        PARTIAL_RECEIVED = 'PARTIAL_RECEIVED', '부분입고'
        RECEIVED = 'RECEIVED', '입고완료'
        CANCELLED = 'CANCELLED', '취소'

    STATUS_TRANSITIONS = {
        'DRAFT': ['CONFIRMED', 'CANCELLED'],
        'CONFIRMED': ['CANCELLED'],
        'PARTIAL_RECEIVED': ['CANCELLED'],
        'RECEIVED': [],
        'CANCELLED': [],
    }

    po_number = models.CharField('발주번호', max_length=30, unique=True, blank=True)
    partner = models.ForeignKey(
        'sales.Partner', verbose_name='공급처',
        on_delete=models.PROTECT,
        limit_choices_to={'partner_type__in': ['SUPPLIER', 'BOTH']},
        related_name='purchase_orders',
    )
    order_date = models.DateField('발주일')
    expected_date = models.DateField('입고예정일', null=True, blank=True)
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.DRAFT,
    )
    total_amount = models.DecimalField(
        '공급가액', max_digits=15, decimal_places=0, default=0,
    )
    tax_total = models.DecimalField(
        '부가세 합계', max_digits=15, decimal_places=0, default=0,
    )
    grand_total = models.DecimalField(
        '총합계(세포함)', max_digits=15, decimal_places=0, default=0,
    )
    vat_included = models.BooleanField(
        'VAT 포함 금액 입력', default=False,
        help_text='체크 시 입력 금액을 VAT 포함 금액으로 간주합니다.',
    )
    approval_request = models.ForeignKey(
        'approval.ApprovalRequest',
        verbose_name='품의서',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='purchase_orders',
        limit_choices_to={'category': 'PURCHASE'},
    )
    currency = models.ForeignKey(
        'accounting.Currency', verbose_name='통화',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    exchange_rate = models.DecimalField(
        '적용환율', max_digits=15, decimal_places=4, default=1,
    )
    attachment = models.FileField(
        '첨부파일',
        upload_to='purchase/attachments/',
        blank=True,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '발주서'
        verbose_name_plural = '발주서'
        ordering = ['-po_number']
        indexes = [
            models.Index(fields=['status'], name='idx_po_status'),
            models.Index(fields=['order_date'], name='idx_po_order_date'),
            models.Index(fields=['status', 'order_date'], name='idx_po_status_date'),
        ]

    def __str__(self):
        return self.po_number

    def save(self, *args, **kwargs):
        if not self.po_number:
            self.po_number = generate_document_number(PurchaseOrder, 'po_number', 'PO')
        # 결재 필수화 체크: CONFIRMED 전환 시 승인된 품의서 필요
        if self.status == 'CONFIRMED' and self.pk:
            from django.conf import settings
            if getattr(settings, 'PO_APPROVAL_REQUIRED', False):
                if not self.approval_request or self.approval_request.status != 'APPROVED':
                    from django.core.exceptions import ValidationError
                    raise ValidationError(
                        '발주 확정을 위해 승인된 품의서가 필요합니다. '
                        '품의서를 먼저 등록하고 결재를 받아주세요.'
                    )
        super().save(*args, **kwargs)

    def update_total(self):
        from django.db.models import Sum
        totals = self.items.aggregate(
            total_amount=Sum('amount'),
            tax_total=Sum('tax_amount'),
        )
        self.total_amount = totals['total_amount'] or 0
        self.tax_total = totals['tax_total'] or 0
        self.grand_total = self.total_amount + self.tax_total
        self.save(update_fields=['total_amount', 'tax_total', 'grand_total', 'updated_at'])


class PurchaseOrderItem(BaseModel):
    purchase_order = models.ForeignKey(
        PurchaseOrder, verbose_name='발주서',
        on_delete=models.CASCADE, related_name='items',
    )
    product = models.ForeignKey(
        Product, verbose_name='제품', on_delete=models.PROTECT,
    )
    quantity = models.PositiveIntegerField('수량')
    unit_price = models.DecimalField('단가', max_digits=12, decimal_places=0, validators=[MinValueValidator(0)])
    amount = models.DecimalField('공급가액', max_digits=15, decimal_places=0, default=0)
    tax_amount = models.DecimalField('부가세', max_digits=15, decimal_places=0, default=0)
    received_quantity = models.PositiveIntegerField('입고수량', default=0)
    receipt_file = models.FileField('영수증', upload_to='receipts/purchase/', blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '발주항목'
        verbose_name_plural = '발주항목'
        ordering = ['pk']

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'

    def save(self, *args, **kwargs):
        # 금액 미입력 시 수량×단가로 자동 계산
        if not self.amount and self.quantity and self.unit_price:
            self.amount = int(self.quantity * self.unit_price)
        # amount(총액)이 사용자 입력 원본 — 원단위 그대로 보존
        if self.purchase_order.vat_included:
            # amount = VAT 포함 총액 → 공급가액/부가세 역산
            input_total = int(self.amount)
            self.amount = int(Decimal(str(input_total)) / Decimal('1.1'))
            self.tax_amount = input_total - int(self.amount)
        else:
            # amount = 공급가액 그대로
            self.tax_amount = int(self.amount * Decimal('0.1'))
        # 단가 역산 (참고용, 이동평균 원가 계산에도 사용)
        if self.quantity and self.quantity > 0:
            self.unit_price = int(Decimal(str(int(self.amount))) / self.quantity)
        super().save(*args, **kwargs)

    @property
    def remaining_quantity(self):
        return self.quantity - self.received_quantity


class GoodsReceipt(BaseModel):
    receipt_number = models.CharField('입고번호', max_length=30, unique=True, blank=True)
    purchase_order = models.ForeignKey(
        PurchaseOrder, verbose_name='발주서',
        on_delete=models.PROTECT, related_name='receipts',
    )
    warehouse = models.ForeignKey(
        'inventory.Warehouse', verbose_name='입고창고',
        null=True, blank=True,
        on_delete=models.PROTECT,
        help_text='입고 대상 창고',
    )
    receipt_date = models.DateField('입고일')
    history = HistoricalRecords()

    class Meta:
        verbose_name = '입고확인'
        verbose_name_plural = '입고확인'
        ordering = ['-receipt_number']

    def __str__(self):
        return self.receipt_number

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = generate_document_number(GoodsReceipt, 'receipt_number', 'GR')
        super().save(*args, **kwargs)


class GoodsReceiptItem(BaseModel):
    goods_receipt = models.ForeignKey(
        GoodsReceipt, verbose_name='입고확인',
        on_delete=models.CASCADE, related_name='items',
    )
    po_item = models.ForeignKey(
        PurchaseOrderItem, verbose_name='발주항목',
        on_delete=models.PROTECT, related_name='receipt_items',
    )
    received_quantity = models.PositiveIntegerField('입고수량')
    is_inspected = models.BooleanField('검수완료', default=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '입고항목'
        verbose_name_plural = '입고항목'
        ordering = ['pk']

    def __str__(self):
        return f'{self.po_item.product.name} x {self.received_quantity}'
