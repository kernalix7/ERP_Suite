from datetime import timedelta

from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.fields import EncryptedCharField
from apps.core.models import BaseModel
from apps.core.storage import hashed_upload_path
from apps.inventory.models import Product

DEFAULT_WARRANTY_DAYS = 365
DEFAULT_VERIFIED_WARRANTY_DAYS = 730


class ProductRegistration(BaseModel):
    BUSINESS_KEY_FIELD = 'serial_number'

    serial_number = models.CharField('시리얼번호', max_length=100, unique=True)
    product = models.ForeignKey(
        Product, verbose_name='제품', on_delete=models.PROTECT,
    )
    customer = models.ForeignKey(
        'sales.Customer', verbose_name='고객',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='product_registrations',
    )
    customer_name = models.CharField('고객명', max_length=100)
    phone = EncryptedCharField('연락처', max_length=500)
    email = EncryptedCharField('이메일', max_length=500, blank=True)
    purchase_date = models.DateField('구매일')
    purchase_channel = models.CharField(
        '구매처', max_length=100, blank=True,
        help_text='스마트스토어, 공식홈페이지, 오프라인 등',
    )
    warranty_start = models.DateField('보증시작일')
    warranty_end = models.DateField('보증만료일')
    warranty_days = models.PositiveIntegerField(
        'AS기간(일)', default=DEFAULT_WARRANTY_DAYS,
        help_text='정품등록 시 기본 AS기간. 생성 후 수동 변경 가능.',
    )
    verified_warranty_days = models.PositiveIntegerField(
        '인증 후 AS기간(일)', default=DEFAULT_VERIFIED_WARRANTY_DAYS,
        help_text='인증 완료 시 적용되는 AS기간. 생성 후 수동 변경 가능.',
    )
    photo = models.ImageField('인증사진', upload_to=hashed_upload_path('warranty'), null=True, blank=True)
    custom_info = models.BooleanField('고객 정보와 다름', default=False)
    is_verified = models.BooleanField('인증완료', default=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '정품등록'
        verbose_name_plural = '정품등록'
        ordering = ['-pk']

    def __str__(self):
        return f'{self.serial_number} - {self.customer_name}'

    def save(self, *args, **kwargs):
        # warranty_end 자동 계산: 인증 여부에 따라 다른 기간 적용
        start = self.warranty_start or self.purchase_date
        if start:
            if self.is_verified:
                self.warranty_end = start + timedelta(days=self.verified_warranty_days)
            else:
                self.warranty_end = start + timedelta(days=self.warranty_days)

        super().save(*args, **kwargs)

    @property
    def is_warranty_valid(self):
        from datetime import date
        return self.warranty_end >= date.today()
