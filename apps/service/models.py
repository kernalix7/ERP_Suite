from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel
from apps.core.utils import generate_document_number
from apps.inventory.models import Product
from apps.sales.models import Customer


class ServiceRequest(BaseModel):
    class Status(models.TextChoices):
        RECEIVED = 'RECEIVED', '접수'
        INSPECTING = 'INSPECTING', '검수중'
        REPAIRING = 'REPAIRING', '수리중'
        COMPLETED = 'COMPLETED', '완료'
        RETURNED = 'RETURNED', '반송완료'
        CANCELLED = 'CANCELLED', '취소'

    class RequestType(models.TextChoices):
        WARRANTY = 'WARRANTY', '보증수리'
        PAID = 'PAID', '유상수리'
        EXCHANGE = 'EXCHANGE', '교환'
        REFUND = 'REFUND', '환불'

    request_number = models.CharField('AS번호', max_length=30, unique=True, blank=True)
    customer = models.ForeignKey(
        Customer, verbose_name='고객',
        on_delete=models.PROTECT, related_name='service_requests',
    )
    product = models.ForeignKey(
        Product, verbose_name='제품',
        on_delete=models.PROTECT,
    )
    serial_number = models.CharField('시리얼번호', max_length=100, blank=True)
    request_type = models.CharField(
        '요청유형', max_length=10,
        choices=RequestType.choices, default=RequestType.WARRANTY,
    )
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.RECEIVED,
    )
    symptom = models.TextField('증상/내용')
    received_date = models.DateField('접수일')
    completed_date = models.DateField('완료일', null=True, blank=True)
    is_warranty = models.BooleanField('보증기간내', default=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'AS 요청'
        verbose_name_plural = 'AS 요청'
        ordering = ['-request_number']
        indexes = [
            models.Index(fields=['status'], name='idx_service_status'),
            models.Index(
                fields=['received_date'], name='idx_service_date',
            ),
        ]

    def __str__(self):
        return f'{self.request_number} - {self.customer.name}'

    def save(self, *args, **kwargs):
        if not self.request_number:
            self.request_number = generate_document_number(ServiceRequest, 'request_number', 'AS')
        super().save(*args, **kwargs)


class RepairRecord(BaseModel):
    service_request = models.ForeignKey(
        ServiceRequest, verbose_name='AS 요청',
        on_delete=models.CASCADE, related_name='repairs',
    )
    repair_date = models.DateField('수리일')
    description = models.TextField('수리내용')
    parts_used = models.TextField('사용부품', blank=True)
    cost = models.DecimalField('수리비용', max_digits=12, decimal_places=0, default=0)
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='수리담당',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '수리이력'
        verbose_name_plural = '수리이력'
        ordering = ['-repair_date']

    def __str__(self):
        return f'{self.service_request.request_number} - {self.repair_date}'
