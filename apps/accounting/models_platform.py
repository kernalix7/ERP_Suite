from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class PlatformFinancialConfig(BaseModel):
    """판매 채널(직판/마켓플레이스)별 재무·세무 설정.

    - 직판(DIRECT) / 네이버(NAVER) / 쿠팡(COUPANG) 등의 채널별로
      기본 결제수단, 정산주기, 수수료율, 세금계산서/현금영수증/카드매출 발행 주체,
      기본 과세구분 등을 관리한다.
    - Order.sales_channel, TaxInvoice.issuer_type 자동 매핑에 사용.
    """

    BUSINESS_KEY_FIELD = 'code'

    class IssuerType(models.TextChoices):
        SELF = 'SELF', '자사 발행'
        PLATFORM = 'PLATFORM', '플랫폼 발행'
        NONE = 'NONE', '발행 없음'

    class PaymentMethod(models.TextChoices):
        BANK_TRANSFER = 'BANK_TRANSFER', '계좌이체'
        CASH = 'CASH', '현금'
        CHECK = 'CHECK', '수표'
        CARD = 'CARD', '카드'
        PLATFORM_SETTLEMENT = 'PLATFORM_SETTLEMENT', '플랫폼 정산'

    class TaxType(models.TextChoices):
        TAXABLE = 'TAXABLE', '과세(10%)'
        ZERO_RATE = 'ZERO_RATE', '영세율(0%)'
        EXEMPT = 'EXEMPT', '면세'
        NON_TAXABLE = 'NON_TAXABLE', '과세대상 아님'

    code = models.CharField('플랫폼코드', max_length=32, unique=True)
    name = models.CharField('플랫폼명', max_length=64)

    payment_method_default = models.CharField(
        '기본 결제수단',
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.BANK_TRANSFER,
    )
    settlement_cycle_days = models.IntegerField(
        '정산주기(일)',
        default=0,
        help_text='판매 확정일로부터 정산 완료까지 걸리는 일수 (직판=0)',
    )
    commission_rate = models.DecimalField(
        '수수료율(%)',
        max_digits=5,
        decimal_places=2,
        default=0,
    )

    tax_invoice_issuer = models.CharField(
        '세금계산서 발행주체',
        max_length=20,
        choices=IssuerType.choices,
        default=IssuerType.SELF,
    )
    cash_receipt_issuer = models.CharField(
        '현금영수증 발행주체',
        max_length=20,
        choices=IssuerType.choices,
        default=IssuerType.SELF,
    )
    card_receipt_issuer = models.CharField(
        '카드매출전표 발행주체',
        max_length=20,
        choices=IssuerType.choices,
        default=IssuerType.SELF,
    )

    vat_classification_default = models.CharField(
        '기본 과세구분',
        max_length=20,
        choices=TaxType.choices,
        default=TaxType.TAXABLE,
    )
    allow_zero_rate = models.BooleanField('영세율 허용', default=False)
    is_enabled = models.BooleanField('사용', default=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '플랫폼 재무설정'
        verbose_name_plural = '플랫폼 재무설정'
        ordering = ['code']

    def __str__(self):
        return f'{self.name} ({self.code})'

    @classmethod
    def get_by_code(cls, code):
        """플랫폼 코드로 설정 조회 (없으면 None)."""
        if not code:
            return None
        return cls.objects.filter(code=code, is_active=True, is_enabled=True).first()
