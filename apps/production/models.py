from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel
from apps.inventory.models import Product


class BOM(BaseModel):
    product = models.ForeignKey(
        Product, verbose_name='완제품',
        on_delete=models.PROTECT,
        limit_choices_to={'product_type': 'FINISHED'},
        related_name='boms',
    )
    version = models.CharField('버전', max_length=20, default='1.0')
    is_default = models.BooleanField('기본BOM', default=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'BOM'
        verbose_name_plural = 'BOM'
        unique_together = ['product', 'version']

    def __str__(self):
        return f'{self.product.name} v{self.version}'

    @property
    def total_material_cost(self):
        return sum(item.material_cost for item in self.items.all())


class BOMItem(BaseModel):
    bom = models.ForeignKey(BOM, on_delete=models.CASCADE, related_name='items')
    material = models.ForeignKey(
        Product, verbose_name='자재',
        on_delete=models.PROTECT,
        limit_choices_to={'product_type__in': ['RAW', 'SEMI']},
    )
    quantity = models.DecimalField('소요량', max_digits=10, decimal_places=3)
    loss_rate = models.DecimalField('손실률(%)', max_digits=5, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'BOM 항목'
        verbose_name_plural = 'BOM 항목'

    def __str__(self):
        return f'{self.material.name} x {self.quantity}'

    @property
    def effective_quantity(self):
        return self.quantity * (1 + self.loss_rate / 100)

    @property
    def material_cost(self):
        return int(self.effective_quantity * self.material.cost_price)


class ProductionPlan(BaseModel):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '작성중'
        CONFIRMED = 'CONFIRMED', '확정'
        IN_PROGRESS = 'IN_PROGRESS', '진행중'
        COMPLETED = 'COMPLETED', '완료'
        CANCELLED = 'CANCELLED', '취소'

    plan_number = models.CharField('계획번호', max_length=30, unique=True)
    product = models.ForeignKey(
        Product, verbose_name='생산제품', on_delete=models.PROTECT,
    )
    bom = models.ForeignKey(
        BOM, verbose_name='BOM', on_delete=models.PROTECT,
    )
    planned_quantity = models.PositiveIntegerField('계획수량')
    planned_start = models.DateField('계획시작일')
    planned_end = models.DateField('계획종료일')
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.DRAFT,
    )
    estimated_cost = models.DecimalField('예상원가', max_digits=15, decimal_places=0, default=0)
    actual_cost = models.DecimalField('실제원가', max_digits=15, decimal_places=0, default=0)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '생산계획'
        verbose_name_plural = '생산계획'
        ordering = ['-planned_start']
        indexes = [
            models.Index(fields=['status'], name='idx_plan_status'),
            models.Index(fields=['planned_start'], name='idx_plan_start'),
        ]

    def __str__(self):
        return f'{self.plan_number} - {self.product.name}'

    @property
    def produced_quantity(self):
        return sum(
            r.good_quantity
            for wo in self.work_orders.all()
            for r in wo.records.all()
        )

    @property
    def progress_rate(self):
        if self.planned_quantity == 0:
            return 0
        return round(self.produced_quantity / self.planned_quantity * 100, 1)


class WorkOrder(BaseModel):
    class Status(models.TextChoices):
        PENDING = 'PENDING', '대기'
        IN_PROGRESS = 'IN_PROGRESS', '작업중'
        COMPLETED = 'COMPLETED', '완료'
        CANCELLED = 'CANCELLED', '취소'

    order_number = models.CharField('작업지시번호', max_length=30, unique=True)
    production_plan = models.ForeignKey(
        ProductionPlan, verbose_name='생산계획',
        on_delete=models.CASCADE, related_name='work_orders',
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='담당자',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    quantity = models.PositiveIntegerField('지시수량')
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.PENDING,
    )
    started_at = models.DateTimeField('작업시작', null=True, blank=True)
    completed_at = models.DateTimeField('작업완료', null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '작업지시'
        verbose_name_plural = '작업지시'
        ordering = ['-pk']
        indexes = [
            models.Index(fields=['status'], name='idx_wo_status'),
        ]

    def __str__(self):
        return self.order_number


class ProductionRecord(BaseModel):
    work_order = models.ForeignKey(
        WorkOrder, verbose_name='작업지시',
        on_delete=models.CASCADE, related_name='records',
    )
    good_quantity = models.PositiveIntegerField('양품수량')
    defect_quantity = models.PositiveIntegerField('불량수량', default=0)
    record_date = models.DateField('실적일')
    worker = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='작업자',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '생산실적'
        verbose_name_plural = '생산실적'
        ordering = ['-record_date']
        indexes = [
            models.Index(fields=['record_date'], name='idx_record_date'),
        ]

    def __str__(self):
        return f'{self.work_order.order_number} - {self.record_date}'

    @property
    def total_quantity(self):
        return self.good_quantity + self.defect_quantity
