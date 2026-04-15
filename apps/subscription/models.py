from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel
from apps.core.utils import generate_document_number


class SubscriptionPlan(BaseModel):
    """구독 플랜"""

    class BillingCycle(models.TextChoices):
        MONTHLY = 'MONTHLY', '월간'
        QUARTERLY = 'QUARTERLY', '분기'
        YEARLY = 'YEARLY', '연간'

    name = models.CharField('플랜명', max_length=100)
    code = models.CharField('플랜코드', max_length=20, unique=True)
    description = models.TextField('설명', blank=True)
    billing_cycle = models.CharField(
        '과금 주기', max_length=10,
        choices=BillingCycle.choices, default=BillingCycle.MONTHLY,
    )
    price = models.DecimalField('가격', max_digits=15, decimal_places=0, default=0)
    currency = models.CharField('통화', max_length=3, default='KRW')
    features = models.JSONField('기능 목록', default=list, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '구독 플랜'
        verbose_name_plural = '구독 플랜'
        ordering = ['price']

    def __str__(self):
        return f'{self.name} ({self.get_billing_cycle_display()})'


class Subscription(BaseModel):
    """구독"""
    BUSINESS_KEY_FIELD = 'subscription_number'

    class Status(models.TextChoices):
        TRIAL = 'TRIAL', '체험'
        ACTIVE = 'ACTIVE', '활성'
        PAUSED = 'PAUSED', '일시중지'
        CANCELLED = 'CANCELLED', '해지'
        EXPIRED = 'EXPIRED', '만료'

    subscription_number = models.CharField(
        '구독번호', max_length=20, unique=True, blank=True,
    )
    partner = models.ForeignKey(
        'sales.Partner', verbose_name='거래처',
        on_delete=models.PROTECT, related_name='subscriptions',
    )
    plan = models.ForeignKey(
        SubscriptionPlan, verbose_name='플랜',
        on_delete=models.PROTECT, related_name='subscriptions',
    )
    status = models.CharField(
        '상태', max_length=10,
        choices=Status.choices, default=Status.TRIAL,
    )
    start_date = models.DateField('시작일')
    end_date = models.DateField('종료일', null=True, blank=True)
    next_billing_date = models.DateField('다음 과금일', null=True, blank=True)
    auto_renew = models.BooleanField('자동갱신', default=True)
    cancel_reason = models.TextField('해지 사유', blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '구독'
        verbose_name_plural = '구독'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status'], name='idx_sub_status'),
            models.Index(fields=['next_billing_date'], name='idx_sub_billing'),
        ]

    def __str__(self):
        return f'{self.subscription_number} - {self.partner.name}'

    STATUS_TRANSITIONS = {
        'TRIAL': ['ACTIVE', 'CANCELLED'],
        'ACTIVE': ['PAUSED', 'CANCELLED'],
        'PAUSED': ['ACTIVE', 'CANCELLED'],
        'CANCELLED': [],
        'EXPIRED': [],
    }

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        if self.pk:
            old_status = Subscription.objects.filter(pk=self.pk).values_list('status', flat=True).first()
            if old_status and old_status != self.status:
                allowed = self.STATUS_TRANSITIONS.get(old_status, [])
                if self.status not in allowed:
                    old_label = dict(self.Status.choices).get(old_status, old_status)
                    new_label = dict(self.Status.choices).get(self.status, self.status)
                    raise ValidationError(
                        f'{old_label}에서 {new_label}(으)로 전이할 수 없습니다.'
                    )

    def save(self, *args, **kwargs):
        if not self.subscription_number:
            self.subscription_number = generate_document_number(
                Subscription, 'subscription_number', 'SUB',
            )
        super().save(*args, **kwargs)


class SubscriptionItem(BaseModel):
    """구독 항목"""
    subscription = models.ForeignKey(
        Subscription, verbose_name='구독',
        on_delete=models.PROTECT, related_name='items',
    )
    product = models.ForeignKey(
        'inventory.Product', verbose_name='제품',
        on_delete=models.PROTECT, related_name='subscription_items',
    )
    quantity = models.PositiveIntegerField('수량', default=1)
    unit_price = models.DecimalField('단가', max_digits=15, decimal_places=0, default=0)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '구독 항목'
        verbose_name_plural = '구독 항목'

    def __str__(self):
        return f'{self.subscription.subscription_number} - {self.product.name}'

    @property
    def amount(self):
        return self.quantity * self.unit_price


class BillingRecord(BaseModel):
    """과금 기록"""

    class Status(models.TextChoices):
        PENDING = 'PENDING', '대기'
        INVOICED = 'INVOICED', '청구됨'
        PAID = 'PAID', '결제완료'
        OVERDUE = 'OVERDUE', '연체'

    subscription = models.ForeignKey(
        Subscription, verbose_name='구독',
        on_delete=models.PROTECT, related_name='billing_records',
    )
    billing_date = models.DateField('과금일')
    amount = models.DecimalField('공급가액', max_digits=15, decimal_places=0, default=0)
    tax_amount = models.DecimalField('세액', max_digits=15, decimal_places=0, default=0)
    total = models.DecimalField('합계', max_digits=15, decimal_places=0, default=0)
    status = models.CharField(
        '상태', max_length=10,
        choices=Status.choices, default=Status.PENDING,
    )
    invoice = models.ForeignKey(
        'accounting.TaxInvoice', verbose_name='세금계산서',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='billing_records',
    )
    order = models.ForeignKey(
        'sales.Order', verbose_name='주문',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='billing_records',
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '과금 기록'
        verbose_name_plural = '과금 기록'
        ordering = ['-billing_date']

    def __str__(self):
        return f'{self.subscription.subscription_number} - {self.billing_date}'

    BILLING_STATUS_TRANSITIONS = {
        'PENDING': ['INVOICED', 'OVERDUE'],
        'INVOICED': ['PAID', 'OVERDUE'],
        'OVERDUE': ['PAID'],
        'PAID': [],
    }

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        if self.pk:
            old_status = BillingRecord.objects.filter(pk=self.pk).values_list('status', flat=True).first()
            if old_status and old_status != self.status:
                allowed = self.BILLING_STATUS_TRANSITIONS.get(old_status, [])
                if self.status not in allowed:
                    old_label = dict(self.Status.choices).get(old_status, old_status)
                    new_label = dict(self.Status.choices).get(self.status, self.status)
                    raise ValidationError(
                        f'{old_label}에서 {new_label}(으)로 전이할 수 없습니다.'
                    )

    def save(self, *args, **kwargs):
        from decimal import Decimal
        if self.amount:
            if not self.tax_amount:
                self.tax_amount = round(self.amount * Decimal('0.1'))
            self.total = self.amount + self.tax_amount
        super().save(*args, **kwargs)


class UsageRecord(BaseModel):
    """사용량 기록"""
    subscription = models.ForeignKey(
        Subscription, verbose_name='구독',
        on_delete=models.PROTECT, related_name='usage_records',
    )
    metric_name = models.CharField('항목명', max_length=100)
    quantity = models.DecimalField('수량', max_digits=15, decimal_places=2, default=0)
    recorded_date = models.DateField('기록일')
    billed = models.BooleanField('청구됨', default=False)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '사용량 기록'
        verbose_name_plural = '사용량 기록'
        ordering = ['-recorded_date']

    def __str__(self):
        return f'{self.subscription.subscription_number} - {self.metric_name} ({self.recorded_date})'
