from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel
from apps.core.storage import hashed_upload_path
from apps.core.utils import generate_document_number
from apps.inventory.models import Product


class PurchaseOrder(BaseModel):
    BUSINESS_KEY_FIELD = 'po_number'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '작성중'
        CONFIRMED = 'CONFIRMED', '확정'
        PARTIAL_RECEIVED = 'PARTIAL_RECEIVED', '부분입고'
        RECEIVED = 'RECEIVED', '입고완료'
        CANCELLED = 'CANCELLED', '취소'

    STATUS_TRANSITIONS = {
        'DRAFT': ['CONFIRMED', 'CANCELLED'],
        'CONFIRMED': ['PARTIAL_RECEIVED', 'RECEIVED', 'CANCELLED'],
        'PARTIAL_RECEIVED': ['RECEIVED', 'CANCELLED'],
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
    is_taxable = models.BooleanField(
        '과세 거래', default=True,
        help_text='면세(중고거래, 개인 간 현금거래 등)인 경우 해제',
    )

    class VatDeductionType(models.TextChoices):
        DEDUCTIBLE = 'DEDUCTIBLE', '일반매입(공제)'
        DEEMED = 'DEEMED', '의제매입세액(면세 농축수산물)'
        NON_DEDUCTIBLE = 'NON_DEDUCTIBLE', '공제받지못할매입(접대비·사업무관)'

    vat_deduction_type = models.CharField(
        '매입세액 구분', max_length=20,
        choices=VatDeductionType.choices,
        default=VatDeductionType.DEDUCTIBLE,
        help_text='부가세 신고 시 매입세액 구분 — 의제/불공제는 별도 집계',
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
        upload_to=hashed_upload_path('purchase/attachments'),
        blank=True,
    )
    attachment_filename = models.CharField('첨부파일 원본명', max_length=255, blank=True)
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
    receipt_file = models.FileField('영수증', upload_to=hashed_upload_path('receipts/purchase'), blank=True)
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
        # 부가세 계산
        if not self.purchase_order.is_taxable:
            # 면세 거래: 부가세 없음
            self.tax_amount = 0
        elif self.purchase_order.vat_included:
            # amount = VAT 포함 총액 → 공급가액/부가세 역산
            input_total = int(self.amount)
            self.amount = int(Decimal(str(input_total)) / Decimal('1.1'))
            self.tax_amount = input_total - int(self.amount)
        else:
            # amount = 공급가액 그대로
            self.tax_amount = int(self.amount * Decimal('0.1'))
        # 단가 = 공급가액 / 수량 (VAT 미포함 단가로 저장)
        if self.quantity and self.quantity > 0:
            self.unit_price = int(Decimal(str(int(self.amount))) / self.quantity)
        super().save(*args, **kwargs)

    @property
    def remaining_quantity(self):
        return self.quantity - self.received_quantity


class GoodsReceipt(BaseModel):
    BUSINESS_KEY_FIELD = 'receipt_number'

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
        indexes = [
            models.Index(fields=['receipt_date'], name='idx_gr_receipt_date'),
            models.Index(fields=['purchase_order', 'receipt_date'], name='idx_gr_po_date'),
        ]

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
    is_fixed_asset = models.BooleanField('자산등록', default=False)
    asset_category = models.ForeignKey(
        'asset.AssetCategory', verbose_name='자산분류',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '입고항목'
        verbose_name_plural = '입고항목'
        ordering = ['pk']

    def __str__(self):
        return f'{self.po_item.product.name} x {self.received_quantity}'


class RFQ(BaseModel):
    """견적요청서"""
    BUSINESS_KEY_FIELD = 'rfq_number'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '작성중'
        SENT = 'SENT', '발송'
        RECEIVED = 'RECEIVED', '접수'
        COMPARED = 'COMPARED', '비교완료'
        CLOSED = 'CLOSED', '종결'

    rfq_number = models.CharField('견적요청번호', max_length=30, unique=True, blank=True)
    title = models.CharField('제목', max_length=200)
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.DRAFT,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='요청자',
        on_delete=models.PROTECT,
        related_name='rfqs',
    )
    due_date = models.DateField('마감일', null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '견적요청'
        verbose_name_plural = '견적요청'
        ordering = ['-rfq_number']
        indexes = [
            models.Index(fields=['status'], name='idx_rfq_status'),
        ]

    def __str__(self):
        return f'{self.rfq_number} - {self.title}'

    def save(self, *args, **kwargs):
        if not self.rfq_number:
            from django.utils import timezone
            today = timezone.now().strftime('%Y%m%d')
            last = RFQ.objects.filter(
                rfq_number__startswith=f'RFQ-{today}',
            ).order_by('-rfq_number').first()
            seq = int(last.rfq_number.split('-')[-1]) + 1 if last else 1
            self.rfq_number = f'RFQ-{today}-{seq:04d}'
        super().save(*args, **kwargs)


class RFQItem(BaseModel):
    """견적요청 항목"""
    rfq = models.ForeignKey(
        RFQ, verbose_name='견적요청',
        on_delete=models.CASCADE, related_name='items',
    )
    product = models.ForeignKey(
        Product, verbose_name='제품',
        on_delete=models.PROTECT,
    )
    quantity = models.DecimalField('수량', max_digits=15, decimal_places=2)
    specifications = models.TextField('사양', blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '견적요청항목'
        verbose_name_plural = '견적요청항목'
        ordering = ['pk']

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'


class RFQResponse(BaseModel):
    """견적응답"""
    rfq = models.ForeignKey(
        RFQ, verbose_name='견적요청',
        on_delete=models.CASCADE, related_name='responses',
    )
    partner = models.ForeignKey(
        'sales.Partner', verbose_name='공급처',
        on_delete=models.PROTECT,
        limit_choices_to={'partner_type__in': ['SUPPLIER', 'BOTH']},
        related_name='rfq_responses',
    )
    response_date = models.DateField('응답일')
    total_amount = models.DecimalField(
        '총금액', max_digits=15, decimal_places=0, default=0,
    )
    delivery_days = models.PositiveIntegerField('납기(일)', default=0)
    is_selected = models.BooleanField('낙찰', default=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '견적응답'
        verbose_name_plural = '견적응답'
        ordering = ['total_amount']
        indexes = [
            models.Index(fields=['rfq', 'is_selected'], name='idx_rfqresp_rfq_selected'),
        ]

    def __str__(self):
        return f'{self.partner.name} - {self.total_amount}'


class VendorScore(BaseModel):
    """공급처 평가"""
    partner = models.ForeignKey(
        'sales.Partner', verbose_name='공급처',
        on_delete=models.PROTECT,
        limit_choices_to={'partner_type__in': ['SUPPLIER', 'BOTH']},
        related_name='vendor_scores',
    )
    evaluation_date = models.DateField('평가일')
    delivery_score = models.PositiveIntegerField(
        '납기점수', validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='1-5',
    )
    quality_score = models.PositiveIntegerField(
        '품질점수', validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='1-5',
    )
    price_score = models.PositiveIntegerField(
        '가격점수', validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='1-5',
    )
    service_score = models.PositiveIntegerField(
        '서비스점수', validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='1-5',
    )
    overall_score = models.DecimalField(
        '종합점수', max_digits=3, decimal_places=1, default=0,
    )
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='평가자',
        on_delete=models.PROTECT,
        related_name='vendor_evaluations',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '공급처평가'
        verbose_name_plural = '공급처평가'
        ordering = ['-evaluation_date']
        indexes = [
            models.Index(fields=['evaluation_date'], name='idx_vendor_eval_date'),
        ]

    def __str__(self):
        return f'{self.partner.name} - {self.overall_score}'

    def save(self, *args, **kwargs):
        self.overall_score = Decimal(str(
            (self.delivery_score + self.quality_score + self.price_score + self.service_score) / 4
        )).quantize(Decimal('0.1'))
        super().save(*args, **kwargs)
