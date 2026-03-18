from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class Category(BaseModel):
    name = models.CharField('카테고리명', max_length=100)
    parent = models.ForeignKey(
        'self', verbose_name='상위 카테고리',
        null=True, blank=True, on_delete=models.CASCADE,
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
    unit_price = models.DecimalField('판매단가', max_digits=12, decimal_places=0, default=0)
    cost_price = models.DecimalField('원가', max_digits=12, decimal_places=0, default=0)
    safety_stock = models.PositiveIntegerField('안전재고', default=0)
    current_stock = models.IntegerField('현재고', default=0)
    specification = models.TextField('규격/사양', blank=True)
    image = models.ImageField('이미지', upload_to='products/', null=True, blank=True)
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
        ]

    def __str__(self):
        return f'[{self.code}] {self.name}'

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
    history = HistoricalRecords()

    class Meta:
        verbose_name = '창고'
        verbose_name_plural = '창고'
        ordering = ['code']

    def __str__(self):
        return self.name


class StockMovement(BaseModel):
    class MovementType(models.TextChoices):
        IN = 'IN', '입고'
        OUT = 'OUT', '출고'
        ADJ_PLUS = 'ADJ_PLUS', '재고조정(+)'
        ADJ_MINUS = 'ADJ_MINUS', '재고조정(-)'
        PROD_IN = 'PROD_IN', '생산입고'
        PROD_OUT = 'PROD_OUT', '생산출고'
        RETURN = 'RETURN', '반품'

    movement_number = models.CharField('전표번호', max_length=30, unique=True)
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
    quantity = models.PositiveIntegerField('수량')
    unit_price = models.DecimalField('단가', max_digits=12, decimal_places=0, default=0)
    movement_date = models.DateField('입출고일')
    reference = models.CharField('참조', max_length=100, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '입출고'
        verbose_name_plural = '입출고'
        ordering = ['-movement_date', '-pk']
        indexes = [
            models.Index(fields=['movement_type'], name='idx_movement_type'),
            models.Index(fields=['movement_date'], name='idx_movement_date'),
            models.Index(fields=['product', 'movement_type'], name='idx_mv_product_type'),
        ]

    def __str__(self):
        return f'{self.movement_number} ({self.get_movement_type_display()})'

    @property
    def total_amount(self):
        return self.quantity * self.unit_price


class StockTransfer(BaseModel):
    transfer_number = models.CharField('이동번호', max_length=30, unique=True)
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
    quantity = models.PositiveIntegerField('수량')
    transfer_date = models.DateField('이동일')
    history = HistoricalRecords()

    class Meta:
        verbose_name = '창고간이동'
        verbose_name_plural = '창고간이동'
        ordering = ['-transfer_date', '-pk']

    def __str__(self):
        return f'{self.transfer_number}'
