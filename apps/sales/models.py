from decimal import Decimal

from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel
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
    history = HistoricalRecords()

    class Meta:
        verbose_name = '거래처'
        verbose_name_plural = '거래처'
        ordering = ['name']

    def __str__(self):
        return self.name


class Customer(BaseModel):
    name = models.CharField('고객명', max_length=100)
    phone = models.CharField('연락처', max_length=20)
    email = models.EmailField('이메일', blank=True)
    address = models.TextField('주소', blank=True)
    purchase_date = models.DateField('구매일', null=True, blank=True)
    product = models.ForeignKey(
        Product, verbose_name='구매제품',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    serial_number = models.CharField('시리얼번호', max_length=100, blank=True)
    warranty_end = models.DateField('보증만료일', null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '고객'
        verbose_name_plural = '고객'
        ordering = ['-purchase_date']

    def __str__(self):
        return self.name

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
        SHIPPED = 'SHIPPED', '출고완료'
        DELIVERED = 'DELIVERED', '배송완료'
        CANCELLED = 'CANCELLED', '취소'

    order_number = models.CharField('주문번호', max_length=30, unique=True)
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
    history = HistoricalRecords()

    class Meta:
        verbose_name = '주문'
        verbose_name_plural = '주문'
        ordering = ['-order_date', '-pk']
        indexes = [
            models.Index(fields=['status'], name='idx_order_status'),
            models.Index(fields=['order_date'], name='idx_order_date'),
            models.Index(fields=['status', 'order_date'], name='idx_order_status_date'),
        ]

    def __str__(self):
        return self.order_number

    def update_total(self):
        items = self.items.all()
        self.total_amount = sum(item.amount for item in items)
        self.tax_total = sum(item.tax_amount for item in items)
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
    unit_price = models.DecimalField('단가', max_digits=12, decimal_places=0)
    amount = models.DecimalField('공급가액', max_digits=15, decimal_places=0, default=0)
    tax_amount = models.DecimalField('부가세', max_digits=15, decimal_places=0, default=0)
    total_with_tax = models.DecimalField('합계(세포함)', max_digits=15, decimal_places=0, default=0)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '주문항목'
        verbose_name_plural = '주문항목'

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'

    def save(self, *args, **kwargs):
        self.amount = self.quantity * self.unit_price
        self.tax_amount = int(self.amount * Decimal('0.1'))
        self.total_with_tax = self.amount + self.tax_amount
        super().save(*args, **kwargs)


class Quotation(BaseModel):
    """견적서"""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '작성중'
        SENT = 'SENT', '발송'
        ACCEPTED = 'ACCEPTED', '수락'
        REJECTED = 'REJECTED', '거절'
        CONVERTED = 'CONVERTED', '주문전환'
        EXPIRED = 'EXPIRED', '만료'

    quote_number = models.CharField('견적번호', max_length=30, unique=True)
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
    converted_order = models.ForeignKey(
        Order, verbose_name='전환된 주문',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='source_quotation',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '견적서'
        verbose_name_plural = '견적서'
        ordering = ['-quote_date', '-pk']

    def __str__(self):
        return self.quote_number

    def update_total(self):
        items = self.quote_items.all()
        self.total_amount = sum(i.amount for i in items)
        self.tax_total = sum(i.tax_amount for i in items)
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
    unit_price = models.DecimalField(
        '단가', max_digits=12, decimal_places=0,
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

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'

    def save(self, *args, **kwargs):
        self.amount = self.quantity * self.unit_price
        self.tax_amount = int(self.amount * Decimal('0.1'))
        super().save(*args, **kwargs)


class Shipment(BaseModel):
    """배송 추적"""

    class Status(models.TextChoices):
        PREPARING = 'PREPARING', '준비중'
        SHIPPED = 'SHIPPED', '발송'
        IN_TRANSIT = 'IN_TRANSIT', '배송중'
        DELIVERED = 'DELIVERED', '배송완료'
        RETURNED = 'RETURNED', '반품'

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
        '배송번호', max_length=30, unique=True,
    )
    carrier = models.CharField(
        '택배사', max_length=20,
        choices=Carrier.choices, default=Carrier.CJ,
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


from apps.sales.commission import CommissionRate, CommissionRecord  # noqa
