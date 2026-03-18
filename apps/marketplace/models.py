from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class MarketplaceConfig(BaseModel):
    shop_name = models.CharField('스토어명', max_length=100)
    client_id = models.CharField('Client ID', max_length=200)
    client_secret = models.CharField('Client Secret', max_length=200)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '스토어 설정'
        verbose_name_plural = '스토어 설정'

    def __str__(self):
        return self.shop_name


class MarketplaceOrder(BaseModel):
    class Status(models.TextChoices):
        NEW = 'NEW', '신규주문'
        CONFIRMED = 'CONFIRMED', '확인'
        SHIPPED = 'SHIPPED', '발송완료'
        DELIVERED = 'DELIVERED', '배송완료'
        CANCELLED = 'CANCELLED', '취소'
        RETURNED = 'RETURNED', '반품'

    store_order_id = models.CharField('스토어주문번호', max_length=50, unique=True)
    product_name = models.CharField('상품명', max_length=200)
    option_name = models.CharField('옵션', max_length=200, blank=True)
    quantity = models.PositiveIntegerField('수량')
    price = models.DecimalField('결제금액', max_digits=15, decimal_places=0)
    buyer_name = models.CharField('주문자', max_length=100)
    buyer_phone = models.CharField('연락처', max_length=20, blank=True)
    receiver_name = models.CharField('수취인', max_length=100)
    receiver_phone = models.CharField('수취인연락처', max_length=20, blank=True)
    receiver_address = models.TextField('배송주소', blank=True)
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.NEW,
    )
    ordered_at = models.DateTimeField('주문일시')
    erp_order = models.ForeignKey(
        'sales.Order', verbose_name='연결된 ERP 주문',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    synced_at = models.DateTimeField('동기화일시', null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '스토어주문'
        verbose_name_plural = '스토어주문'
        ordering = ['-ordered_at']
        indexes = [
            models.Index(fields=['status'], name='idx_mktorder_status'),
            models.Index(fields=['ordered_at'], name='idx_mktorder_date'),
        ]

    def __str__(self):
        return f'{self.store_order_id} - {self.product_name}'


class SyncLog(BaseModel):
    class Direction(models.TextChoices):
        PULL = 'PULL', '수신'
        PUSH = 'PUSH', '발신'

    direction = models.CharField(
        '방향', max_length=10,
        choices=Direction.choices,
    )
    started_at = models.DateTimeField('시작일시')
    completed_at = models.DateTimeField('완료일시', null=True, blank=True)
    total_count = models.IntegerField('전체건수', default=0)
    success_count = models.IntegerField('성공건수', default=0)
    error_count = models.IntegerField('오류건수', default=0)
    error_message = models.TextField('오류내용', blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '동기화이력'
        verbose_name_plural = '동기화이력'
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.get_direction_display()} - {self.started_at}'
