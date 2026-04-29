"""판매채널·결제수단 DB 마스터 — Order의 enum 하드코딩 대체.

Order.sales_channel / payment_method 는 CharField(코드 저장)로 유지하되,
폼/관리화면에서 사용 가능한 선택지는 이 모델로 사용자가 추가/비활성화 가능.

기존 Order.SalesChannel / PaymentMethod TextChoices 는 시드 기본값으로
보존되며, 신규 채널(11번가/위메프/옥션 등) 추가 시 admin에서 즉시 활성화.
"""
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class SalesChannel(BaseModel):
    """판매채널 마스터 (DIRECT/NAVER/COUPANG/11ST/WEMAKEPRICE/AUCTION 등 자유 추가)."""

    BUSINESS_KEY_FIELD = 'code'

    code = models.CharField('채널 코드', max_length=32, unique=True)
    name = models.CharField('채널명', max_length=100)
    is_marketplace = models.BooleanField(
        '마켓플레이스 여부', default=False,
        help_text='True 시 PlatformFinancialConfig 와 연동 가능',
    )
    sort_order = models.PositiveIntegerField('정렬순서', default=100)
    is_enabled = models.BooleanField('사용', default=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '판매채널'
        verbose_name_plural = '판매채널'
        ordering = ['sort_order', 'code']

    def __str__(self):
        return f'[{self.code}] {self.name}'

    @classmethod
    def active_choices(cls, include_legacy=True):
        """폼에 사용할 (code, name) 목록.

        DB 활성 채널 + (옵션) Order.SalesChannel TextChoices 의 누락 항목 병합.
        """
        rows = list(cls.objects.filter(
            is_enabled=True, is_active=True,
        ).values_list('code', 'name'))
        seen = {c for c, _ in rows}
        if include_legacy:
            from apps.sales.models import Order
            for code, label in Order.SalesChannel.choices:
                if code not in seen:
                    rows.append((code, label))
        return rows


class PaymentMethod(BaseModel):
    """결제수단 마스터 (CARD/BANK_TRANSFER/CASH/NAVER_PAY/KAKAO_PAY/...)."""

    BUSINESS_KEY_FIELD = 'code'

    code = models.CharField('결제수단 코드', max_length=32, unique=True)
    name = models.CharField('결제수단명', max_length=100)
    is_card = models.BooleanField(
        '카드 결제 여부', default=False,
        help_text='True 시 PG가 국세청에 자동 신고 (카드매출전표)',
    )
    is_cash_equivalent = models.BooleanField(
        '현금성 여부', default=False,
        help_text='현금영수증 발행 가능 여부 판단용',
    )
    sort_order = models.PositiveIntegerField('정렬순서', default=100)
    is_enabled = models.BooleanField('사용', default=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '결제수단'
        verbose_name_plural = '결제수단'
        ordering = ['sort_order', 'code']

    def __str__(self):
        return f'[{self.code}] {self.name}'

    @classmethod
    def active_choices(cls, include_legacy=True):
        rows = list(cls.objects.filter(
            is_enabled=True, is_active=True,
        ).values_list('code', 'name'))
        seen = {c for c, _ in rows}
        if include_legacy:
            from apps.sales.models import Order
            for code, label in Order.PaymentMethod.choices:
                if code not in seen:
                    rows.append((code, label))
        return rows
