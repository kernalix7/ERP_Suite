from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class WarehouseZone(BaseModel):
    """창고 구역"""

    class ZoneType(models.TextChoices):
        RECEIVING = 'RECEIVING', '입고구역'
        STORAGE = 'STORAGE', '보관구역'
        PICKING = 'PICKING', '피킹구역'
        PACKING = 'PACKING', '포장구역'
        SHIPPING = 'SHIPPING', '출하구역'
        QUARANTINE = 'QUARANTINE', '격리구역'

    warehouse = models.ForeignKey(
        'inventory.Warehouse',
        verbose_name='창고',
        on_delete=models.PROTECT,
        related_name='zones',
    )
    name = models.CharField('구역명', max_length=100)
    code = models.CharField('구역코드', max_length=20, unique=True)
    zone_type = models.CharField(
        '구역유형', max_length=20,
        choices=ZoneType.choices, default=ZoneType.STORAGE,
    )
    description = models.TextField('설명', blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '창고구역'
        verbose_name_plural = verbose_name
        ordering = ['warehouse', 'code']
        indexes = [
            models.Index(fields=['warehouse', 'zone_type'], name='idx_zone_warehouse_type'),
        ]

    def __str__(self):
        return f'[{self.code}] {self.name}'


class BinLocation(BaseModel):
    """보관 위치 (빈)"""

    zone = models.ForeignKey(
        WarehouseZone,
        verbose_name='구역',
        on_delete=models.PROTECT,
        related_name='bins',
    )
    code = models.CharField('위치코드', max_length=30, unique=True)
    row = models.CharField('행', max_length=10, blank=True)
    column = models.CharField('열', max_length=10, blank=True)
    level = models.CharField('단', max_length=10, blank=True)
    max_weight = models.DecimalField(
        '최대적재량(kg)', max_digits=10, decimal_places=2,
        null=True, blank=True,
    )
    is_occupied = models.BooleanField('사용중', default=False)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '보관위치'
        verbose_name_plural = verbose_name
        ordering = ['zone', 'code']

    def __str__(self):
        return f'{self.zone.code}-{self.code}'


class PickOrder(BaseModel):
    """피킹 오더"""

    BUSINESS_KEY_FIELD = 'pick_number'

    class Status(models.TextChoices):
        PENDING = 'PENDING', '대기'
        PICKING = 'PICKING', '피킹중'
        PACKED = 'PACKED', '포장완료'
        SHIPPED = 'SHIPPED', '출하완료'
        CANCELLED = 'CANCELLED', '취소'

    class Priority(models.TextChoices):
        LOW = 'LOW', '낮음'
        NORMAL = 'NORMAL', '보통'
        HIGH = 'HIGH', '높음'
        URGENT = 'URGENT', '긴급'

    pick_number = models.CharField('피킹번호', max_length=20, unique=True, blank=True)
    order = models.ForeignKey(
        'sales.Order',
        verbose_name='주문',
        on_delete=models.PROTECT,
        related_name='pick_orders',
        null=True, blank=True,
    )
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.PENDING,
    )
    priority = models.CharField(
        '우선순위', max_length=10,
        choices=Priority.choices, default=Priority.NORMAL,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='담당자',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_pick_orders',
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '피킹오더'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at'], name='idx_pick_status_date'),
            models.Index(fields=['status', 'priority'], name='idx_pick_status_priority'),
        ]

    def __str__(self):
        return self.pick_number

    def save(self, *args, **kwargs):
        if not self.pick_number:
            from apps.core.utils import generate_document_number
            self.pick_number = generate_document_number(
                PickOrder, 'pick_number', 'PK',
            )
        super().save(*args, **kwargs)


class PickOrderItem(BaseModel):
    """피킹 오더 항목"""

    pick_order = models.ForeignKey(
        PickOrder,
        verbose_name='피킹오더',
        on_delete=models.PROTECT,
        related_name='items',
    )
    product = models.ForeignKey(
        'inventory.Product',
        verbose_name='품목',
        on_delete=models.PROTECT,
        related_name='pick_order_items',
    )
    bin_location = models.ForeignKey(
        BinLocation,
        verbose_name='보관위치',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pick_items',
    )
    quantity = models.DecimalField('요청수량', max_digits=15, decimal_places=3)
    picked_qty = models.DecimalField(
        '피킹수량', max_digits=15, decimal_places=3, default=0,
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '피킹항목'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.pick_order} - {self.product}'


class PutAwayTask(BaseModel):
    """입고적치 작업"""

    class Status(models.TextChoices):
        PENDING = 'PENDING', '대기'
        IN_PROGRESS = 'IN_PROGRESS', '진행중'
        COMPLETED = 'COMPLETED', '완료'
        CANCELLED = 'CANCELLED', '취소'

    goods_receipt = models.ForeignKey(
        'purchase.GoodsReceipt',
        verbose_name='입고',
        on_delete=models.PROTECT,
        related_name='putaway_tasks',
        null=True, blank=True,
    )
    product = models.ForeignKey(
        'inventory.Product',
        verbose_name='품목',
        on_delete=models.PROTECT,
        related_name='putaway_tasks',
    )
    quantity = models.DecimalField('수량', max_digits=15, decimal_places=3)
    suggested_bin = models.ForeignKey(
        BinLocation,
        verbose_name='추천위치',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='suggested_putaways',
    )
    actual_bin = models.ForeignKey(
        BinLocation,
        verbose_name='실제위치',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='actual_putaways',
    )
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.PENDING,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='담당자',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_putaway_tasks',
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '입고적치작업'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at'], name='idx_putaway_status_date'),
        ]

    def __str__(self):
        return f'적치-{self.pk}: {self.product}'


class WavePlan(BaseModel):
    """웨이브 계획"""

    BUSINESS_KEY_FIELD = 'wave_number'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '초안'
        RELEASED = 'RELEASED', '확정'
        IN_PROGRESS = 'IN_PROGRESS', '진행중'
        COMPLETED = 'COMPLETED', '완료'
        CANCELLED = 'CANCELLED', '취소'

    wave_number = models.CharField('웨이브번호', max_length=20, unique=True, blank=True)
    name = models.CharField('웨이브명', max_length=100)
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.DRAFT,
    )
    pick_orders = models.ManyToManyField(
        PickOrder,
        verbose_name='피킹오더',
        blank=True,
        related_name='wave_plans',
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '웨이브계획'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at'], name='idx_wave_status_date'),
        ]

    def __str__(self):
        return f'[{self.wave_number}] {self.name}'

    def save(self, *args, **kwargs):
        if not self.wave_number:
            from apps.core.utils import generate_document_number
            self.wave_number = generate_document_number(
                WavePlan, 'wave_number', 'WV',
            )
        super().save(*args, **kwargs)
