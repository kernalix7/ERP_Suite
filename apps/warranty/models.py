from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel
from apps.inventory.models import Product


class ProductRegistration(BaseModel):
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
    phone = models.CharField('연락처', max_length=20)
    email = models.EmailField('이메일', blank=True)
    purchase_date = models.DateField('구매일')
    purchase_channel = models.CharField(
        '구매처', max_length=100, blank=True,
        help_text='스마트스토어, 공식홈페이지, 오프라인 등',
    )
    warranty_start = models.DateField('보증시작일')
    warranty_end = models.DateField('보증만료일')
    photo = models.ImageField('인증사진', upload_to='warranty/', null=True, blank=True)
    is_verified = models.BooleanField('인증완료', default=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '정품등록'
        verbose_name_plural = '정품등록'
        ordering = ['-pk']

    def __str__(self):
        return f'{self.serial_number} - {self.customer_name}'

    @property
    def is_warranty_valid(self):
        from datetime import date
        return self.warranty_end >= date.today()
