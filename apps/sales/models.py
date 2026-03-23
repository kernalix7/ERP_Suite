from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel
from apps.core.utils import generate_document_number
from apps.inventory.models import Product


class Partner(BaseModel):
    class PartnerType(models.TextChoices):
        CUSTOMER = 'CUSTOMER', '고객'
        SUPPLIER = 'SUPPLIER', '공급처'
        BOTH = 'BOTH', '고객/공급처'

    code = models.CharField('거래처코드', max_length=30, unique=True)
    name = models.CharField('거래처명', max_length=200)
    partner_type = models.CharField(
        '유형', max_length=10,
        choices=PartnerType.choices, default=PartnerType.CUSTOMER,
    )
    business_number = models.CharField('사업자번호', max_length=20, blank=True)
    representative = models.CharField('대표자', max_length=50, blank=True)
    contact_name = models.CharField('담당자', max_length=50, blank=True)
    phone = models.CharField('전화번호', max_length=20, blank=True)
    email = models.EmailField('이메일', blank=True)
    address = models.TextField('주소', blank=True)
    lead_time_days = models.PositiveIntegerField(
        '리드타임(일)', default=0,
        help_text='평균 납품 소요일',
    )
    default_currency = models.ForeignKey(
        'accounting.Currency', verbose_name='기본통화',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '거래처'
        verbose_name_plural = '거래처'
        ordering = ['name']
        indexes = [
            models.Index(fields=['partner_type'], name='idx_partner_type'),
        ]

    @property
    def total_commission_rate(self):
        """활성 수수료 항목 중 정률(%) 항목의 합산 수수료율"""
        from apps.sales.commission import CommissionRate
        rates = CommissionRate.objects.filter(
            partner=self, is_active=True,
            calc_type='PERCENT', product__isnull=True,
        )
        return sum(r.rate for r in rates)

    @property
    def total_fixed_commission(self):
        """활성 수수료 항목 중 정액(원) 항목의 합산"""
        from apps.sales.commission import CommissionRate
        items = CommissionRate.objects.filter(
            partner=self, is_active=True,
            calc_type='FIXED', product__isnull=True,
        )
        return sum(int(i.fixed_amount) for i in items)

    def calculate_commission(self, base_amount):
        """모든 활성 수수료 항목 합산 계산"""
        from apps.sales.commission import CommissionRate
        total = 0
        for item in CommissionRate.objects.filter(
            partner=self, is_active=True, product__isnull=True,
        ):
            total += item.calculate(base_amount)
        return total

    def __str__(self):
        return self.name


class Customer(BaseModel):
    name = models.CharField('고객명', max_length=100)
    phone = models.CharField('연락처', max_length=20)
    email = models.EmailField('이메일', blank=True)
    address = models.TextField('주소', blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '고객'
        verbose_name_plural = '고객'
        ordering = ['name']

    def __str__(self):
        return self.name


class CustomerPurchase(BaseModel):
    customer = models.ForeignKey(
        Customer, verbose_name='고객',
        on_delete=models.CASCADE, related_name='purchases',
    )
    product = models.ForeignKey(
        Product, verbose_name='구매제품',
        on_delete=models.PROTECT,
    )
    serial_number = models.CharField('시리얼번호', max_length=100, blank=True)
    purchase_date = models.DateField('구매일', null=True, blank=True)
    warranty_end = models.DateField('보증만료일', null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '고객구매내역'
        verbose_name_plural = '고객구매내역'
        ordering = ['-purchase_date']

    def __str__(self):
        return f'{self.customer.name} - {self.product.name} ({self.serial_number})'

    @property
    def is_warranty_valid(self):
        from datetime import date
        if not self.warranty_end:
            return False
        return self.warranty_end >= date.today()


class Order(BaseModel):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '작성중'
        CONFIRMED = 'CONFIRMED', '확정'
        PARTIAL_SHIPPED = 'PARTIAL_SHIPPED', '부분출고'
        SHIPPED = 'SHIPPED', '출고완료'
        DELIVERED = 'DELIVERED', '배송완료'
        CANCELLED = 'CANCELLED', '취소'

    class OrderType(models.TextChoices):
        NORMAL = 'NORMAL', '일반주문'
        SAMPLE = 'SAMPLE', '샘플주문'
        RETURN = 'RETURN', '반품주문'
        EXCHANGE = 'EXCHANGE', '교환주문'

    # 허용되는 상태 전환 맵
    STATUS_TRANSITIONS = {
        'DRAFT': ['CONFIRMED', 'CANCELLED'],
        'CONFIRMED': ['PARTIAL_SHIPPED', 'SHIPPED', 'CANCELLED'],
        'PARTIAL_SHIPPED': ['PARTIAL_SHIPPED', 'CANCELLED'],
        'SHIPPED': ['DELIVERED'],
        'DELIVERED': [],
        'CANCELLED': [],
    }

    order_number = models.CharField('주문번호', max_length=30, unique=True, blank=True)
    order_type = models.CharField(
        '주문유형', max_length=10,
        choices=OrderType.choices, default=OrderType.NORMAL,
    )
    partner = models.ForeignKey(
        Partner, verbose_name='거래처',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='orders',
    )
    customer = models.ForeignKey(
        Customer, verbose_name='고객',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='orders',
    )
    assigned_to = models.ForeignKey(
        'accounts.User', verbose_name='담당자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='assigned_orders',
    )
    order_date = models.DateField('주문일')
    delivery_date = models.DateField('납기일', null=True, blank=True)
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.DRAFT,
    )
    total_amount = models.DecimalField(
        '공급가액', max_digits=15, decimal_places=0, default=0,
    )
    tax_total = models.DecimalField('부가세 합계', max_digits=15, decimal_places=0, default=0)
    grand_total = models.DecimalField('총합계(세포함)', max_digits=15, decimal_places=0, default=0)
    shipping_address = models.TextField('배송주소', blank=True)
    shipping_method = models.CharField('배송방법', max_length=50, blank=True)
    tracking_number = models.CharField('운송장번호', max_length=50, blank=True)
    vat_included = models.BooleanField(
        'VAT 포함 금액 입력', default=False,
        help_text='체크 시 입력 금액을 VAT 포함 금액으로 간주합니다.',
    )
    shipping_cost = models.DecimalField(
        '배송비', max_digits=12, decimal_places=0, default=0,
        validators=[MinValueValidator(0)],
    )
    bank_account = models.ForeignKey(
        'accounting.BankAccount', verbose_name='입금계좌',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='orders',
    )
    currency = models.ForeignKey(
        'accounting.Currency', verbose_name='통화',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    exchange_rate = models.DecimalField(
        '적용환율', max_digits=15, decimal_places=4, default=1,
    )
    is_paid = models.BooleanField('입금완료', default=False)
    paid_date = models.DateField('입금일', null=True, blank=True)
    is_settled = models.BooleanField('정산완료', default=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '주문'
        verbose_name_plural = '주문'
        ordering = ['-order_number']
        indexes = [
            models.Index(fields=['status'], name='idx_order_status'),
            models.Index(fields=['order_date'], name='idx_order_date'),
            models.Index(fields=['status', 'order_date'], name='idx_order_status_date'),
        ]

    def __str__(self):
        return self.order_number

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = generate_document_number(Order, 'order_number', 'ORD')
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


class OrderItem(BaseModel):
    order = models.ForeignKey(
        Order, verbose_name='주문',
        on_delete=models.CASCADE, related_name='items',
    )
    product = models.ForeignKey(
        Product, verbose_name='제품', on_delete=models.PROTECT,
    )
    quantity = models.PositiveIntegerField('수량')
    cost_price = models.DecimalField(
        '원가', max_digits=12, decimal_places=0, default=0,
        validators=[MinValueValidator(0)],
        help_text='생산원가 (견적서에서 자동 반영)',
    )
    unit_price = models.DecimalField('단가', max_digits=12, decimal_places=0, validators=[MinValueValidator(0)])
    discount_rate = models.DecimalField(
        '할인율(%)', max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
    )
    discount_amount = models.DecimalField(
        '할인금액', max_digits=15, decimal_places=0, default=0,
        validators=[MinValueValidator(0)],
    )
    amount = models.DecimalField('공급가액', max_digits=15, decimal_places=0, default=0)
    tax_amount = models.DecimalField('부가세', max_digits=15, decimal_places=0, default=0)
    total_with_tax = models.DecimalField('합계(세포함)', max_digits=15, decimal_places=0, default=0)
    shipped_quantity = models.PositiveIntegerField('출고수량', default=0)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '주문항목'
        verbose_name_plural = '주문항목'
        ordering = ['pk']

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'

    @property
    def remaining_quantity(self):
        """미출고 수량"""
        return self.quantity - self.shipped_quantity

    def save(self, *args, **kwargs):
        subtotal = self.quantity * self.unit_price
        # 할인: 할인율 우선, 할인금액은 직접 지정 시 사용
        if self.discount_rate > 0:
            self.discount_amount = round(subtotal * self.discount_rate / 100)
        raw_amount = subtotal - self.discount_amount

        if self.order.vat_included:
            # 입력 금액이 VAT 포함 → 역산
            self.amount = int(Decimal(str(int(raw_amount))) / Decimal('1.1'))
            self.tax_amount = int(raw_amount) - int(self.amount)
        else:
            self.amount = raw_amount
            self.tax_amount = round(self.amount * Decimal('0.1'))
        self.total_with_tax = self.amount + self.tax_amount
        super().save(*args, **kwargs)

    @property
    def total_cost(self):
        return self.quantity * self.cost_price

    @property
    def profit(self):
        return int(self.amount) - int(self.total_cost)

    @property
    def profit_rate(self):
        if self.amount == 0:
            return 0
        return round(self.profit / int(self.amount) * 100, 1)


class Quotation(BaseModel):
    """견적서"""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '작성중'
        SENT = 'SENT', '발송'
        ACCEPTED = 'ACCEPTED', '수락'
        REJECTED = 'REJECTED', '거절'
        CONVERTED = 'CONVERTED', '주문전환'
        EXPIRED = 'EXPIRED', '만료'

    quote_number = models.CharField('견적번호', max_length=30, unique=True, blank=True)
    partner = models.ForeignKey(
        Partner, verbose_name='거래처',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='quotations',
    )
    customer = models.ForeignKey(
        Customer, verbose_name='고객',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='quotations',
    )
    quote_date = models.DateField('견적일')
    valid_until = models.DateField('유효기한')
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.DRAFT,
    )
    total_amount = models.DecimalField(
        '공급가액', max_digits=15, decimal_places=0, default=0,
    )
    tax_total = models.DecimalField(
        '부가세', max_digits=15, decimal_places=0, default=0,
    )
    grand_total = models.DecimalField(
        '총합계', max_digits=15, decimal_places=0, default=0,
    )
    vat_included = models.BooleanField(
        'VAT 포함 금액 입력', default=False,
        help_text='체크 시 입력 금액을 VAT 포함 금액으로 간주합니다.',
    )
    bank_account = models.ForeignKey(
        'accounting.BankAccount', verbose_name='입금계좌',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='quotations',
    )
    converted_order = models.ForeignKey(
        Order, verbose_name='전환된 주문',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='source_quotation',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '견적서'
        verbose_name_plural = '견적서'
        ordering = ['-quote_number']
        indexes = [
            models.Index(fields=['status'], name='idx_quotation_status'),
            models.Index(fields=['quote_date'], name='idx_quotation_date'),
        ]

    def __str__(self):
        return self.quote_number

    def save(self, *args, **kwargs):
        if not self.quote_number:
            self.quote_number = generate_document_number(Quotation, 'quote_number', 'QT')
        super().save(*args, **kwargs)

    def update_total(self):
        from django.db.models import Sum
        totals = self.quote_items.aggregate(
            total_amount=Sum('amount'),
            tax_total=Sum('tax_amount'),
        )
        self.total_amount = totals['total_amount'] or 0
        self.tax_total = totals['tax_total'] or 0
        self.grand_total = self.total_amount + self.tax_total
        self.save(update_fields=[
            'total_amount', 'tax_total', 'grand_total', 'updated_at',
        ])


class QuotationItem(BaseModel):
    quotation = models.ForeignKey(
        Quotation, verbose_name='견적서',
        on_delete=models.CASCADE,
        related_name='quote_items',
    )
    product = models.ForeignKey(
        Product, verbose_name='제품', on_delete=models.PROTECT,
    )
    quantity = models.PositiveIntegerField('수량')
    cost_price = models.DecimalField(
        '원가', max_digits=12, decimal_places=0, default=0,
        validators=[MinValueValidator(0)],
        help_text='생산원가 (자동 반영)',
    )
    unit_price = models.DecimalField(
        '공급단가', max_digits=12, decimal_places=0,
        validators=[MinValueValidator(0)],
    )
    discount_rate = models.DecimalField(
        '할인율(%)', max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
    )
    discount_amount = models.DecimalField(
        '할인금액', max_digits=15, decimal_places=0, default=0,
        validators=[MinValueValidator(0)],
    )
    amount = models.DecimalField(
        '공급가액', max_digits=15, decimal_places=0, default=0,
    )
    tax_amount = models.DecimalField(
        '부가세', max_digits=15, decimal_places=0, default=0,
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '견적항목'
        verbose_name_plural = '견적항목'
        ordering = ['pk']

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'

    def save(self, *args, **kwargs):
        subtotal = self.quantity * self.unit_price
        if self.discount_rate > 0:
            self.discount_amount = round(subtotal * self.discount_rate / 100)
        raw_amount = subtotal - self.discount_amount

        if self.quotation.vat_included:
            self.amount = int(Decimal(str(int(raw_amount))) / Decimal('1.1'))
            self.tax_amount = int(raw_amount) - int(self.amount)
        else:
            self.amount = raw_amount
            self.tax_amount = round(self.amount * Decimal('0.1'))
        super().save(*args, **kwargs)

    @property
    def total_cost(self):
        return self.quantity * self.cost_price

    @property
    def profit(self):
        return int(self.amount) - int(self.total_cost)

    @property
    def profit_rate(self):
        if self.amount == 0:
            return 0
        return round(self.profit / int(self.amount) * 100, 1)


class ShippingCarrier(BaseModel):
    """택배사"""
    code = models.CharField('택배사코드', max_length=20, unique=True)
    name = models.CharField('택배사명', max_length=50)
    tracking_url_template = models.URLField(
        '추적URL 템플릿', blank=True,
        help_text='{tracking_number}를 치환',
    )
    api_endpoint = models.URLField('API 엔드포인트', blank=True)
    api_key = models.CharField('API Key', max_length=200, blank=True)
    is_default = models.BooleanField('기본택배사', default=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '택배사'
        verbose_name_plural = '택배사'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_default:
            ShippingCarrier.objects.filter(
                is_default=True,
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class Shipment(BaseModel):
    """배송 추적"""

    class Status(models.TextChoices):
        PREPARING = 'PREPARING', '준비중'
        SHIPPED = 'SHIPPED', '발송'
        IN_TRANSIT = 'IN_TRANSIT', '배송중'
        DELIVERED = 'DELIVERED', '배송완료'
        RETURNED = 'RETURNED', '반품'

    class ShippingType(models.TextChoices):
        PARCEL = 'PARCEL', '택배'
        FREIGHT = 'FREIGHT', '화물'
        QUICK = 'QUICK', '퀵서비스'
        DIRECT = 'DIRECT', '직접배송'
        PICKUP = 'PICKUP', '직접수령'
        ETC = 'ETC', '기타'

    class Carrier(models.TextChoices):
        CJ = 'CJ', 'CJ대한통운'
        HANJIN = 'HANJIN', '한진택배'
        LOTTE = 'LOTTE', '롯데택배'
        LOGEN = 'LOGEN', '로젠택배'
        POST = 'POST', '우체국택배'
        ETC = 'ETC', '기타'

    order = models.ForeignKey(
        Order, verbose_name='주문',
        on_delete=models.CASCADE, related_name='shipments',
    )
    shipment_number = models.CharField(
        '배송번호', max_length=30, unique=True, blank=True,
    )
    shipping_type = models.CharField(
        '배송유형', max_length=10,
        choices=ShippingType.choices, default=ShippingType.PARCEL,
    )
    carrier = models.CharField(
        '택배사', max_length=20,
        choices=Carrier.choices, default=Carrier.CJ,
        blank=True,
    )
    shipping_carrier = models.ForeignKey(
        ShippingCarrier, verbose_name='택배사(상세)',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='shipments',
    )
    tracking_number = models.CharField(
        '운송장번호', max_length=50, blank=True,
    )
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.PREPARING,
    )
    shipped_date = models.DateField('발송일', null=True, blank=True)
    delivered_date = models.DateField('도착일', null=True, blank=True)
    receiver_name = models.CharField(
        '수취인', max_length=100, blank=True,
    )
    receiver_phone = models.CharField(
        '수취인연락처', max_length=20, blank=True,
    )
    receiver_address = models.TextField('배송주소', blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '배송'
        verbose_name_plural = '배송'
        ordering = ['-shipped_date', '-pk']
        indexes = [
            models.Index(
                fields=['status'], name='idx_shipment_status',
            ),
        ]

    def __str__(self):
        return f'{self.shipment_number} ({self.get_status_display()})'

    def save(self, *args, **kwargs):
        if not self.shipment_number:
            self.shipment_number = generate_document_number(Shipment, 'shipment_number', 'SH')
        super().save(*args, **kwargs)

    @property
    def tracking_url(self):
        """택배사별 조회 URL"""
        urls = {
            'CJ': f'https://trace.cjlogistics.com/next/tracking.html?wblNo={self.tracking_number}',
            'HANJIN': f'https://www.hanjin.com/kor/CMS/DeliveryMg498/tracking.do?wblNo={self.tracking_number}',
            'LOTTE': f'https://www.lotteglogis.com/home/reservation/tracking/link498?InvNo={self.tracking_number}',
            'LOGEN': f'https://www.ilogen.com/web/personal/trace/{self.tracking_number}',
            'POST': f'https://service.epost.go.kr/trace.RetrieveDomRi498.postal?sid1={self.tracking_number}',
        }
        return urls.get(self.carrier, '')


class ShipmentItem(BaseModel):
    """배송 항목 — 부분 출고 추적"""
    shipment = models.ForeignKey(
        Shipment, verbose_name='배송',
        on_delete=models.CASCADE, related_name='items',
    )
    order_item = models.ForeignKey(
        OrderItem, verbose_name='주문항목',
        on_delete=models.PROTECT, related_name='shipment_items',
    )
    quantity = models.PositiveIntegerField('출고수량')
    history = HistoricalRecords()

    class Meta:
        verbose_name = '배송항목'
        verbose_name_plural = '배송항목'
        ordering = ['pk']

    def __str__(self):
        return f'{self.order_item.product.name} x {self.quantity}'


class ShipmentTracking(BaseModel):
    """배송 추적 이력"""
    shipment = models.ForeignKey(
        Shipment, on_delete=models.PROTECT,
        related_name='tracking_history', verbose_name='배송',
    )
    status = models.CharField('상태', max_length=50)
    location = models.CharField('위치', max_length=200, blank=True)
    description = models.TextField('상세', blank=True)
    tracked_at = models.DateTimeField('추적시각')
    history = HistoricalRecords()

    class Meta:
        verbose_name = '배송추적'
        verbose_name_plural = '배송추적'
        ordering = ['-tracked_at']

    def __str__(self):
        return f'{self.shipment.shipment_number} - {self.status} ({self.tracked_at})'


from apps.sales.commission import CommissionRate, CommissionRecord  # noqa
