from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.fields import EncryptedCharField, EncryptedTextField
from apps.core.models import BaseModel
from apps.core.utils import generate_document_number, generate_sequential_code
from apps.inventory.models import Product


class Partner(BaseModel):
    BUSINESS_KEY_FIELD = 'code'

    class PartnerType(models.TextChoices):
        CUSTOMER = 'CUSTOMER', '고객'
        SUPPLIER = 'SUPPLIER', '공급처'
        BOTH = 'BOTH', '고객/공급처'

    TYPE_PREFIX_MAP = {
        'CUSTOMER': 'CUS',
        'SUPPLIER': 'SUP',
        'BOTH': 'SUS',
    }

    code = models.CharField('거래처코드', max_length=30, unique=True)
    name = models.CharField('거래처명', max_length=200)
    partner_type = models.CharField(
        '유형', max_length=10,
        choices=PartnerType.choices, default=PartnerType.CUSTOMER,
    )
    business_number = models.CharField('사업자번호', max_length=20, blank=True)
    representative = models.CharField('대표자', max_length=50, blank=True)
    contact_name = models.CharField('담당자', max_length=50, blank=True)
    phone = EncryptedCharField('전화번호', max_length=500, blank=True)
    email = EncryptedCharField('이메일', max_length=500, blank=True)
    address = EncryptedTextField('주소', blank=True)
    address_road = EncryptedTextField('도로명주소', blank=True)
    address_detail = EncryptedTextField('상세주소', blank=True)
    bank_name = models.CharField('은행명', max_length=50, blank=True)
    bank_account = EncryptedCharField('계좌번호', max_length=500, blank=True)
    bank_holder = models.CharField('예금주', max_length=50, blank=True)
    lead_time_days = models.PositiveIntegerField(
        '리드타임(일)', default=0,
        help_text='평균 납품 소요일',
    )
    default_currency = models.ForeignKey(
        'accounting.Currency', verbose_name='기본통화',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    default_bank_account = models.ForeignKey(
        'accounting.BankAccount', verbose_name='기본 입금계좌',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='default_partners',
        help_text='주문 생성 시 자동 설정되는 입금계좌',
    )
    commission_bank_account = models.ForeignKey(
        'accounting.BankAccount', verbose_name='수수료 계좌',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='commission_partners',
        help_text='수수료 자동 차감 계좌 (미설정 시 기본계좌)',
    )
    store_module = models.CharField(
        '스토어 모듈', max_length=50, blank=True, default='',
        help_text='연결된 스토어 모듈 ID (예: naver_smartstore, coupang, direct_sale)',
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

    def calculate_commission(self, base_amount, product=None):
        """수수료 합산 계산 — product 지정 시 제품별 수수료 우선, 없으면 거래처 전체 수수료"""
        from apps.sales.commission import CommissionRate
        total = 0
        if product:
            # 제품별 수수료가 있으면 제품별로 계산
            product_rates = CommissionRate.objects.filter(
                partner=self, is_active=True, product=product,
            )
            if product_rates.exists():
                for item in product_rates:
                    total += item.calculate(base_amount)
                return total
        # 제품별 수수료 없으면 거래처 전체 수수료
        for item in CommissionRate.objects.filter(
            partner=self, is_active=True, product__isnull=True,
        ):
            total += item.calculate(base_amount)
        return total

    @classmethod
    def generate_next_code(cls, partner_type):
        """거래처 유형별 다음 코드 생성"""
        prefix = cls.TYPE_PREFIX_MAP.get(partner_type, 'CUS')
        return generate_sequential_code(cls, 'code', prefix, digits=3)

    def save(self, *args, **kwargs):
        if self.address_road or self.address_detail:
            self.address = f'{self.address_road} {self.address_detail}'.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Customer(BaseModel):
    BUSINESS_KEY_FIELD = 'code'

    code = models.CharField('고객코드', max_length=30, unique=True, blank=True)
    name = models.CharField('고객명', max_length=100)
    phone = EncryptedCharField('연락처', max_length=500)
    email = EncryptedCharField('이메일', max_length=500, blank=True)
    address = EncryptedTextField('주소', blank=True)
    address_road = EncryptedTextField('도로명주소', blank=True)
    address_detail = EncryptedTextField('상세주소', blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '고객'
        verbose_name_plural = '고객'
        ordering = ['code']

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_sequential_code(
                Customer, 'code', 'CST', digits=4,
            )
        if self.address_road or self.address_detail:
            self.address = f'{self.address_road} {self.address_detail}'.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.code}] {self.name}"


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
    BUSINESS_KEY_FIELD = 'order_number'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '작성중'
        CONFIRMED = 'CONFIRMED', '확정'
        PARTIAL_SHIPPED = 'PARTIAL_SHIPPED', '부분출고'
        SHIPPED = 'SHIPPED', '출고완료'
        DELIVERED = 'DELIVERED', '배송완료'
        CLOSED = 'CLOSED', '종결'
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
        'PARTIAL_SHIPPED': ['PARTIAL_SHIPPED', 'SHIPPED', 'CANCELLED'],
        'SHIPPED': ['DELIVERED'],
        'DELIVERED': ['CLOSED'],
        'CLOSED': [],
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
    shipping_address = EncryptedTextField('배송주소', blank=True)
    shipping_address_road = EncryptedTextField('배송 도로명주소', blank=True)
    shipping_address_detail = EncryptedTextField('배송 상세주소', blank=True)
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
        if self.shipping_address_road or self.shipping_address_detail:
            self.shipping_address = f'{self.shipping_address_road} {self.shipping_address_detail}'.strip()
        super().save(*args, **kwargs)

    def update_total(self):
        from django.db.models import Sum
        totals = self.items.filter(is_active=True).aggregate(
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
    BUSINESS_KEY_FIELD = 'quote_number'

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
        totals = self.quote_items.filter(is_active=True).aggregate(
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
    api_key = EncryptedCharField('API Key', max_length=500, blank=True)
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
    BUSINESS_KEY_FIELD = 'shipment_number'

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
    receiver_phone = EncryptedCharField(
        '수취인연락처', max_length=500, blank=True,
    )
    receiver_address = EncryptedTextField('배송주소', blank=True)
    receiver_address_road = EncryptedTextField('수취인 도로명주소', blank=True)
    receiver_address_detail = EncryptedTextField('수취인 상세주소', blank=True)
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
        if self.receiver_address_road or self.receiver_address_detail:
            self.receiver_address = f'{self.receiver_address_road} {self.receiver_address_detail}'.strip()
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


class PriceRule(BaseModel):
    """거래처별/수량별 가격규칙"""
    product = models.ForeignKey(
        Product, verbose_name='제품',
        on_delete=models.PROTECT, related_name='price_rules',
    )
    partner = models.ForeignKey(
        Partner, verbose_name='거래처',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='price_rules',
    )
    customer = models.ForeignKey(
        Customer, verbose_name='고객',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='price_rules',
    )
    min_quantity = models.PositiveIntegerField('최소수량', default=1)
    unit_price = models.DecimalField(
        '적용단가', max_digits=15, decimal_places=0,
        null=True, blank=True,
        help_text='설정 시 이 단가 적용. 비워두면 기본 판매단가에서 할인',
    )
    discount_rate = models.DecimalField(
        '할인율(%)', max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    valid_from = models.DateField('적용시작일', null=True, blank=True)
    valid_to = models.DateField('적용종료일', null=True, blank=True)
    priority = models.PositiveIntegerField('우선순위', default=0, help_text='높을수록 우선 적용')
    history = HistoricalRecords()

    class Meta:
        verbose_name = '가격규칙'
        verbose_name_plural = '가격규칙'
        ordering = ['-priority', 'min_quantity']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'partner', 'customer', 'min_quantity'],
                name='uq_price_rule',
            ),
        ]

    def __str__(self):
        parts = [str(self.product)]
        if self.partner:
            parts.append(str(self.partner))
        if self.customer:
            parts.append(str(self.customer))
        parts.append(f'Q>={self.min_quantity}')
        return ' / '.join(parts)


from apps.sales.commission import CommissionRate, CommissionRecord  # noqa
