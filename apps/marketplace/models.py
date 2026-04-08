from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.fields import EncryptedCharField, EncryptedTextField
from apps.core.models import BaseModel


class MarketplaceConfig(BaseModel):
    shop_name = models.CharField('스토어명', max_length=100)
    client_id = EncryptedCharField('Client ID', max_length=500)
    client_secret = EncryptedCharField('Client Secret', max_length=500)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '스토어 설정'
        verbose_name_plural = '스토어 설정'

    def __str__(self):
        return self.shop_name


class MarketplaceOrder(BaseModel):
    BUSINESS_KEY_FIELD = 'store_order_id'

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
    buyer_phone = EncryptedCharField('연락처', max_length=500, blank=True)
    receiver_name = models.CharField('수취인', max_length=100)
    receiver_phone = EncryptedCharField('수취인연락처', max_length=500, blank=True)
    receiver_address = EncryptedTextField('배송주소', blank=True)
    platform_order_id = models.CharField(
        '플랫폼주문번호', max_length=100, blank=True, default='', db_index=True,
    )
    platform_product_order_id = models.CharField(
        '플랫폼상품주문번호', max_length=100, blank=True, default='',
    )
    delivery_company = models.CharField('택배사', max_length=50, blank=True, default='')
    tracking_number = models.CharField('운송장번호', max_length=100, blank=True, default='')
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.NEW,
    )
    ordered_at = models.DateTimeField('주문일시')
    erp_order = models.ForeignKey(
        'sales.Order', verbose_name='연결된 ERP 주문',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='marketplace_orders',
    )
    erp_quotation = models.ForeignKey(
        'sales.Quotation', verbose_name='연결된 견적서',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='marketplace_quotations',
    )
    synced_at = models.DateTimeField('동기화일시', null=True, blank=True)

    class ImportStatus(models.TextChoices):
        PENDING = 'PENDING', '대기'
        CUSTOMER_DONE = 'CUSTOMER_DONE', '고객등록완료'
        QUOTATION_DONE = 'QUOTATION_DONE', '견적생성완료'
        ORDER_DONE = 'ORDER_DONE', '주문전환완료'
        SKIPPED = 'SKIPPED', '건너뜀'
        ERROR = 'ERROR', '오류'

    import_session = models.ForeignKey(
        'ImportSession', verbose_name='가져오기 세션',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='orders',
    )
    import_status = models.CharField(
        '가져오기상태', max_length=20,
        choices=ImportStatus.choices, default=ImportStatus.PENDING,
    )
    import_error = models.TextField('가져오기오류', blank=True)

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


class ImportTemplate(BaseModel):
    class StoreType(models.TextChoices):
        NAVER = 'NAVER', '네이버 스마트스토어'
        COUPANG = 'COUPANG', '쿠팡'
        OTHER = 'OTHER', '기타'

    name = models.CharField('템플릿명', max_length=100)
    store_type = models.CharField(
        '스토어유형', max_length=20,
        choices=StoreType.choices, default=StoreType.OTHER,
    )
    default_period = models.IntegerField('기본 조회기간(일)', default=7)
    auto_confirm = models.BooleanField('자동 견적생성', default=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '가져오기 템플릿'
        verbose_name_plural = '가져오기 템플릿'
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.name} ({self.get_store_type_display()})'


class ProductMapping(BaseModel):
    template = models.ForeignKey(
        ImportTemplate, on_delete=models.CASCADE,
        related_name='mappings', verbose_name='템플릿',
        null=True, blank=True,
    )
    store_product_name = models.CharField('스토어상품명', max_length=200)
    store_option_name = models.CharField('옵션명', max_length=200, blank=True, default='')
    product = models.ForeignKey(
        'inventory.Product', on_delete=models.CASCADE, verbose_name='ERP제품',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '상품매핑'
        verbose_name_plural = '상품매핑'
        unique_together = ('template', 'store_product_name', 'store_option_name')

    def __str__(self):
        if self.store_option_name:
            return f'{self.store_product_name} [{self.store_option_name}] → {self.product}'
        return f'{self.store_product_name} → {self.product}'


class ImportSession(BaseModel):
    """가져오기 세션 — 6단계 위자드 진행 상태 추적"""

    class Stage(models.TextChoices):
        FETCH = 'FETCH', '데이터 수집'
        PREVIEW = 'PREVIEW', '미리보기'
        CUSTOMER = 'CUSTOMER', '고객등록'
        QUOTATION = 'QUOTATION', '견적생성'
        ORDER = 'ORDER', '주문전환'
        DONE = 'DONE', '완료'

    stage = models.CharField(
        '현재단계', max_length=20,
        choices=Stage.choices, default=Stage.FETCH,
    )
    source_type = models.CharField(
        '소스유형', max_length=10, default='API',
        help_text='API 또는 EXCEL',
    )
    platform = models.CharField('플랫폼', max_length=20, blank=True)
    total_count = models.IntegerField('전체건수', default=0)
    selected_count = models.IntegerField('선택건수', default=0)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '가져오기 세션'
        verbose_name_plural = '가져오기 세션'
        ordering = ['-created_at']

    def __str__(self):
        return f'Import #{self.pk} ({self.get_stage_display()})'


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


class SettlementReconciliation(BaseModel):
    """정산 대사 — 스토어 정산액과 실제 입금 비교"""

    class Status(models.TextChoices):
        PENDING = 'PENDING', '대기'
        MATCHED = 'MATCHED', '일치'
        MISMATCHED = 'MISMATCHED', '불일치'
        MANUAL = 'MANUAL', '수동처리'

    store_module = models.CharField('스토어', max_length=50)
    settlement_date = models.DateField('정산일')
    expected_amount = models.DecimalField(
        '예상 정산액', max_digits=15, decimal_places=0, default=0,
    )
    actual_amount = models.DecimalField(
        '실제 입금액', max_digits=15, decimal_places=0, default=0,
    )
    difference = models.DecimalField(
        '차이', max_digits=15, decimal_places=0, default=0,
    )
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.PENDING,
    )
    partner = models.ForeignKey(
        'sales.Partner', verbose_name='거래처',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='settlement_reconciliations',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '정산 대사'
        verbose_name_plural = '정산 대사'
        ordering = ['-settlement_date', '-pk']
        indexes = [
            models.Index(fields=['status'], name='idx_recon_status'),
            models.Index(fields=['settlement_date'], name='idx_recon_date'),
        ]

    def __str__(self):
        return f'{self.store_module} {self.settlement_date} ({self.get_status_display()})'
