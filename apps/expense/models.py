from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel
from apps.core.utils import generate_document_number


class ExpensePolicy(BaseModel):
    """경비 정책"""
    name = models.CharField('정책명', max_length=100)
    category = models.CharField('적용 카테고리', max_length=50, blank=True)
    max_amount = models.DecimalField(
        '건당 한도', max_digits=15, decimal_places=0,
        default=0, validators=[MinValueValidator(0)],
    )
    requires_receipt = models.BooleanField('영수증 필수', default=True)
    requires_approval = models.BooleanField('결재 필수', default=True)
    daily_limit = models.DecimalField(
        '일일 한도', max_digits=15, decimal_places=0,
        default=0, validators=[MinValueValidator(0)],
    )
    monthly_limit = models.DecimalField(
        '월간 한도', max_digits=15, decimal_places=0,
        default=0, validators=[MinValueValidator(0)],
    )
    applicable_roles = models.JSONField('적용 직급', default=list, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '경비 정책'
        verbose_name_plural = '경비 정책'
        ordering = ['name']

    def __str__(self):
        return self.name


class ExpenseCategory(BaseModel):
    """경비 카테고리"""
    name = models.CharField('카테고리명', max_length=100)
    code = models.CharField('코드', max_length=20, unique=True)
    account_code = models.ForeignKey(
        'accounting.AccountCode', verbose_name='계정과목',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='expense_categories',
    )
    parent = models.ForeignKey(
        'self', verbose_name='상위 카테고리',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='children',
    )
    policy = models.ForeignKey(
        ExpensePolicy, verbose_name='적용 정책',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='categories',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '경비 카테고리'
        verbose_name_plural = '경비 카테고리'
        ordering = ['code']

    def __str__(self):
        return f'[{self.code}] {self.name}'


class ExpenseClaim(BaseModel):
    """경비 청구"""
    BUSINESS_KEY_FIELD = 'claim_number'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '작성중'
        SUBMITTED = 'SUBMITTED', '제출'
        APPROVED = 'APPROVED', '승인'
        REJECTED = 'REJECTED', '반려'
        PAID = 'PAID', '지급완료'

    claim_number = models.CharField('청구번호', max_length=20, unique=True, blank=True)
    employee = models.ForeignKey(
        'hr.EmployeeProfile', verbose_name='신청자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='expense_claims',
    )
    title = models.CharField('제목', max_length=200)
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.DRAFT,
    )
    submitted_date = models.DateField('제출일', null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='승인자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='approved_expense_claims',
    )
    approved_date = models.DateField('승인일', null=True, blank=True)
    total_amount = models.DecimalField(
        '총금액', max_digits=15, decimal_places=0,
        default=0, validators=[MinValueValidator(0)],
    )
    paid_date = models.DateField('지급일', null=True, blank=True)
    rejection_reason = models.TextField('반려 사유', blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '경비 청구'
        verbose_name_plural = '경비 청구'
        ordering = ['-pk']
        indexes = [
            models.Index(fields=['status'], name='idx_expense_claim_status'),
        ]

    def __str__(self):
        return f'{self.claim_number} - {self.title}'

    def save(self, *args, **kwargs):
        if not self.claim_number:
            self.claim_number = generate_document_number(
                ExpenseClaim, 'claim_number', 'EXP',
            )
        super().save(*args, **kwargs)

    def recalculate_total(self):
        from django.db.models import Sum
        total = self.items.filter(is_active=True).aggregate(
            total=Sum('amount'),
        )['total'] or 0
        self.total_amount = total
        self.save(update_fields=['total_amount', 'updated_at'])


class ExpenseItem(BaseModel):
    """경비 항목"""
    claim = models.ForeignKey(
        ExpenseClaim, verbose_name='경비 청구',
        on_delete=models.PROTECT, related_name='items',
    )
    category = models.ForeignKey(
        ExpenseCategory, verbose_name='카테고리',
        on_delete=models.PROTECT, related_name='items',
    )
    date = models.DateField('사용일')
    description = models.CharField('설명', max_length=200)
    amount = models.DecimalField(
        '금액', max_digits=15, decimal_places=0,
        validators=[MinValueValidator(0)],
    )
    tax_amount = models.DecimalField(
        '부가세', max_digits=15, decimal_places=0,
        default=0, validators=[MinValueValidator(0)],
    )
    receipt_file = models.FileField('영수증', upload_to='expenses/receipts/%Y/%m/', blank=True)
    is_corporate_card = models.BooleanField('법인카드 사용', default=False)
    card_transaction_id = models.CharField('카드거래ID', max_length=50, blank=True)
    merchant_name = models.CharField('가맹점명', max_length=100, blank=True)
    policy_violation_note = models.TextField('정책 위반 사항', blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '경비 항목'
        verbose_name_plural = '경비 항목'
        ordering = ['date']

    def __str__(self):
        return f'{self.description} ({self.amount:,}원)'


class CorporateCard(BaseModel):
    """법인카드"""
    card_number_last4 = models.CharField('카드번호 끝4자리', max_length=4)
    employee = models.ForeignKey(
        'hr.EmployeeProfile', verbose_name='사용자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='expense_corporate_cards',
    )
    card_type = models.CharField('카드유형', max_length=50, blank=True)
    monthly_limit = models.DecimalField(
        '월간 한도', max_digits=15, decimal_places=0,
        default=0, validators=[MinValueValidator(0)],
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '법인카드'
        verbose_name_plural = '법인카드'
        ordering = ['-pk']

    def __str__(self):
        name = self.employee.user.get_full_name() if self.employee else '미지정'
        return f'{name} (*{self.card_number_last4})'


class CardTransaction(BaseModel):
    """카드 거래내역"""
    card = models.ForeignKey(
        CorporateCard, verbose_name='법인카드',
        on_delete=models.PROTECT, related_name='expense_transactions',
    )
    transaction_date = models.DateField('거래일')
    merchant = models.CharField('가맹점', max_length=100)
    amount = models.DecimalField(
        '거래금액', max_digits=15, decimal_places=0,
        validators=[MinValueValidator(0)],
    )
    category = models.ForeignKey(
        ExpenseCategory, verbose_name='카테고리',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='card_transactions',
    )
    matched_expense = models.ForeignKey(
        ExpenseItem, verbose_name='매칭 경비',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='card_transactions',
    )
    is_personal = models.BooleanField('개인사용', default=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '카드 거래'
        verbose_name_plural = '카드 거래'
        ordering = ['-transaction_date', '-pk']

    def __str__(self):
        return f'{self.merchant} {self.amount:,}원 ({self.transaction_date})'
