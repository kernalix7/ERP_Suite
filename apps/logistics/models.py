from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel
from apps.core.utils import generate_document_number


class Driver(BaseModel):
    """배송 기사"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name='사용자',
        on_delete=models.PROTECT, related_name='driver_profile',
    )
    license_number = models.CharField('면허번호', max_length=50)
    license_type = models.CharField(
        '면허종류', max_length=20,
        choices=[
            ('TYPE1', '1종 대형'), ('TYPE1_NORMAL', '1종 보통'),
            ('TYPE2', '2종 보통'), ('TYPE2_SMALL', '2종 소형'),
        ],
        default='TYPE1_NORMAL',
    )
    license_expiry = models.DateField('면허 만료일')
    phone = models.CharField('연락처', max_length=20)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '배송 기사'
        verbose_name_plural = '배송 기사'
        ordering = ['user__username']

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.license_number})'


class Vehicle(BaseModel):
    """차량"""

    class VehicleType(models.TextChoices):
        TRUCK = 'TRUCK', '트럭'
        VAN = 'VAN', '밴'
        MOTORCYCLE = 'MOTORCYCLE', '오토바이'

    class VehicleStatus(models.TextChoices):
        AVAILABLE = 'AVAILABLE', '사용 가능'
        IN_USE = 'IN_USE', '사용 중'
        MAINTENANCE = 'MAINTENANCE', '정비 중'

    name = models.CharField('차량명', max_length=100)
    plate_number = models.CharField('차량번호', max_length=20, unique=True)
    vehicle_type = models.CharField(
        '차종', max_length=15,
        choices=VehicleType.choices, default=VehicleType.TRUCK,
    )
    capacity_kg = models.DecimalField(
        '적재량(kg)', max_digits=10, decimal_places=2, default=0,
    )
    capacity_cbm = models.DecimalField(
        '적재용적(CBM)', max_digits=10, decimal_places=2, default=0,
    )
    status = models.CharField(
        '상태', max_length=15,
        choices=VehicleStatus.choices, default=VehicleStatus.AVAILABLE,
    )
    driver = models.ForeignKey(
        Driver, verbose_name='기본 기사',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='vehicles',
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '차량'
        verbose_name_plural = '차량'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.plate_number})'


class DeliveryZone(BaseModel):
    """배송 권역"""
    name = models.CharField('권역명', max_length=100)
    region = models.CharField('지역', max_length=100)
    base_cost = models.DecimalField(
        '기본 배송비', max_digits=15, decimal_places=0, default=0,
    )
    cost_per_kg = models.DecimalField(
        'kg당 비용', max_digits=15, decimal_places=0, default=0,
    )
    cost_per_km = models.DecimalField(
        'km당 비용', max_digits=15, decimal_places=0, default=0,
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '배송 권역'
        verbose_name_plural = '배송 권역'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.region})'


class DeliveryRoute(BaseModel):
    """배송 경로"""
    BUSINESS_KEY_FIELD = 'route_number'

    class RouteStatus(models.TextChoices):
        PLANNED = 'PLANNED', '계획'
        IN_PROGRESS = 'IN_PROGRESS', '진행 중'
        COMPLETED = 'COMPLETED', '완료'

    route_number = models.CharField('경로번호', max_length=20, unique=True, blank=True)
    name = models.CharField('경로명', max_length=200)
    date = models.DateField('배송일')
    vehicle = models.ForeignKey(
        Vehicle, verbose_name='차량',
        on_delete=models.PROTECT, related_name='routes',
    )
    driver = models.ForeignKey(
        Driver, verbose_name='기사',
        on_delete=models.PROTECT, related_name='routes',
    )
    status = models.CharField(
        '상태', max_length=15,
        choices=RouteStatus.choices, default=RouteStatus.PLANNED,
    )
    total_distance_km = models.DecimalField(
        '총 거리(km)', max_digits=10, decimal_places=2, default=0,
    )
    total_cost = models.DecimalField(
        '총 비용', max_digits=15, decimal_places=0, default=0,
    )
    departure_time = models.DateTimeField('출발 시간', null=True, blank=True)
    return_time = models.DateTimeField('귀환 시간', null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '배송 경로'
        verbose_name_plural = '배송 경로'
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date'], name='idx_route_date'),
            models.Index(fields=['status'], name='idx_route_status'),
        ]

    def __str__(self):
        return f'{self.route_number} - {self.name}'

    STATUS_TRANSITIONS = {
        'PLANNED': ['IN_PROGRESS'],
        'IN_PROGRESS': ['COMPLETED'],
        'COMPLETED': [],
    }

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        if self.pk:
            old_status = DeliveryRoute.objects.filter(pk=self.pk).values_list('status', flat=True).first()
            if old_status and old_status != self.status:
                allowed = self.STATUS_TRANSITIONS.get(old_status, [])
                if self.status not in allowed:
                    old_label = dict(self.RouteStatus.choices).get(old_status, old_status)
                    new_label = dict(self.RouteStatus.choices).get(self.status, self.status)
                    raise ValidationError(
                        f'{old_label}에서 {new_label}(으)로 전이할 수 없습니다.'
                    )

    def save(self, *args, **kwargs):
        if not self.route_number:
            self.route_number = generate_document_number(
                DeliveryRoute, 'route_number', 'RT',
            )
        super().save(*args, **kwargs)


class RouteStop(BaseModel):
    """경유지"""

    class StopStatus(models.TextChoices):
        PENDING = 'PENDING', '대기'
        ARRIVED = 'ARRIVED', '도착'
        COMPLETED = 'COMPLETED', '완료'
        SKIPPED = 'SKIPPED', '건너뜀'

    route = models.ForeignKey(
        DeliveryRoute, verbose_name='경로',
        on_delete=models.PROTECT, related_name='stops',
    )
    sequence = models.PositiveIntegerField('순서', default=1)
    order = models.ForeignKey(
        'sales.Order', verbose_name='관련 주문',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='route_stops',
    )
    partner = models.ForeignKey(
        'sales.Partner', verbose_name='거래처',
        on_delete=models.PROTECT, related_name='route_stops',
    )
    address = models.TextField('주소')
    estimated_arrival = models.DateTimeField('예상 도착', null=True, blank=True)
    actual_arrival = models.DateTimeField('실제 도착', null=True, blank=True)
    status = models.CharField(
        '상태', max_length=10,
        choices=StopStatus.choices, default=StopStatus.PENDING,
    )

    STOP_STATUS_TRANSITIONS = {
        'PENDING': ['ARRIVED', 'SKIPPED'],
        'ARRIVED': ['COMPLETED'],
        'COMPLETED': [],
        'SKIPPED': [],
    }

    history = HistoricalRecords()

    class Meta:
        verbose_name = '경유지'
        verbose_name_plural = '경유지'
        ordering = ['route', 'sequence']
        unique_together = ['route', 'sequence']

    def __str__(self):
        return f'{self.route.route_number} #{self.sequence} - {self.partner.name}'

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        if self.pk:
            old_status = RouteStop.objects.filter(pk=self.pk).values_list('status', flat=True).first()
            if old_status and old_status != self.status:
                allowed = self.STOP_STATUS_TRANSITIONS.get(old_status, [])
                if self.status not in allowed:
                    old_label = dict(self.StopStatus.choices).get(old_status, old_status)
                    new_label = dict(self.StopStatus.choices).get(self.status, self.status)
                    raise ValidationError(
                        f'{old_label}에서 {new_label}(으)로 전이할 수 없습니다.'
                    )


class FreightCost(BaseModel):
    """운송 비용"""

    class CostType(models.TextChoices):
        FUEL = 'FUEL', '유류비'
        TOLL = 'TOLL', '통행료'
        LABOR = 'LABOR', '인건비'
        OTHER = 'OTHER', '기타'

    route = models.ForeignKey(
        DeliveryRoute, verbose_name='경로',
        on_delete=models.PROTECT, related_name='freight_costs',
    )
    cost_type = models.CharField(
        '비용 유형', max_length=10,
        choices=CostType.choices,
    )
    amount = models.DecimalField('금액', max_digits=15, decimal_places=0)
    description = models.CharField('설명', max_length=200, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '운송 비용'
        verbose_name_plural = '운송 비용'

    def __str__(self):
        return f'{self.route.route_number} - {self.get_cost_type_display()} {self.amount}'
