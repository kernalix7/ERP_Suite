from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel
from apps.core.utils import generate_document_number
from apps.inventory.models import Product


class BOM(BaseModel):
    product = models.ForeignKey(
        Product, verbose_name='완제품',
        on_delete=models.PROTECT,
        limit_choices_to={'product_type__in': ['FINISHED', 'SEMI']},
        related_name='boms',
    )
    version = models.CharField('버전', max_length=20, default='1.0')
    is_default = models.BooleanField('기본BOM', default=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'BOM'
        verbose_name_plural = 'BOM'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'version'],
                name='uq_bom_product_version',
            ),
        ]

    def __str__(self):
        return f'{self.product.name} v{self.version}'

    @property
    def total_material_cost(self):
        return sum(item.material_cost for item in self.items.all())

    def explode_multilevel(self, quantity=1, level=0, max_depth=10):
        """BOM 다단계 전개 -- 반제품 재귀 분해

        Args:
            quantity: 생산할 수량
            level: 현재 전개 깊이
            max_depth: 최대 전개 깊이 (무한 루프 방지)
        Returns:
            list of dict: [{material, quantity, level, is_leaf, parent_bom}]
        """
        if level >= max_depth:
            return []

        result = []
        for item in self.items.select_related('material').filter(is_active=True):
            effective_qty = item.effective_quantity * quantity
            material = item.material

            # 반제품인 경우 하위 BOM 전개
            sub_bom = None
            if material.product_type == 'SEMI':
                sub_bom = BOM.objects.filter(
                    product=material, is_active=True,
                ).first()

            if sub_bom:
                result.append({
                    'material': material,
                    'quantity': effective_qty,
                    'level': level,
                    'is_leaf': False,
                    'parent_bom': self,
                })
                result.extend(
                    sub_bom.explode_multilevel(effective_qty, level + 1, max_depth)
                )
            else:
                result.append({
                    'material': material,
                    'quantity': effective_qty,
                    'level': level,
                    'is_leaf': True,
                    'parent_bom': self,
                })
        return result

    def check_material_availability(self, quantity):
        """BOM 자재 가용성 체크 — 부족 자재 목록 반환

        Args:
            quantity: 생산할 완제품 수량
        Returns:
            list of dict: [{'material': Product, 'required': Decimal,
                           'available': Decimal, 'shortage': Decimal}]
        """
        shortages = []
        for item in self.items.select_related('material').all():
            required = item.effective_quantity * quantity
            available = item.material.available_stock
            if available < required:
                shortages.append({
                    'material': item.material,
                    'required': required,
                    'available': available,
                    'shortage': required - available,
                })
        return shortages


class BOMItem(BaseModel):
    bom = models.ForeignKey(BOM, verbose_name='BOM', on_delete=models.CASCADE, related_name='items')
    material = models.ForeignKey(
        Product, verbose_name='자재',
        on_delete=models.PROTECT,
        limit_choices_to={'product_type__in': ['RAW', 'SEMI']},
    )
    quantity = models.DecimalField('소요량', max_digits=10, decimal_places=3, validators=[MinValueValidator(0)])
    purchase_qty = models.DecimalField(
        '구매수량', max_digits=10, decimal_places=3,
        default=0, validators=[MinValueValidator(0)],
        help_text='1회 구매 단위 수량',
    )
    production_qty = models.PositiveIntegerField(
        '생산가능수량', default=0,
        help_text='구매수량으로 생산 가능한 완제품 수',
    )
    loss_rate = models.DecimalField('손실률(%)', max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'BOM 항목'
        verbose_name_plural = 'BOM 항목'
        ordering = ['pk']

    def __str__(self):
        return f'{self.material.name} x {self.quantity}'

    @property
    def effective_quantity(self):
        return self.quantity * (1 + self.loss_rate / 100)

    @property
    def material_cost(self):
        return round(self.effective_quantity * self.material.cost_price)


class ProductionPlan(BaseModel):
    BUSINESS_KEY_FIELD = 'plan_number'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '작성중'
        CONFIRMED = 'CONFIRMED', '확정'
        IN_PROGRESS = 'IN_PROGRESS', '진행중'
        COMPLETED = 'COMPLETED', '완료'
        CANCELLED = 'CANCELLED', '취소'

    plan_number = models.CharField('계획번호', max_length=30, unique=True, blank=True)
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
    estimated_cost = models.DecimalField('예상원가', max_digits=15, decimal_places=0, default=0, validators=[MinValueValidator(0)])
    actual_cost = models.DecimalField('실제원가', max_digits=15, decimal_places=0, default=0, validators=[MinValueValidator(0)])
    history = HistoricalRecords()

    class Meta:
        verbose_name = '생산계획'
        verbose_name_plural = '생산계획'
        ordering = ['-plan_number']
        indexes = [
            models.Index(fields=['status'], name='idx_plan_status'),
            models.Index(fields=['planned_start'], name='idx_plan_start'),
        ]

    def __str__(self):
        return f'{self.plan_number} - {self.product.name}'

    def save(self, *args, **kwargs):
        if not self.plan_number:
            self.plan_number = generate_document_number(ProductionPlan, 'plan_number', 'PP')
        super().save(*args, **kwargs)

    @property
    def produced_quantity(self):
        from django.db.models import Sum
        result = ProductionRecord.objects.filter(
            work_order__production_plan=self, is_active=True,
        ).aggregate(total=Sum('good_quantity'))
        return result['total'] or 0

    @property
    def progress_rate(self):
        if self.planned_quantity == 0:
            return 0
        return round(self.produced_quantity / self.planned_quantity * 100, 1)


class WorkOrder(BaseModel):
    BUSINESS_KEY_FIELD = 'order_number'

    class Status(models.TextChoices):
        PENDING = 'PENDING', '대기'
        IN_PROGRESS = 'IN_PROGRESS', '작업중'
        COMPLETED = 'COMPLETED', '완료'
        CANCELLED = 'CANCELLED', '취소'

    order_number = models.CharField('작업지시번호', max_length=30, unique=True, blank=True)
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
    work_center = models.ForeignKey(
        'WorkCenter', verbose_name='작업장',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='work_orders',
    )
    started_at = models.DateTimeField('작업시작', null=True, blank=True)
    completed_at = models.DateTimeField('작업완료', null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '작업지시'
        verbose_name_plural = '작업지시'
        ordering = ['-order_number']
        indexes = [
            models.Index(fields=['status'], name='idx_wo_status'),
        ]

    def __str__(self):
        return self.order_number

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = generate_document_number(WorkOrder, 'order_number', 'WO')
        super().save(*args, **kwargs)


class ProductionRecord(BaseModel):
    work_order = models.ForeignKey(
        WorkOrder, verbose_name='작업지시',
        on_delete=models.CASCADE, related_name='records',
    )
    warehouse = models.ForeignKey(
        'inventory.Warehouse', verbose_name='입고창고',
        null=True, blank=True,
        on_delete=models.PROTECT,
        help_text='완제품 입고 및 원자재 출고 대상 창고',
    )
    good_quantity = models.PositiveIntegerField('양품수량')
    defect_quantity = models.PositiveIntegerField('불량수량', default=0)
    unit_cost = models.DecimalField(
        '생산단가', max_digits=12, decimal_places=0, default=0,
        validators=[MinValueValidator(0)],
        help_text='생산 시점 제품 원가 (자동 기록)',
    )
    actual_material_cost = models.DecimalField(
        '실제자재원가', max_digits=15, decimal_places=0, default=0,
    )
    actual_labor_cost = models.DecimalField(
        '실제노무비', max_digits=15, decimal_places=0, default=0,
    )
    actual_overhead_cost = models.DecimalField(
        '실제간접비', max_digits=15, decimal_places=0, default=0,
    )
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


class StandardCost(BaseModel):
    """제품별 표준원가 설정"""
    product = models.ForeignKey(
        Product, verbose_name='제품',
        on_delete=models.PROTECT,
        related_name='standard_costs',
    )
    version = models.CharField('버전', max_length=20)
    effective_date = models.DateField('적용일')

    # 자재원가 (BOM 기반 자동 계산)
    material_cost = models.DecimalField(
        '표준자재원가', max_digits=15, decimal_places=0, default=0,
    )

    # 노무비
    direct_labor_hours = models.DecimalField(
        '직접노무시간', max_digits=10, decimal_places=2, default=0,
    )
    labor_rate_per_hour = models.DecimalField(
        '시간당 노무비', max_digits=15, decimal_places=0, default=0,
    )
    labor_cost = models.DecimalField(
        '표준노무비', max_digits=15, decimal_places=0, default=0,
    )

    # 제조간접비
    overhead_rate = models.DecimalField(
        '간접비 배부율(%)', max_digits=5, decimal_places=2, default=0,
        help_text='직접노무비 대비 간접비 비율',
    )
    overhead_cost = models.DecimalField(
        '표준간접비', max_digits=15, decimal_places=0, default=0,
    )

    # 합계
    total_standard_cost = models.DecimalField(
        '표준원가 합계', max_digits=15, decimal_places=0, default=0,
    )

    is_current = models.BooleanField('현행 여부', default=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '표준원가'
        verbose_name_plural = '표준원가'
        ordering = ['-effective_date']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'version'],
                name='uq_stdcost_product_version',
            ),
        ]

    def __str__(self):
        return f'{self.product.name} v{self.version}'

    def save(self, *args, **kwargs):
        # 노무비 자동 계산
        self.labor_cost = int(self.direct_labor_hours * self.labor_rate_per_hour)
        # 간접비 자동 계산 (직접노무비 기반)
        self.overhead_cost = int(self.labor_cost * self.overhead_rate / 100)
        # 합계
        self.total_standard_cost = self.material_cost + self.labor_cost + self.overhead_cost
        # 동일 제품의 기존 현행 표준원가 해제
        if self.is_current:
            StandardCost.objects.filter(
                product=self.product, is_current=True, is_active=True,
            ).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)

    def calculate_material_cost(self):
        """BOM 기반 자재원가 자동 계산"""
        bom = BOM.objects.filter(
            product=self.product, is_default=True, is_active=True,
        ).first()
        if bom:
            self.material_cost = int(bom.total_material_cost)
            return self.material_cost
        return 0


class QualityInspection(BaseModel):
    """품질검수 — 생산실적 또는 입고에 대한 검수 기록"""
    BUSINESS_KEY_FIELD = 'inspection_number'

    class InspectionType(models.TextChoices):
        PRODUCTION = 'PRODUCTION', '생산검수'
        INCOMING = 'INCOMING', '입고검수'

    class Result(models.TextChoices):
        PENDING = 'PENDING', '대기'
        PASS = 'PASS', '합격'
        FAIL = 'FAIL', '불합격'
        CONDITIONAL = 'CONDITIONAL', '조건부합격'

    inspection_number = models.CharField(
        '검수번호', max_length=30, unique=True, blank=True,
    )
    inspection_type = models.CharField(
        '검수유형', max_length=15,
        choices=InspectionType.choices,
        default=InspectionType.PRODUCTION,
    )
    production_record = models.ForeignKey(
        ProductionRecord, verbose_name='생산실적',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='inspections',
    )
    product = models.ForeignKey(
        Product, verbose_name='제품',
        on_delete=models.PROTECT,
    )
    inspected_quantity = models.PositiveIntegerField('검수수량')
    pass_quantity = models.PositiveIntegerField(
        '합격수량', default=0,
    )
    fail_quantity = models.PositiveIntegerField(
        '불합격수량', default=0,
    )
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='검수자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='inspections',
    )
    inspection_date = models.DateField('검수일')
    result = models.CharField(
        '결과', max_length=15,
        choices=Result.choices, default=Result.PENDING,
    )
    defect_description = models.TextField(
        '불량 내용', blank=True,
    )
    corrective_action = models.TextField(
        '시정 조치', blank=True,
    )
    conditional_notes = models.TextField(
        '조건부합격 사유', blank=True,
    )
    conditional_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='조건부합격 승인자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='conditional_approvals',
    )
    conditional_approved_at = models.DateTimeField(
        '조건부합격 승인일시', null=True, blank=True,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '품질검수'
        verbose_name_plural = '품질검수'
        ordering = ['-inspection_date', '-pk']

    def __str__(self):
        return (
            f'{self.inspection_number} '
            f'({self.get_result_display()})'
        )

    def save(self, *args, **kwargs):
        if not self.inspection_number:
            self.inspection_number = generate_document_number(
                QualityInspection,
                'inspection_number', 'QC',
            )
        # 합격/불합격 수량 합계 = 검수수량
        if self.pass_quantity + self.fail_quantity == 0:
            self.pass_quantity = self.inspected_quantity
        super().save(*args, **kwargs)

    @property
    def pass_rate(self):
        if self.inspected_quantity == 0:
            return 0
        return round(
            self.pass_quantity / self.inspected_quantity * 100,
            1,
        )


class WorkCenter(BaseModel):
    """작업장/생산라인"""
    name = models.CharField('작업장명', max_length=100)
    code = models.CharField('코드', max_length=20, unique=True)
    capacity_per_day = models.PositiveIntegerField('일일생산능력', default=100)
    efficiency_rate = models.DecimalField(
        '효율', max_digits=5, decimal_places=2, default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('2.00'))],
    )
    operating_hours = models.DecimalField(
        '가동시간', max_digits=4, decimal_places=1, default=Decimal('8.0'),
        validators=[MinValueValidator(Decimal('0.5')), MaxValueValidator(Decimal('24.0'))],
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '작업장'
        verbose_name_plural = '작업장'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class ProductionSchedule(BaseModel):
    """생산 스케줄"""
    work_order = models.ForeignKey(
        WorkOrder, verbose_name='작업지시',
        on_delete=models.PROTECT,
        related_name='schedules',
    )
    work_center = models.ForeignKey(
        WorkCenter, verbose_name='작업장',
        on_delete=models.PROTECT,
        related_name='schedules',
    )
    scheduled_start = models.DateTimeField('예정시작')
    scheduled_end = models.DateTimeField('예정종료')
    actual_start = models.DateTimeField('실제시작', null=True, blank=True)
    actual_end = models.DateTimeField('실제종료', null=True, blank=True)

    class Status(models.TextChoices):
        PLANNED = 'PLANNED', '계획'
        IN_PROGRESS = 'IN_PROGRESS', '진행중'
        COMPLETED = 'COMPLETED', '완료'
        DELAYED = 'DELAYED', '지연'

    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.PLANNED,
    )
    assigned_workers = models.PositiveIntegerField('배정인원', default=1)
    priority = models.PositiveIntegerField(
        '우선순위', default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text='1(최우선) ~ 10(최하위)',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '생산스케줄'
        verbose_name_plural = '생산스케줄'
        ordering = ['scheduled_start', 'priority']
        indexes = [
            models.Index(fields=['status'], name='idx_schedule_status'),
            models.Index(fields=['scheduled_start'], name='idx_schedule_start'),
        ]

    def __str__(self):
        return f'{self.work_order.order_number} @ {self.work_center.code}'

    @property
    def scheduled_hours(self):
        """예정 작업시간(시간)"""
        delta = self.scheduled_end - self.scheduled_start
        return round(delta.total_seconds() / 3600, 1)
