from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel
from apps.inventory.models import Product


class PurchaseOrder(BaseModel):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '작성중'
        CONFIRMED = 'CONFIRMED', '확정'
        PARTIAL_RECEIVED = 'PARTIAL_RECEIVED', '부분입고'
        RECEIVED = 'RECEIVED', '입고완료'
        CANCELLED = 'CANCELLED', '취소'

    po_number = models.CharField('발주번호', max_length=30, unique=True)
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
    history = HistoricalRecords()

    class Meta:
        verbose_name = '발주서'
        verbose_name_plural = '발주서'
        ordering = ['-order_date', '-pk']
        indexes = [
            models.Index(fields=['status'], name='idx_po_status'),
            models.Index(fields=['order_date'], name='idx_po_order_date'),
            models.Index(fields=['status', 'order_date'], name='idx_po_status_date'),
        ]

    def __str__(self):
        return self.po_number

    def update_total(self):
        items = self.items.all()
        self.total_amount = sum(item.amount for item in items)
        self.tax_total = sum(item.tax_amount for item in items)
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
    history = HistoricalRecords()

    class Meta:
        verbose_name = '발주항목'
        verbose_name_plural = '발주항목'

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'

    def save(self, *args, **kwargs):
        self.amount = self.quantity * self.unit_price
        self.tax_amount = int(self.amount * Decimal('0.1'))
        super().save(*args, **kwargs)

    @property
    def remaining_quantity(self):
        return self.quantity - self.received_quantity


class GoodsReceipt(BaseModel):
    receipt_number = models.CharField('입고번호', max_length=30, unique=True)
    purchase_order = models.ForeignKey(
        PurchaseOrder, verbose_name='발주서',
        on_delete=models.PROTECT, related_name='receipts',
    )
    receipt_date = models.DateField('입고일')
    history = HistoricalRecords()

    class Meta:
        verbose_name = '입고확인'
        verbose_name_plural = '입고확인'
        ordering = ['-receipt_date', '-pk']

    def __str__(self):
        return self.receipt_number


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

    def __str__(self):
        return f'{self.po_item.product.name} x {self.received_quantity}'
