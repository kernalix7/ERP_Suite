from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from simple_history.models import HistoricalRecords
from apps.core.models import BaseModel


class AssetCategory(BaseModel):
    """자산 분류"""
    name = models.CharField('분류명', max_length=100)
    code = models.CharField('분류코드', max_length=20, unique=True)
    useful_life_years = models.PositiveIntegerField('내용연수(년)', default=5)
    depreciation_method = models.CharField('감가상각법', max_length=10, choices=[
        ('STRAIGHT', '정액법'),
        ('DECLINING', '정률법'),
    ], default='STRAIGHT')
    history = HistoricalRecords()

    class Meta:
        verbose_name = '자산분류'
        verbose_name_plural = '자산분류'
        ordering = ['code']

    def __str__(self):
        return f'[{self.code}] {self.name}'


class Location(BaseModel):
    """자산 위치 마스터"""
    name = models.CharField('위치명', max_length=100)
    code = models.CharField('위치코드', max_length=20, unique=True)
    building = models.CharField('건물', max_length=100, blank=True)
    floor = models.CharField('층', max_length=20, blank=True)
    room = models.CharField('호실/구역', max_length=50, blank=True)
    parent = models.ForeignKey(
        'self', verbose_name='상위위치',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='children',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '자산위치'
        verbose_name_plural = '자산위치'
        ordering = ['code']

    def __str__(self):
        return f'[{self.code}] {self.name}'

    @property
    def full_path(self):
        parts = [self.name]
        if self.building:
            parts.insert(0, self.building)
        if self.floor:
            parts.append(f'{self.floor}층')
        if self.room:
            parts.append(self.room)
        return ' > '.join(parts)


class FixedAsset(BaseModel):
    """고정자산 대장"""
    BUSINESS_KEY_FIELD = 'asset_number'

    class AssetType(models.TextChoices):
        TANGIBLE = 'TANGIBLE', '유형자산'
        INTANGIBLE = 'INTANGIBLE', '무형자산'

    asset_number = models.CharField('자산번호', max_length=30, unique=True)
    name = models.CharField('자산명', max_length=200)
    category = models.ForeignKey(AssetCategory, on_delete=models.PROTECT, related_name='assets', verbose_name='분류')
    asset_type = models.CharField('자산유형', max_length=20, choices=AssetType.choices, default=AssetType.TANGIBLE)

    # 취득 정보
    acquisition_date = models.DateField('취득일')
    acquisition_cost = models.DecimalField('취득원가', max_digits=15, decimal_places=0)
    residual_value = models.DecimalField('잔존가치', max_digits=15, decimal_places=0, default=0)

    # 감가상각 설정
    useful_life_years = models.PositiveIntegerField('내용연수(년)')
    depreciation_method = models.CharField('감가상각법', max_length=10, choices=[
        ('STRAIGHT', '정액법'),
        ('DECLINING', '정률법'),
    ], default='STRAIGHT')

    # 현재 상태
    accumulated_depreciation = models.DecimalField('감가상각 누계액', max_digits=15, decimal_places=0, default=0)
    book_value = models.DecimalField('장부가액', max_digits=15, decimal_places=0, default=0)

    # 관리 정보
    department = models.ForeignKey('hr.Department', null=True, blank=True, on_delete=models.SET_NULL, verbose_name='사용부서')
    location = models.CharField('위치', max_length=200, blank=True)
    managed_location = models.ForeignKey(
        'Location', verbose_name='관리위치',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='assets',
    )
    responsible_person = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='managed_assets', verbose_name='관리자')

    # 입고 출처
    source_receipt_item = models.ForeignKey(
        'purchase.GoodsReceiptItem', verbose_name='입고출처',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='created_assets',
    )

    # 처분
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', '사용중'
        DISPOSED = 'DISPOSED', '처분'
        SCRAPPED = 'SCRAPPED', '폐기'

    status = models.CharField('상태', max_length=10, choices=Status.choices, default=Status.ACTIVE)
    disposal_date = models.DateField('처분일', null=True, blank=True)
    disposal_amount = models.DecimalField('처분금액', max_digits=15, decimal_places=0, default=0)
    disposal_reason = models.TextField('처분사유', blank=True)
    disposal_approval = models.ForeignKey(
        'approval.ApprovalRequest', verbose_name='처분결재',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='disposal_assets',
    )
    condition_assessment = models.TextField('상태평가', blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '고정자산'
        verbose_name_plural = '고정자산'
        ordering = ['-acquisition_date']
        indexes = [
            models.Index(fields=['status', 'acquisition_date'], name='idx_asset_status_acq'),
            models.Index(fields=['category', 'status'], name='idx_asset_cat_status'),
        ]

    def __str__(self):
        return f'[{self.asset_number}] {self.name}'

    def clean(self):
        super().clean()
        errors = {}
        if self.acquisition_cost is None or self.acquisition_cost <= 0:
            errors['acquisition_cost'] = '취득원가는 0보다 커야 합니다.'
        if self.residual_value is None or self.residual_value < 0:
            errors['residual_value'] = '잔존가치는 0 이상이어야 합니다.'
        if (self.acquisition_cost is not None and self.residual_value is not None
                and self.acquisition_cost > 0 and self.residual_value >= self.acquisition_cost):
            errors['residual_value'] = '잔존가치는 취득원가보다 작아야 합니다.'
        if self.useful_life_years is None or self.useful_life_years <= 0:
            errors['useful_life_years'] = '내용연수는 0보다 커야 합니다.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.category_id and (self.useful_life_years is None or self.useful_life_years == 0):
            self.useful_life_years = self.category.useful_life_years
        self.book_value = self.acquisition_cost - self.accumulated_depreciation
        super().save(*args, **kwargs)

    @property
    def monthly_depreciation(self):
        """월 감가상각비 계산"""
        if self.depreciation_method == 'STRAIGHT':
            depreciable = self.acquisition_cost - self.residual_value
            return int(depreciable / (self.useful_life_years * 12))
        else:  # DECLINING (정률법)
            if self.useful_life_years <= 0:
                return 0
            rate = 1 - (float(self.residual_value) / float(self.acquisition_cost)) ** (1.0 / self.useful_life_years) if self.acquisition_cost > 0 else 0
            return int(self.book_value * rate / 12)

    @property
    def is_fully_depreciated(self):
        return self.book_value <= self.residual_value


class DepreciationRecord(BaseModel):
    """감가상각 내역"""
    asset = models.ForeignKey(FixedAsset, on_delete=models.PROTECT, related_name='depreciation_records')
    year = models.PositiveIntegerField('년도')
    month = models.PositiveIntegerField('월')
    depreciation_amount = models.DecimalField('감가상각비', max_digits=15, decimal_places=0)
    accumulated_amount = models.DecimalField('누계액', max_digits=15, decimal_places=0)
    book_value_after = models.DecimalField('상각후 장부가', max_digits=15, decimal_places=0)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '감가상각 내역'
        verbose_name_plural = '감가상각 내역'
        ordering = ['-year', '-month']
        constraints = [
            models.UniqueConstraint(fields=['asset', 'year', 'month'], name='uq_depreciation_asset_period'),
        ]
        indexes = [
            models.Index(fields=['asset', 'year', 'month'], name='idx_deprec_asset_yr_mo'),
        ]

    def __str__(self):
        return f'{self.asset.asset_number} - {self.year}/{self.month}'


class AssetTransfer(BaseModel):
    """자산 이관 이력"""
    asset = models.ForeignKey(
        FixedAsset, verbose_name='자산',
        on_delete=models.PROTECT, related_name='transfers',
    )
    transfer_date = models.DateField('이관일')
    from_department = models.ForeignKey(
        'hr.Department', verbose_name='이전부서',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='asset_transfers_out',
    )
    to_department = models.ForeignKey(
        'hr.Department', verbose_name='이관부서',
        on_delete=models.PROTECT, related_name='asset_transfers_in',
    )
    from_person = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='이전관리자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='asset_transfers_from',
    )
    to_person = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='이관관리자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='asset_transfers_to',
    )
    from_location = models.CharField('이전위치', max_length=200, blank=True)
    to_location = models.CharField('이관위치', max_length=200, blank=True)
    from_managed_location = models.ForeignKey(
        'asset.Location', verbose_name='이전관리위치',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='transfers_out',
    )
    to_managed_location = models.ForeignKey(
        'asset.Location', verbose_name='이관관리위치',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='transfers_in',
    )
    reason = models.TextField('이관사유', blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '자산이관'
        verbose_name_plural = '자산이관'
        ordering = ['-transfer_date', '-pk']
        indexes = [
            models.Index(fields=['asset', 'transfer_date'], name='idx_transfer_asset_dt'),
        ]

    def __str__(self):
        return f'{self.asset.asset_number} {self.transfer_date} 이관'


class Certification(BaseModel):
    """제품 인증 관리"""

    class CertType(models.TextChoices):
        KC = 'KC', 'KC인증'
        CE = 'CE', 'CE인증'
        FCC = 'FCC', 'FCC인증'
        ISO = 'ISO', 'ISO인증'
        ROHS = 'ROHS', 'RoHS'
        OTHER = 'OTHER', '기타'

    product = models.ForeignKey(
        'inventory.Product', verbose_name='대상제품',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='certifications',
    )
    asset = models.ForeignKey(
        FixedAsset, verbose_name='연결자산',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='certifications',
    )
    cert_type = models.CharField('인증유형', max_length=10, choices=CertType.choices)
    cert_number = models.CharField('인증번호', max_length=100, blank=True)
    cert_name = models.CharField('인증명', max_length=200)
    issuer = models.CharField('발급기관', max_length=200, blank=True)
    issue_date = models.DateField('발급일')
    expiry_date = models.DateField('만료일', null=True, blank=True)
    cost = models.DecimalField('취득비용', max_digits=15, decimal_places=0, default=0)
    is_capitalized = models.BooleanField(
        '자본화', default=False,
        help_text='무형자산으로 자본화 처리',
    )
    attachment = models.FileField(
        '인증서',
        upload_to='certifications/',
        blank=True,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '인증'
        verbose_name_plural = '인증'
        ordering = ['-issue_date']

    def __str__(self):
        return f'{self.cert_name} ({self.get_cert_type_display()})'


class LeaseContract(BaseModel):
    """리스 계약"""
    BUSINESS_KEY_FIELD = 'contract_number'

    class LeaseType(models.TextChoices):
        OPERATING = 'OPERATING', '운용리스'
        FINANCE = 'FINANCE', '금융리스'

    asset = models.ForeignKey(
        FixedAsset, verbose_name='대상자산',
        on_delete=models.PROTECT, related_name='lease_contracts',
    )
    contract_number = models.CharField('계약번호', max_length=50, unique=True, blank=True)
    lessor = models.ForeignKey(
        'sales.Partner', verbose_name='임대인',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='lease_contracts',
    )
    lease_type = models.CharField('리스유형', max_length=20, choices=LeaseType.choices)
    start_date = models.DateField('계약시작일')
    end_date = models.DateField('계약종료일')
    monthly_payment = models.DecimalField('월 리스료', max_digits=15, decimal_places=0, default=0)
    deposit = models.DecimalField('보증금', max_digits=15, decimal_places=0, default=0)
    total_amount = models.DecimalField('총 계약금액', max_digits=15, decimal_places=0, default=0)
    auto_voucher = models.BooleanField('월 전표 자동생성', default=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '리스계약'
        verbose_name_plural = '리스계약'
        ordering = ['-start_date']

    def __str__(self):
        return f'[{self.contract_number}] {self.asset.name}'

    def save(self, *args, **kwargs):
        if not self.contract_number:
            from apps.core.utils import generate_document_number
            self.contract_number = generate_document_number(
                LeaseContract, 'contract_number', 'LS',
            )
        # total_amount 자동계산: monthly_payment x 개월수
        if self.monthly_payment and self.start_date and self.end_date:
            months = (self.end_date.year - self.start_date.year) * 12 + (self.end_date.month - self.start_date.month)
            if months < 1:
                months = 1
            self.total_amount = int(self.monthly_payment) * months
        super().save(*args, **kwargs)

    @property
    def remaining_months(self):
        """남은 계약 월수"""
        from datetime import date as date_cls
        today = date_cls.today()
        if self.end_date <= today:
            return 0
        return (self.end_date.year - today.year) * 12 + (self.end_date.month - today.month)


class AssetAudit(BaseModel):
    """자산 실사"""
    audit_date = models.DateField('실사일')
    auditor = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='실사자',
        on_delete=models.PROTECT, related_name='asset_audits',
    )
    department = models.ForeignKey(
        'hr.Department', verbose_name='대상부서',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '자산실사'
        verbose_name_plural = '자산실사'
        ordering = ['-audit_date']

    def __str__(self):
        dept_name = self.department.name if self.department else '전체'
        return f'실사 {self.audit_date} ({dept_name})'


class AssetAuditItem(BaseModel):
    """실사 항목"""

    class AuditStatus(models.TextChoices):
        FOUND = 'FOUND', '확인'
        MISSING = 'MISSING', '미발견'
        DAMAGED = 'DAMAGED', '파손'
        LOCATION_MISMATCH = 'LOCATION_MISMATCH', '위치불일치'

    class Condition(models.TextChoices):
        GOOD = 'GOOD', '양호'
        FAIR = 'FAIR', '보통'
        POOR = 'POOR', '불량'
        BROKEN = 'BROKEN', '파손'

    audit = models.ForeignKey(
        AssetAudit, verbose_name='실사',
        on_delete=models.PROTECT, related_name='items',
    )
    asset = models.ForeignKey(
        FixedAsset, verbose_name='자산',
        on_delete=models.PROTECT, related_name='audit_items',
    )
    status = models.CharField('실사상태', max_length=20, choices=AuditStatus.choices, default=AuditStatus.FOUND)
    actual_location = models.CharField('실제위치', max_length=200, blank=True)
    condition = models.CharField('상태', max_length=10, choices=Condition.choices, default=Condition.GOOD)
    remark = models.TextField('비고', blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '실사항목'
        verbose_name_plural = '실사항목'
        constraints = [
            models.UniqueConstraint(
                fields=['audit', 'asset'],
                name='uq_asset_audit_item',
            ),
        ]

    def __str__(self):
        return f'{self.audit} - {self.asset.asset_number}'


# ============================================================
# 자산 예약 (Asset Reservation)
# ============================================================

class ReservableAsset(BaseModel):
    """예약 가능 자산 (공용 자산 등록)"""

    class ResourceType(models.TextChoices):
        MEETING_ROOM = 'MEETING_ROOM', '회의실'
        VEHICLE = 'VEHICLE', '차량'
        EQUIPMENT = 'EQUIPMENT', '장비'
        FACILITY = 'FACILITY', '시설'
        OTHER = 'OTHER', '기타'

    fixed_asset = models.OneToOneField(
        FixedAsset, verbose_name='고정자산',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='reservable',
    )
    name = models.CharField('예약자산명', max_length=200)
    resource_type = models.CharField('자산유형', max_length=20, choices=ResourceType.choices, default=ResourceType.EQUIPMENT)
    description = models.TextField('설명', blank=True)
    location = models.ForeignKey(
        Location, verbose_name='위치',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='reservable_assets',
    )
    capacity = models.PositiveIntegerField('수용인원/수량', default=1)
    min_reserve_minutes = models.PositiveIntegerField('최소예약시간(분)', default=30)
    max_reserve_hours = models.PositiveIntegerField('최대예약시간(시)', default=8)
    advance_days = models.PositiveIntegerField('최대 사전예약일', default=30)
    requires_approval = models.BooleanField('승인필요', default=False)
    image = models.ImageField('이미지', upload_to='asset/reservable/', blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '예약가능자산'
        verbose_name_plural = '예약가능자산'
        ordering = ['resource_type', 'name']

    def __str__(self):
        return f'[{self.get_resource_type_display()}] {self.name}'


class ReservationRule(BaseModel):
    """예약 가능 시간대 규칙"""

    class DayOfWeek(models.IntegerChoices):
        MON = 0, '월요일'
        TUE = 1, '화요일'
        WED = 2, '수요일'
        THU = 3, '목요일'
        FRI = 4, '금요일'
        SAT = 5, '토요일'
        SUN = 6, '일요일'

    asset = models.ForeignKey(
        ReservableAsset, verbose_name='예약자산',
        on_delete=models.PROTECT, related_name='rules',
    )
    day_of_week = models.IntegerField('요일', choices=DayOfWeek.choices)
    open_time = models.TimeField('운영시작')
    close_time = models.TimeField('운영종료')
    is_closed = models.BooleanField('휴무', default=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '예약규칙'
        verbose_name_plural = '예약규칙'
        constraints = [
            models.UniqueConstraint(
                fields=['asset', 'day_of_week'],
                name='uq_reservation_rule_asset_day',
            ),
        ]
        ordering = ['asset', 'day_of_week']

    def __str__(self):
        return f'{self.asset.name} - {self.get_day_of_week_display()}'


class AssetReservation(BaseModel):
    """자산 예약"""

    class Status(models.TextChoices):
        PENDING = 'PENDING', '승인대기'
        APPROVED = 'APPROVED', '승인'
        REJECTED = 'REJECTED', '거부'
        CANCELLED = 'CANCELLED', '취소'
        COMPLETED = 'COMPLETED', '사용완료'

    reservation_number = models.CharField('예약번호', max_length=20, unique=True, blank=True)
    asset = models.ForeignKey(
        ReservableAsset, verbose_name='예약자산',
        on_delete=models.PROTECT, related_name='reservations',
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='예약자',
        on_delete=models.PROTECT, related_name='asset_reservations',
    )
    start_datetime = models.DateTimeField('예약시작일시')
    end_datetime = models.DateTimeField('예약종료일시')
    purpose = models.CharField('사용목적', max_length=500)
    attendee_count = models.PositiveIntegerField('참여인원', default=1)
    status = models.CharField('상태', max_length=20, choices=Status.choices, default=Status.PENDING)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='승인자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='approved_reservations',
    )
    approved_at = models.DateTimeField('승인일시', null=True, blank=True)
    rejection_reason = models.TextField('거부사유', blank=True)
    actual_start = models.DateTimeField('실제시작', null=True, blank=True)
    actual_end = models.DateTimeField('실제종료', null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '자산예약'
        verbose_name_plural = '자산예약'
        ordering = ['-start_datetime']

    def __str__(self):
        return f'[{self.reservation_number}] {self.asset.name} {self.start_datetime:%Y-%m-%d %H:%M}'

    def save(self, *args, **kwargs):
        if not self.reservation_number:
            from apps.core.utils import generate_document_number
            self.reservation_number = generate_document_number(
                AssetReservation, 'reservation_number', 'RSV',
            )
        super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.start_datetime and self.end_datetime:
            if self.end_datetime <= self.start_datetime:
                raise ValidationError({'end_datetime': '종료일시는 시작일시 이후여야 합니다.'})
            # 중복 예약 체크
            overlap_qs = AssetReservation.objects.filter(
                asset=self.asset,
                is_active=True,
                status__in=[self.Status.PENDING, self.Status.APPROVED],
                start_datetime__lt=self.end_datetime,
                end_datetime__gt=self.start_datetime,
            )
            if self.pk:
                overlap_qs = overlap_qs.exclude(pk=self.pk)
            if overlap_qs.exists():
                raise ValidationError('해당 시간대에 이미 예약이 존재합니다.')


class AssetMaintenance(BaseModel):
    """자산 유지보수 이력"""

    class MaintenanceType(models.TextChoices):
        PREVENTIVE = 'PREVENTIVE', '예방정비'
        CORRECTIVE = 'CORRECTIVE', '사후정비'
        INSPECTION = 'INSPECTION', '점검'
        CLEANING = 'CLEANING', '청소'

    class Status(models.TextChoices):
        SCHEDULED = 'SCHEDULED', '예정'
        IN_PROGRESS = 'IN_PROGRESS', '진행중'
        COMPLETED = 'COMPLETED', '완료'
        CANCELLED = 'CANCELLED', '취소'

    asset = models.ForeignKey(
        FixedAsset, verbose_name='자산',
        on_delete=models.PROTECT, related_name='maintenances',
    )
    maintenance_type = models.CharField('정비유형', max_length=20, choices=MaintenanceType.choices, default=MaintenanceType.PREVENTIVE)
    status = models.CharField('상태', max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    scheduled_date = models.DateField('예정일')
    completed_date = models.DateField('완료일', null=True, blank=True)
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='담당자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='asset_maintenances',
    )
    vendor = models.CharField('정비업체', max_length=200, blank=True)
    description = models.TextField('정비내용', blank=True)
    cost = models.DecimalField('정비비용', max_digits=15, decimal_places=0, default=0)
    next_maintenance_date = models.DateField('다음 정비 예정일', null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '자산유지보수'
        verbose_name_plural = '자산유지보수'
        ordering = ['-scheduled_date']

    def __str__(self):
        return f'{self.asset.name} - {self.get_maintenance_type_display()} {self.scheduled_date}'
