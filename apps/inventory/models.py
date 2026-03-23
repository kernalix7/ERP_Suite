from django.conf import settings
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel
from apps.core.utils import generate_document_number


class Category(BaseModel):
    name = models.CharField('카테고리명', max_length=100)
    parent = models.ForeignKey(
        'self', verbose_name='상위 카테고리',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='children',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '카테고리'
        verbose_name_plural = '카테고리'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(BaseModel):
    class ProductType(models.TextChoices):
        RAW = 'RAW', '원자재'
        SEMI = 'SEMI', '반제품'
        FINISHED = 'FINISHED', '완제품'

    class ValuationMethod(models.TextChoices):
        WEIGHTED_AVG = 'AVG', '이동평균법'
        FIFO = 'FIFO', '선입선출법'
        LIFO = 'LIFO', '후입선출법'

    code = models.CharField('제품코드', max_length=50, unique=True)
    name = models.CharField('제품명', max_length=200)
    product_type = models.CharField(
        '제품유형', max_length=10,
        choices=ProductType.choices, default=ProductType.FINISHED,
    )
    category = models.ForeignKey(
        Category, verbose_name='카테고리',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    unit = models.CharField('단위', max_length=20, default='EA')
    unit_price = models.DecimalField('판매단가', max_digits=12, decimal_places=0, default=0, validators=[MinValueValidator(0)])
    cost_price = models.DecimalField('원가', max_digits=12, decimal_places=0, default=0, validators=[MinValueValidator(0)])
    valuation_method = models.CharField(
        '재고평가법', max_length=5,
        choices=ValuationMethod.choices, default=ValuationMethod.WEIGHTED_AVG,
    )
    safety_stock = models.PositiveIntegerField('안전재고', default=0)
    current_stock = models.DecimalField('현재고', max_digits=15, decimal_places=3, default=0)
    reserved_stock = models.DecimalField('예약재고', max_digits=15, decimal_places=3, default=0)
    lead_time_days = models.PositiveIntegerField(
        '조달리드타임(일)', default=0,
        help_text='주문~입고 평균 소요일',
    )
    specification = models.TextField('규격/사양', blank=True)
    image = models.ImageField(
        '이미지', upload_to='products/',
        null=True, blank=True,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '제품'
        verbose_name_plural = '제품'
        ordering = ['code']
        indexes = [
            models.Index(fields=['product_type'], name='idx_product_type'),
            models.Index(fields=['product_type', 'is_active'], name='idx_product_type_active'),
            models.Index(fields=['current_stock'], name='idx_product_stock'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(current_stock__gte=0),
                name='stock_non_negative',
            ),
            models.CheckConstraint(
                check=models.Q(reserved_stock__gte=0),
                name='reserved_stock_non_negative',
            ),
        ]

    def __str__(self):
        return f'[{self.code}] {self.name}'

    @property
    def available_stock(self):
        """가용재고 = 현재고 - 예약재고 (0 이상)"""
        return max(self.current_stock - self.reserved_stock, 0)

    @property
    def is_below_safety_stock(self):
        return self.current_stock < self.safety_stock

    @property
    def shortage(self):
        if self.current_stock >= self.safety_stock:
            return 0
        return self.safety_stock - self.current_stock

    @property
    def profit_margin(self):
        if self.unit_price == 0:
            return 0
        return round((self.unit_price - self.cost_price) / self.unit_price * 100, 1)


class Warehouse(BaseModel):
    code = models.CharField('창고코드', max_length=20, unique=True)
    name = models.CharField('창고명', max_length=100)
    location = models.CharField('위치', max_length=200, blank=True)
    is_default = models.BooleanField('기본창고', default=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '창고'
        verbose_name_plural = '창고'
        ordering = ['code']

    def __str__(self):
        return self.name

    @classmethod
    def get_default(cls):
        """기본 창고 반환 (is_default=True 우선, 없으면 첫 번째 활성 창고)"""
        return (
            cls.objects.filter(is_active=True, is_default=True).first()
            or cls.objects.filter(is_active=True).first()
        )


class StockMovement(BaseModel):
    class MovementType(models.TextChoices):
        IN = 'IN', '입고'
        OUT = 'OUT', '출고'
        ADJ_PLUS = 'ADJ_PLUS', '재고조정(+)'
        ADJ_MINUS = 'ADJ_MINUS', '재고조정(-)'
        PROD_IN = 'PROD_IN', '생산입고'
        PROD_OUT = 'PROD_OUT', '생산출고'
        RETURN = 'RETURN', '반품'

    movement_number = models.CharField('전표번호', max_length=30, unique=True, blank=True)
    movement_type = models.CharField(
        '입출고유형', max_length=10,
        choices=MovementType.choices,
    )
    product = models.ForeignKey(
        Product, verbose_name='제품',
        on_delete=models.PROTECT, related_name='movements',
    )
    warehouse = models.ForeignKey(
        Warehouse, verbose_name='창고',
        on_delete=models.PROTECT, related_name='movements',
    )
    quantity = models.DecimalField('수량', max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal('0.001'))])
    unit_price = models.DecimalField('단가', max_digits=12, decimal_places=0, default=0, validators=[MinValueValidator(0)])
    movement_date = models.DateField('입출고일')
    reference = models.CharField('참조', max_length=200, blank=True)
    lot = models.ForeignKey(
        'StockLot', verbose_name='LOT',
        null=True, blank=True,
        on_delete=models.SET_NULL, related_name='movements',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '입출고'
        verbose_name_plural = '입출고'
        ordering = ['-movement_number']
        indexes = [
            models.Index(fields=['movement_type'], name='idx_movement_type'),
            models.Index(fields=['movement_date'], name='idx_movement_date'),
            models.Index(fields=['product', 'movement_type'], name='idx_mv_product_type'),
        ]

    def __str__(self):
        return f'{self.movement_number} ({self.get_movement_type_display()})'

    def save(self, *args, **kwargs):
        if not self.movement_number:
            self.movement_number = generate_document_number(StockMovement, 'movement_number', 'SM')
        super().save(*args, **kwargs)

    @property
    def total_amount(self):
        return self.quantity * self.unit_price


class StockTransfer(BaseModel):
    transfer_number = models.CharField('이동번호', max_length=30, unique=True, blank=True)
    from_warehouse = models.ForeignKey(
        Warehouse, verbose_name='출발창고',
        on_delete=models.PROTECT, related_name='transfers_out',
    )
    to_warehouse = models.ForeignKey(
        Warehouse, verbose_name='도착창고',
        on_delete=models.PROTECT, related_name='transfers_in',
    )
    product = models.ForeignKey(
        Product, verbose_name='제품', on_delete=models.PROTECT,
    )
    quantity = models.DecimalField('수량', max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal('0.001'))])
    transfer_date = models.DateField('이동일')
    history = HistoricalRecords()

    class Meta:
        verbose_name = '창고간이동'
        verbose_name_plural = '창고간이동'
        ordering = ['-transfer_date', '-pk']
        indexes = [
            models.Index(fields=['transfer_date'], name='idx_transfer_date'),
        ]

    def __str__(self):
        return f'{self.transfer_number}'

    def save(self, *args, **kwargs):
        if not self.transfer_number:
            self.transfer_number = generate_document_number(StockTransfer, 'transfer_number', 'ST')
        super().save(*args, **kwargs)


class StockCount(BaseModel):
    """재고실사 — 정기 실물 재고 점검"""
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '작성중'
        IN_PROGRESS = 'IN_PROGRESS', '실사중'
        COMPLETED = 'COMPLETED', '완료'
        ADJUSTED = 'ADJUSTED', '조정완료'

    count_number = models.CharField('실사번호', max_length=30, unique=True, blank=True)
    warehouse = models.ForeignKey(
        Warehouse, verbose_name='창고',
        on_delete=models.PROTECT, related_name='stock_counts',
    )
    count_date = models.DateField('실사일')
    status = models.CharField(
        '상태', max_length=15,
        choices=Status.choices, default=Status.DRAFT,
    )
    description = models.TextField('비고', blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '재고실사'
        verbose_name_plural = '재고실사'
        ordering = ['-count_date', '-pk']

    def __str__(self):
        return f'{self.count_number} ({self.get_status_display()})'

    def save(self, *args, **kwargs):
        if not self.count_number:
            self.count_number = generate_document_number(StockCount, 'count_number', 'SC')
        super().save(*args, **kwargs)


class StockCountItem(BaseModel):
    """재고실사 항목"""
    stock_count = models.ForeignKey(
        StockCount, verbose_name='재고실사',
        on_delete=models.CASCADE, related_name='items',
    )
    product = models.ForeignKey(
        Product, verbose_name='제품', on_delete=models.PROTECT,
    )
    system_quantity = models.DecimalField(
        '시스템재고', max_digits=15, decimal_places=3, default=0,
    )
    actual_quantity = models.DecimalField(
        '실사재고', max_digits=15, decimal_places=3, default=0,
    )
    difference = models.DecimalField(
        '차이', max_digits=15, decimal_places=3, default=0,
    )
    adjusted = models.BooleanField('조정완료', default=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '재고실사항목'
        verbose_name_plural = '재고실사항목'
        ordering = ['pk']

    def __str__(self):
        return f'{self.product.name}: 시스템 {self.system_quantity} / 실사 {self.actual_quantity}'

    def save(self, *args, **kwargs):
        self.difference = self.actual_quantity - self.system_quantity
        super().save(*args, **kwargs)


class WarehouseStock(BaseModel):
    """창고별 재고 — Product.current_stock의 창고 차원 분해"""
    warehouse = models.ForeignKey(
        Warehouse, verbose_name='창고',
        on_delete=models.PROTECT, related_name='stocks',
    )
    product = models.ForeignKey(
        Product, verbose_name='제품',
        on_delete=models.PROTECT, related_name='warehouse_stocks',
    )
    quantity = models.DecimalField(
        '재고수량', max_digits=15, decimal_places=3, default=0,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '창고별 재고'
        verbose_name_plural = '창고별 재고'
        ordering = ['warehouse', 'product']
        constraints = [
            models.UniqueConstraint(
                fields=['warehouse', 'product'],
                name='uq_warehouse_product',
            ),
            models.CheckConstraint(
                check=models.Q(quantity__gte=0),
                name='warehouse_stock_non_negative',
            ),
        ]

    def __str__(self):
        return f'{self.warehouse.name} - {self.product.name}: {self.quantity}'


class StockLot(BaseModel):
    """입고 배치(LOT) 단위 재고 추적"""
    lot_number = models.CharField('LOT번호', max_length=50, unique=True)
    product = models.ForeignKey(
        Product, verbose_name='제품',
        on_delete=models.PROTECT, related_name='lots',
    )
    warehouse = models.ForeignKey(
        Warehouse, verbose_name='창고',
        on_delete=models.PROTECT, related_name='lots',
    )
    initial_quantity = models.DecimalField('초기입고량', max_digits=15, decimal_places=3)
    remaining_quantity = models.DecimalField('잔여수량', max_digits=15, decimal_places=3)
    unit_cost = models.DecimalField('입고단가', max_digits=15, decimal_places=0)
    received_date = models.DateField('입고일')
    expiry_date = models.DateField('유효기한', null=True, blank=True)
    stock_movement = models.ForeignKey(
        StockMovement, verbose_name='입고전표',
        null=True, blank=True,
        on_delete=models.SET_NULL, related_name='lots',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '재고 LOT'
        verbose_name_plural = '재고 LOT'
        ordering = ['received_date', 'pk']
        constraints = [
            models.CheckConstraint(
                check=models.Q(remaining_quantity__gte=0),
                name='lot_remaining_non_negative',
            ),
        ]

    def __str__(self):
        return f'{self.lot_number} ({self.product.name} / 잔여: {self.remaining_quantity})'
