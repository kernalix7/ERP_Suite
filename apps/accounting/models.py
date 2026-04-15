from datetime import date

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel
from apps.core.utils import generate_document_number


class Currency(BaseModel):
    """통화"""
    code = models.CharField('통화코드', max_length=3, unique=True)  # USD, EUR, JPY, CNY
    name = models.CharField('통화명', max_length=50)
    symbol = models.CharField('기호', max_length=5)  # $, €, ¥, ¥
    decimal_places = models.PositiveSmallIntegerField('소수자리', default=2)
    is_base = models.BooleanField('기준통화', default=False)  # KRW
    history = HistoricalRecords()

    class Meta:
        verbose_name = '통화'
        verbose_name_plural = '통화'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} ({self.name})'

    def save(self, *args, **kwargs):
        if self.is_base:
            # 다른 기준통화 해제
            Currency.objects.filter(
                is_base=True,
            ).exclude(pk=self.pk).update(is_base=False)
        super().save(*args, **kwargs)


class ExchangeRate(BaseModel):
    """환율"""
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name='rates', verbose_name='통화')
    rate_date = models.DateField('적용일')
    rate = models.DecimalField('환율', max_digits=15, decimal_places=4)  # 1 외화 = X KRW
    history = HistoricalRecords()

    class Meta:
        verbose_name = '환율'
        verbose_name_plural = '환율'
        ordering = ['-rate_date']
        constraints = [
            models.UniqueConstraint(fields=['currency', 'rate_date'], name='uq_exchange_rate_date'),
        ]

    def __str__(self):
        return f'{self.currency.code} {self.rate_date} = {self.rate}'


class TaxRate(BaseModel):
    name = models.CharField('세율명', max_length=50)
    code = models.CharField('세율코드', max_length=20, unique=True)
    rate = models.DecimalField('세율(%)', max_digits=5, decimal_places=2)
    is_default = models.BooleanField('기본세율', default=False)
    effective_from = models.DateField('시행일')
    effective_to = models.DateField('종료일', null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '세율'
        verbose_name_plural = '세율'
        ordering = ['code']

    def __str__(self):
        return f'{self.name} ({self.rate}%)'


class TaxInvoice(BaseModel):
    BUSINESS_KEY_FIELD = 'invoice_number'

    class InvoiceType(models.TextChoices):
        SALES = 'SALES', '매출'
        PURCHASE = 'PURCHASE', '매입'

    class ElectronicStatus(models.TextChoices):
        NONE = 'NONE', '미발행'
        DRAFT = 'DRAFT', '작성중'
        ISSUED = 'ISSUED', '발행완료'
        SENT = 'SENT', '국세청 전송'
        ACCEPTED = 'ACCEPTED', '국세청 승인'
        REJECTED = 'REJECTED', '국세청 반려'
        CANCELLED = 'CANCELLED', '취소'

    invoice_number = models.CharField('세금계산서번호', max_length=50, unique=True, blank=True)
    invoice_type = models.CharField('유형', max_length=10, choices=InvoiceType.choices)
    partner = models.ForeignKey(
        'sales.Partner', verbose_name='거래처',
        on_delete=models.PROTECT, related_name='tax_invoices',
    )
    order = models.ForeignKey(
        'sales.Order', verbose_name='주문',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    issue_date = models.DateField('발행일')
    supply_amount = models.DecimalField('공급가액', max_digits=15, decimal_places=0, validators=[MinValueValidator(0)])
    tax_amount = models.DecimalField('부가세', max_digits=15, decimal_places=0, validators=[MinValueValidator(0)])
    total_amount = models.DecimalField('합계', max_digits=15, decimal_places=0, validators=[MinValueValidator(0)])
    description = models.TextField('적요', blank=True)

    # 전자세금계산서 필드
    electronic_status = models.CharField(
        '전자발행상태', max_length=15,
        choices=ElectronicStatus.choices, default=ElectronicStatus.NONE,
    )
    nts_confirmation_number = models.CharField('국세청 승인번호', max_length=50, blank=True)
    issue_id = models.CharField(
        '발행ID', max_length=100, blank=True,
        help_text='전자세금계산서 발행 고유ID',
    )
    sent_at = models.DateTimeField('전송일시', null=True, blank=True)
    nts_response = models.JSONField('국세청 응답', default=dict, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '세금계산서'
        verbose_name_plural = '세금계산서'
        ordering = ['-invoice_number']
        indexes = [
            models.Index(fields=['issue_date'], name='idx_invoice_date'),
            models.Index(fields=['invoice_type'], name='idx_invoice_type'),
            models.Index(fields=['electronic_status'], name='idx_invoice_estatus'),
        ]

    def __str__(self):
        return f'{self.invoice_number} ({self.get_invoice_type_display()})'

    def clean(self):
        super().clean()
        if (self.supply_amount is not None
                and self.tax_amount is not None
                and self.total_amount is not None):
            expected = self.supply_amount + self.tax_amount
            if self.total_amount != expected:
                from django.core.exceptions import ValidationError
                raise ValidationError(
                    f'합계({self.total_amount})가 공급가액({self.supply_amount}) + '
                    f'부가세({self.tax_amount}) = {expected}과 일치하지 않습니다.'
                )

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = generate_document_number(TaxInvoice, 'invoice_number', 'TI')
        super().save(*args, **kwargs)


class FixedCost(BaseModel):
    class CostCategory(models.TextChoices):
        RENT = 'RENT', '임대료/시설비'
        LABOR = 'LABOR', '인건비'
        EQUIPMENT = 'EQUIPMENT', '장비/감가상각'
        INSURANCE = 'INSURANCE', '보험료'
        TELECOM = 'TELECOM', '통신비'
        SUBSCRIPTION = 'SUBSCRIPTION', '구독/라이선스'
        OTHER = 'OTHER', '기타 고정비'

    class RecurringUnit(models.TextChoices):
        WEEKLY = 'WEEKLY', '주'
        MONTHLY = 'MONTHLY', '월'
        QUARTERLY = 'QUARTERLY', '분기'
        YEARLY = 'YEARLY', '년'

    category = models.CharField('비용구분', max_length=20, choices=CostCategory.choices)
    name = models.CharField('비용명', max_length=100)
    amount = models.DecimalField('금액', max_digits=15, decimal_places=0, validators=[MinValueValidator(0)])
    month = models.DateField('해당월')
    is_recurring = models.BooleanField('반복비용', default=True)
    recurring_unit = models.CharField(
        '반복단위', max_length=10,
        choices=RecurringUnit.choices, default=RecurringUnit.MONTHLY,
        blank=True,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '고정비'
        verbose_name_plural = '고정비'
        ordering = ['-month', 'category']
        indexes = [
            models.Index(fields=['month'], name='idx_fixedcost_month'),
        ]

    def __str__(self):
        return f'{self.name} ({self.month.strftime("%Y-%m")})'


class WithholdingTax(BaseModel):
    class TaxType(models.TextChoices):
        INCOME = 'INCOME', '소득세'
        CORPORATE = 'CORPORATE', '법인세'
        RESIDENT = 'RESIDENT', '주민세'

    tax_type = models.CharField('세목', max_length=20, choices=TaxType.choices)
    payee_name = models.CharField('소득자명', max_length=100)
    payment_date = models.DateField('지급일')
    gross_amount = models.DecimalField('지급액', max_digits=15, decimal_places=0, validators=[MinValueValidator(0)])
    tax_rate = models.DecimalField('세율(%)', max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    tax_amount = models.DecimalField('원천징수액', max_digits=15, decimal_places=0, validators=[MinValueValidator(0)])
    net_amount = models.DecimalField('실지급액', max_digits=15, decimal_places=0, validators=[MinValueValidator(0)])
    history = HistoricalRecords()

    class Meta:
        verbose_name = '원천징수'
        verbose_name_plural = '원천징수'
        ordering = ['-payment_date']

    def __str__(self):
        return f'{self.payee_name} - {self.payment_date}'


class AccountCode(BaseModel):
    class AccountType(models.TextChoices):
        ASSET = 'ASSET', '자산'
        LIABILITY = 'LIABILITY', '부채'
        EQUITY = 'EQUITY', '자본'
        REVENUE = 'REVENUE', '수익'
        EXPENSE = 'EXPENSE', '비용'

    class CashFlowCategory(models.TextChoices):
        OPERATING = 'OPERATING', '영업활동'
        INVESTING = 'INVESTING', '투자활동'
        FINANCING = 'FINANCING', '재무활동'

    code = models.CharField('계정코드', max_length=20, unique=True)
    name = models.CharField('계정명', max_length=100)
    account_type = models.CharField('계정유형', max_length=20, choices=AccountType.choices)
    parent = models.ForeignKey('self', verbose_name='상위계정', null=True, blank=True, on_delete=models.SET_NULL)
    cash_flow_category = models.CharField(
        '현금흐름 분류', max_length=20,
        choices=CashFlowCategory.choices, blank=True, default='',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '계정과목'
        verbose_name_plural = '계정과목'
        ordering = ['code']

    def __str__(self):
        return f'[{self.code}] {self.name}'


class Voucher(BaseModel):
    BUSINESS_KEY_FIELD = 'voucher_number'

    class VoucherType(models.TextChoices):
        RECEIPT = 'RECEIPT', '입금'
        PAYMENT = 'PAYMENT', '출금'
        TRANSFER = 'TRANSFER', '대체'

    class ApprovalStatus(models.TextChoices):
        DRAFT = 'DRAFT', '작성중'
        SUBMITTED = 'SUBMITTED', '제출'
        APPROVED = 'APPROVED', '승인'
        REJECTED = 'REJECTED', '반려'

    voucher_number = models.CharField('전표번호', max_length=30, unique=True, blank=True)
    voucher_type = models.CharField('전표유형', max_length=10, choices=VoucherType.choices)
    voucher_date = models.DateField('전표일')
    description = models.CharField('적요', max_length=200)
    approval_status = models.CharField(
        '승인상태', max_length=10,
        choices=ApprovalStatus.choices, default=ApprovalStatus.DRAFT,
    )
    approved_by = models.ForeignKey(
        'accounts.User', verbose_name='승인자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='approved_vouchers',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '전표'
        verbose_name_plural = '전표'
        ordering = ['-voucher_date', '-pk']
        indexes = [
            models.Index(
                fields=['voucher_date'], name='idx_voucher_date',
            ),
            models.Index(
                fields=['approval_status'], name='idx_voucher_approval',
            ),
        ]

    def __str__(self):
        return f'{self.voucher_number} ({self.get_voucher_type_display()})'

    def clean(self):
        super().clean()
        if self.pk and self.lines.exists() and not self.is_balanced:
            from django.core.exceptions import ValidationError
            raise ValidationError('차변 합계와 대변 합계가 일치하지 않습니다.')

    def save(self, *args, **kwargs):
        if not self.voucher_number:
            self.voucher_number = generate_document_number(Voucher, 'voucher_number', 'VC')
        super().save(*args, **kwargs)

    @property
    def total_debit(self):
        from django.db.models import Sum
        result = self.lines.aggregate(total=Sum('debit'))
        return result['total'] or 0

    @property
    def total_credit(self):
        from django.db.models import Sum
        result = self.lines.aggregate(total=Sum('credit'))
        return result['total'] or 0

    @property
    def is_balanced(self):
        return self.total_debit == self.total_credit


class VoucherLine(BaseModel):
    voucher = models.ForeignKey(Voucher, verbose_name='전표', on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(AccountCode, verbose_name='계정과목', on_delete=models.PROTECT)
    debit = models.DecimalField('차변', max_digits=15, decimal_places=0, default=0, validators=[MinValueValidator(0)])
    credit = models.DecimalField('대변', max_digits=15, decimal_places=0, default=0, validators=[MinValueValidator(0)])
    description = models.CharField('적요', max_length=200, blank=True)
    cost_center = models.ForeignKey(
        'CostCenter', verbose_name='원가센터',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '전표항목'
        verbose_name_plural = '전표항목'
        ordering = ['pk']
        indexes = [
            models.Index(fields=['account', 'voucher'], name='idx_voucherline_acct_vch'),
        ]

    def __str__(self):
        return f'{self.account.name} 차:{self.debit} 대:{self.credit}'

    def clean(self):
        super().clean()
        if self.debit and self.credit and self.debit > 0 and self.credit > 0:
            from django.core.exceptions import ValidationError
            raise ValidationError('차변과 대변을 동시에 입력할 수 없습니다.')


class AccountReceivable(BaseModel):
    """미수금"""

    class Status(models.TextChoices):
        PENDING = 'PENDING', '미수'
        PARTIAL = 'PARTIAL', '부분입금'
        PAID = 'PAID', '완납'
        OVERDUE = 'OVERDUE', '연체'

    partner = models.ForeignKey(
        'sales.Partner', verbose_name='거래처',
        on_delete=models.PROTECT, related_name='receivables',
    )
    order = models.ForeignKey(
        'sales.Order', verbose_name='주문',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='receivables',
    )
    invoice = models.ForeignKey(
        TaxInvoice, verbose_name='세금계산서',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='receivables',
    )
    amount = models.DecimalField('청구금액', max_digits=15, decimal_places=0, validators=[MinValueValidator(0)])
    paid_amount = models.DecimalField('입금액', max_digits=15, decimal_places=0, default=0, validators=[MinValueValidator(0)])
    due_date = models.DateField('납기일')
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.PENDING,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '미수금'
        verbose_name_plural = '미수금'
        ordering = ['-due_date', '-pk']
        indexes = [
            models.Index(fields=['status'], name='idx_ar_status'),
            models.Index(fields=['due_date'], name='idx_ar_due_date'),
        ]

    def __str__(self):
        return f'{self.partner.name} - {self.amount}원 ({self.get_status_display()})'

    @property
    def remaining_amount(self):
        return self.amount - self.paid_amount

    @property
    def is_overdue(self):
        return self.status != self.Status.PAID and self.due_date < date.today()


class AccountPayable(BaseModel):
    """미지급금"""

    class Status(models.TextChoices):
        PENDING = 'PENDING', '미지급'
        PARTIAL = 'PARTIAL', '부분지급'
        PAID = 'PAID', '완납'
        OVERDUE = 'OVERDUE', '연체'

    partner = models.ForeignKey(
        'sales.Partner', verbose_name='거래처',
        on_delete=models.PROTECT, related_name='payables',
    )
    purchase_order = models.ForeignKey(
        'purchase.PurchaseOrder', verbose_name='발주서',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='payables',
    )
    invoice = models.ForeignKey(
        TaxInvoice, verbose_name='세금계산서',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='payables',
    )
    amount = models.DecimalField('금액', max_digits=15, decimal_places=0, validators=[MinValueValidator(0)])
    paid_amount = models.DecimalField('지급액', max_digits=15, decimal_places=0, default=0, validators=[MinValueValidator(0)])
    due_date = models.DateField('납기일')
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.PENDING,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '미지급금'
        verbose_name_plural = '미지급금'
        ordering = ['-due_date', '-pk']
        indexes = [
            models.Index(fields=['status'], name='idx_ap_status'),
            models.Index(fields=['due_date'], name='idx_ap_due_date'),
        ]

    def __str__(self):
        return f'{self.partner.name} - {self.amount}원 ({self.get_status_display()})'

    @property
    def remaining_amount(self):
        return self.amount - self.paid_amount

    @property
    def is_overdue(self):
        return self.status != self.Status.PAID and self.due_date < date.today()


class BankAccount(BaseModel):
    """결제계좌"""

    class AccountType(models.TextChoices):
        PERSONAL = 'PERSONAL', '개인통장'
        BUSINESS = 'BUSINESS', '사업자통장'
        PLATFORM = 'PLATFORM', '플랫폼'

    employee = models.ForeignKey(
        'hr.EmployeeProfile', verbose_name='직원',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='bank_accounts',
        help_text='급여계좌 연동 시 직원 프로필과 연결',
    )
    partner = models.ForeignKey(
        'sales.Partner', verbose_name='거래처',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='bank_accounts',
        help_text='거래처 결제계좌 연동',
    )
    name = models.CharField('계좌별칭', max_length=100)
    account_type = models.CharField('계좌유형', max_length=20, choices=AccountType.choices)
    owner = models.CharField('소유자', max_length=50)
    bank = models.CharField('은행/플랫폼', max_length=50, blank=True)
    account_number = models.CharField('계좌번호', max_length=50, blank=True)
    is_default = models.BooleanField('기본계좌', default=False)
    show_on_dashboard = models.BooleanField('대시보드 표시', default=False, help_text='메인 대시보드에 잔액 표시')
    account_code = models.ForeignKey(
        AccountCode, verbose_name='계정과목',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='bank_accounts',
    )
    opening_balance = models.DecimalField(
        '기초잔액', max_digits=15, decimal_places=0, default=0,
    )
    balance = models.DecimalField(
        '현재잔액', max_digits=15, decimal_places=0, default=0,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '결제계좌'
        verbose_name_plural = '결제계좌'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.owner})'

    def save(self, *args, **kwargs):
        if self.is_default:
            with transaction.atomic():
                # 같은 소유자(거래처 또는 직원) 내 다른 기본계좌만 해제
                qs = BankAccount.objects.filter(is_default=True).exclude(pk=self.pk)
                if self.partner_id:
                    qs = qs.filter(partner_id=self.partner_id)
                elif self.employee_id:
                    qs = qs.filter(employee_id=self.employee_id)
                else:
                    # 거래처/직원 미연결 계좌끼리만
                    qs = qs.filter(partner__isnull=True, employee__isnull=True)
                qs.update(is_default=False)
        super().save(*args, **kwargs)


class CreditCard(BaseModel):
    """법인카드/개인카드"""
    BUSINESS_KEY_FIELD = 'name'

    class CardType(models.TextChoices):
        CORPORATE = 'CORPORATE', '법인카드'
        PERSONAL = 'PERSONAL', '개인카드'
        CHECK = 'CHECK', '체크카드'

    class CardIssuer(models.TextChoices):
        KB = 'KB', '국민카드'
        SHINHAN = 'SHINHAN', '신한카드'
        SAMSUNG = 'SAMSUNG', '삼성카드'
        HYUNDAI = 'HYUNDAI', '현대카드'
        LOTTE = 'LOTTE', '롯데카드'
        WOORI = 'WOORI', '우리카드'
        HANA = 'HANA', '하나카드'
        NH = 'NH', 'NH농협카드'
        BC = 'BC', 'BC카드'
        OTHER = 'OTHER', '기타'

    name = models.CharField('카드별칭', max_length=100)
    card_type = models.CharField('카드유형', max_length=20, choices=CardType.choices)
    card_issuer = models.CharField('카드사', max_length=20, choices=CardIssuer.choices)
    card_number_last4 = models.CharField('카드번호 끝4자리', max_length=4)
    cardholder = models.CharField('카드소유자', max_length=50)
    employee = models.ForeignKey(
        'hr.EmployeeProfile', verbose_name='사용자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='credit_cards',
    )
    expiry_date = models.CharField('유효기간', max_length=5, blank=True, help_text='MM/YY')
    monthly_limit = models.DecimalField('월간한도', max_digits=15, decimal_places=0, default=0)
    used_amount = models.DecimalField('당월사용액', max_digits=15, decimal_places=0, default=0)
    billing_day = models.IntegerField('결제일', default=25, help_text='매월 결제일 (1~28)')
    payment_account = models.ForeignKey(
        'BankAccount', verbose_name='결제계좌',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='linked_cards',
    )
    account_code = models.ForeignKey(
        'AccountCode', verbose_name='계정과목',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='credit_cards',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '카드'
        verbose_name_plural = '카드'
        ordering = ['-pk']

    def __str__(self):
        return f'{self.name} ({self.get_card_issuer_display()} {self.card_number_last4})'

    @property
    def remaining_limit(self):
        return self.monthly_limit - self.used_amount

    @property
    def usage_rate(self):
        if self.monthly_limit <= 0:
            return 0
        return round(self.used_amount / self.monthly_limit * 100, 1)


class CardTransaction(BaseModel):
    """카드 사용내역"""
    BUSINESS_KEY_FIELD = 'authorization_number'

    class Category(models.TextChoices):
        PURCHASE = 'PURCHASE', '구매/매입'
        TRAVEL = 'TRAVEL', '출장/교통'
        ENTERTAINMENT = 'ENTERTAINMENT', '접대/회의'
        SUPPLIES = 'SUPPLIES', '사무용품'
        FUEL = 'FUEL', '유류비'
        SUBSCRIPTION = 'SUBSCRIPTION', '정기구독'
        OTHER = 'OTHER', '기타'

    card = models.ForeignKey(
        CreditCard, verbose_name='카드',
        on_delete=models.PROTECT, related_name='transactions',
    )
    transaction_date = models.DateField('거래일')
    merchant_name = models.CharField('가맹점명', max_length=100)
    amount = models.DecimalField(
        '거래금액', max_digits=15, decimal_places=0,
        validators=[MinValueValidator(0)],
    )
    tax_amount = models.DecimalField('부가세', max_digits=15, decimal_places=0, default=0)
    installments = models.IntegerField('할부개월', default=0, help_text='0=일시불')
    authorization_number = models.CharField('승인번호', max_length=30, blank=True)
    category = models.CharField(
        '카테고리', max_length=20,
        choices=Category.choices, default=Category.OTHER,
    )
    partner = models.ForeignKey(
        'sales.Partner', verbose_name='거래처',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='card_transactions',
    )
    voucher = models.ForeignKey(
        'Voucher', verbose_name='자동전표',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='card_transactions',
    )
    is_cancelled = models.BooleanField('취소여부', default=False)
    cancelled_date = models.DateField('취소일', null=True, blank=True)
    billing = models.ForeignKey(
        'CardBilling', verbose_name='청구서',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='transactions',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '카드거래'
        verbose_name_plural = '카드거래'
        ordering = ['-transaction_date', '-pk']
        indexes = [
            models.Index(fields=['card', 'transaction_date'], name='idx_cardtx_card_date'),
        ]

    def __str__(self):
        return f'{self.card.name} {self.merchant_name} {self.amount:,}원'


class CardBilling(BaseModel):
    """카드 월별 청구"""

    class Status(models.TextChoices):
        PENDING = 'PENDING', '결제대기'
        PAID = 'PAID', '결제완료'
        PARTIAL = 'PARTIAL', '부분결제'
        OVERDUE = 'OVERDUE', '연체'

    card = models.ForeignKey(
        CreditCard, verbose_name='카드',
        on_delete=models.PROTECT, related_name='billings',
    )
    billing_month = models.DateField('청구월', help_text='해당월 1일')
    total_amount = models.DecimalField('청구금액', max_digits=15, decimal_places=0, default=0)
    paid_amount = models.DecimalField('결제금액', max_digits=15, decimal_places=0, default=0)
    payment_due_date = models.DateField('결제기한')
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.PENDING,
    )
    payment = models.ForeignKey(
        'Payment', verbose_name='결제',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='card_billings',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '카드청구'
        verbose_name_plural = '카드청구'
        ordering = ['-billing_month', '-pk']
        unique_together = [['card', 'billing_month']]

    def __str__(self):
        return f'{self.card.name} {self.billing_month.strftime("%Y-%m")} ({self.get_status_display()})'

    @property
    def remaining_amount(self):
        return self.total_amount - self.paid_amount


class Payment(BaseModel):
    """입출금 기록"""
    BUSINESS_KEY_FIELD = 'payment_number'

    class PaymentType(models.TextChoices):
        RECEIPT = 'RECEIPT', '입금'
        DISBURSEMENT = 'DISBURSEMENT', '출금'

    class PaymentMethod(models.TextChoices):
        BANK_TRANSFER = 'BANK_TRANSFER', '계좌이체'
        CASH = 'CASH', '현금'
        CHECK = 'CHECK', '수표'
        CARD = 'CARD', '카드'

    payment_number = models.CharField('입출금번호', max_length=30, unique=True, blank=True)
    payment_type = models.CharField('유형', max_length=20, choices=PaymentType.choices)
    partner = models.ForeignKey(
        'sales.Partner', verbose_name='거래처',
        on_delete=models.PROTECT, related_name='payments',
    )
    bank_account = models.ForeignKey(
        BankAccount, verbose_name='결제계좌',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='payments',
    )
    voucher = models.ForeignKey(
        Voucher, verbose_name='자동전표',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='payments',
    )
    receivable = models.ForeignKey(
        AccountReceivable, verbose_name='미수금',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='payments',
    )
    payable = models.ForeignKey(
        AccountPayable, verbose_name='미지급금',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='payments',
    )
    amount = models.DecimalField('금액', max_digits=15, decimal_places=0, validators=[MinValueValidator(0)])
    payment_date = models.DateField('입출금일')
    payment_method = models.CharField(
        '결제수단', max_length=20,
        choices=PaymentMethod.choices, default=PaymentMethod.BANK_TRANSFER,
    )
    reference = models.CharField('참조', max_length=100, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '입출금'
        verbose_name_plural = '입출금'
        ordering = ['-payment_date', '-pk']
        indexes = [
            models.Index(fields=['payment_type'], name='idx_payment_type'),
            models.Index(fields=['payment_date'], name='idx_payment_date'),
        ]

    def __str__(self):
        return f'{self.payment_number} ({self.get_payment_type_display()})'

    def save(self, *args, **kwargs):
        if not self.payment_number:
            self.payment_number = generate_document_number(Payment, 'payment_number', 'PM')
        super().save(*args, **kwargs)


class AccountTransfer(BaseModel):
    """계좌간 이체"""
    BUSINESS_KEY_FIELD = 'transfer_number'

    transfer_number = models.CharField('이체번호', max_length=30, unique=True, blank=True)
    from_account = models.ForeignKey(
        BankAccount, verbose_name='출금계좌',
        on_delete=models.PROTECT, related_name='transfers_out',
    )
    to_account = models.ForeignKey(
        BankAccount, verbose_name='입금계좌',
        on_delete=models.PROTECT, related_name='transfers_in',
    )
    amount = models.DecimalField('이체금액', max_digits=15, decimal_places=0, validators=[MinValueValidator(1)])
    transfer_date = models.DateField('이체일')
    description = models.CharField('적요', max_length=200, blank=True)
    voucher = models.ForeignKey(
        Voucher, verbose_name='자동전표',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='account_transfers',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '계좌이체'
        verbose_name_plural = '계좌이체'
        ordering = ['-transfer_date', '-pk']
        indexes = [
            models.Index(fields=['transfer_date'], name='idx_acct_transfer_date'),
        ]

    def __str__(self):
        return f'{self.transfer_number} ({self.from_account.name} → {self.to_account.name})'

    def save(self, *args, **kwargs):
        if not self.transfer_number:
            self.transfer_number = generate_document_number(AccountTransfer, 'transfer_number', 'BT')
        super().save(*args, **kwargs)


class CostSettlement(BaseModel):
    """원가 정산(월마감) — 제품별 원가/재고 스냅샷"""
    BUSINESS_KEY_FIELD = 'settlement_number'

    class Period(models.TextChoices):
        MONTHLY = 'MONTHLY', '월'
        QUARTERLY = 'QUARTERLY', '분기'
        YEARLY = 'YEARLY', '년'

    settlement_number = models.CharField(
        '정산번호', max_length=30, unique=True, blank=True,
    )
    period_type = models.CharField(
        '정산단위', max_length=10,
        choices=Period.choices, default=Period.MONTHLY,
    )
    period_start = models.DateField('정산 시작일')
    period_end = models.DateField('정산 종료일')
    settled_at = models.DateTimeField('정산일시', auto_now_add=True)
    total_inventory_value = models.DecimalField(
        '총 재고자산', max_digits=15, decimal_places=0, default=0,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '원가정산'
        verbose_name_plural = '원가정산'
        ordering = ['-settlement_number']
        constraints = [
            models.UniqueConstraint(
                fields=['period_type', 'period_start', 'period_end'],
                name='uq_settlement_period',
            ),
        ]

    def __str__(self):
        return f'{self.settlement_number} ({self.period_start}~{self.period_end})'

    def save(self, *args, **kwargs):
        if not self.settlement_number:
            self.settlement_number = generate_document_number(
                CostSettlement, 'settlement_number', 'CS',
            )
        super().save(*args, **kwargs)


class CostSettlementItem(BaseModel):
    """정산 시점 제품별 스냅샷"""

    settlement = models.ForeignKey(
        CostSettlement, verbose_name='정산',
        on_delete=models.CASCADE, related_name='items',
    )
    product = models.ForeignKey(
        'inventory.Product', verbose_name='제품',
        on_delete=models.PROTECT,
    )
    stock_quantity = models.IntegerField('재고수량')
    cost_price = models.DecimalField(
        '확정원가', max_digits=12, decimal_places=0,
    )
    inventory_value = models.DecimalField(
        '재고자산가액', max_digits=15, decimal_places=0,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '정산항목'
        verbose_name_plural = '정산항목'
        ordering = ['pk']
        constraints = [
            models.UniqueConstraint(
                fields=['settlement', 'product'],
                name='uq_settlement_product',
            ),
        ]

    def __str__(self):
        return f'{self.product.name}: {self.cost_price}원 x {self.stock_quantity}'


class PaymentDistribution(BaseModel):
    """결제 분배 (하나의 입금을 여러 계좌로 분배)"""

    payment = models.ForeignKey(
        Payment, verbose_name='입출금',
        on_delete=models.CASCADE, related_name='distributions',
    )
    bank_account = models.ForeignKey(
        BankAccount, verbose_name='대상계좌',
        on_delete=models.PROTECT, related_name='distributions',
    )
    amount = models.DecimalField('분배금액', max_digits=15, decimal_places=0, validators=[MinValueValidator(1)])
    description = models.CharField('적요', max_length=200, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '결제분배'
        verbose_name_plural = '결제분배'
        ordering = ['pk']

    def __str__(self):
        return f'{self.payment.payment_number} → {self.bank_account.name} ({self.amount:,}원)'


class SalesSettlement(BaseModel):
    """매출 정산 — 주문 건별 선택 정산"""
    BUSINESS_KEY_FIELD = 'settlement_number'

    settlement_number = models.CharField(
        '정산번호', max_length=30, unique=True, blank=True,
    )
    settlement_date = models.DateField('정산일')
    description = models.CharField('적요', max_length=200, blank=True)
    orders = models.ManyToManyField(
        'sales.Order', verbose_name='정산 주문',
        through='SalesSettlementOrder',
        related_name='sales_settlements',
    )
    total_revenue = models.DecimalField(
        '총공급가액', max_digits=15, decimal_places=0, default=0,
    )
    total_cost = models.DecimalField(
        '총원가', max_digits=15, decimal_places=0, default=0,
    )
    total_tax = models.DecimalField(
        '총부가세', max_digits=15, decimal_places=0, default=0,
    )
    total_shipping = models.DecimalField(
        '총배송비', max_digits=15, decimal_places=0, default=0,
    )
    total_platform_commission = models.DecimalField(
        '총플랫폼수수료', max_digits=15, decimal_places=0, default=0,
        help_text='플랫폼(네이버, 쿠팡 등)에서 이미 공제된 수수료',
    )
    total_commission = models.DecimalField(
        '총정산수수료', max_digits=15, decimal_places=0, default=0,
        help_text='정산 시 수수료율로 추가 계산된 수수료',
    )
    total_profit = models.DecimalField(
        '총이익', max_digits=15, decimal_places=0, default=0,
    )
    total_cost_variance = models.DecimalField(
        '총원가차이', max_digits=15, decimal_places=0, default=0,
        help_text='양수=원가상승(불리), 음수=원가하락(유리)',
    )
    # 수수료 지급 관리
    commission_bank_account = models.ForeignKey(
        'accounting.BankAccount', verbose_name='수수료 출금계좌',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='commission_settlements',
    )
    commission_deposit_account = models.ForeignKey(
        'accounting.BankAccount', verbose_name='수수료 입금계좌',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='commission_deposit_settlements',
        help_text='거래처/파트너 입금계좌 (선택)',
    )
    commission_paid = models.BooleanField('수수료 지급완료', default=False)
    commission_paid_date = models.DateField(
        '수수료 지급일', null=True, blank=True,
    )
    commission_paid_amount = models.DecimalField(
        '수수료 지급액', max_digits=15, decimal_places=0, default=0,
    )
    commission_voucher = models.ForeignKey(
        'accounting.Voucher', verbose_name='수수료 전표',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='commission_settlements',
    )
    commission_memo = models.CharField(
        '수수료 지급 메모', max_length=200, blank=True,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '매출정산'
        verbose_name_plural = '매출정산'
        ordering = ['-settlement_date', '-pk']
        indexes = [
            models.Index(fields=['settlement_date'], name='idx_settlement_date'),
        ]

    def __str__(self):
        return f'{self.settlement_number} ({self.settlement_date})'

    def save(self, *args, **kwargs):
        if not self.settlement_number:
            self.settlement_number = generate_document_number(
                SalesSettlement, 'settlement_number', 'SS',
            )
        super().save(*args, **kwargs)

    @property
    def profit_rate(self):
        if self.total_revenue and int(self.total_revenue) > 0:
            return round(
                int(self.total_profit) / int(self.total_revenue) * 100, 1,
            )
        return 0

    @property
    def order_count(self):
        return self.settlement_orders.count()


class SalesSettlementOrder(BaseModel):
    """매출 정산 — 주문 항목"""

    settlement = models.ForeignKey(
        SalesSettlement, verbose_name='정산',
        on_delete=models.CASCADE, related_name='settlement_orders',
    )
    order = models.ForeignKey(
        'sales.Order', verbose_name='주문',
        on_delete=models.PROTECT, related_name='settlement_items',
    )
    revenue = models.DecimalField(
        '공급가액', max_digits=15, decimal_places=0, default=0,
    )
    cost = models.DecimalField(
        '원가(주문시점)', max_digits=15, decimal_places=0, default=0,
    )
    current_cost = models.DecimalField(
        '원가(정산시점)', max_digits=15, decimal_places=0, default=0,
        help_text='정산 생성 시 제품 현재 원가로 자동 측정',
    )
    cost_variance = models.DecimalField(
        '원가차이', max_digits=15, decimal_places=0, default=0,
        help_text='정산시점 원가 - 주문시점 원가 (양수=원가상승)',
    )
    cost_variance_rate = models.DecimalField(
        '원가차이율(%)', max_digits=7, decimal_places=2, default=0,
    )
    tax = models.DecimalField(
        '부가세', max_digits=15, decimal_places=0, default=0,
    )
    shipping = models.DecimalField(
        '배송비', max_digits=15, decimal_places=0, default=0,
    )
    platform_commission = models.DecimalField(
        '플랫폼 수수료', max_digits=15, decimal_places=0, default=0,
        help_text='플랫폼에서 이미 공제된 수수료',
    )
    commission_rate = models.DecimalField(
        '정산 수수료율(%)', max_digits=5, decimal_places=2, default=0,
    )
    commission = models.DecimalField(
        '정산 수수료', max_digits=15, decimal_places=0, default=0,
    )
    profit = models.DecimalField(
        '이익', max_digits=15, decimal_places=0, default=0,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '매출정산항목'
        verbose_name_plural = '매출정산항목'
        ordering = ['pk']
        constraints = [
            models.UniqueConstraint(
                fields=['settlement', 'order'],
                name='uq_settlement_order',
            ),
        ]

    def __str__(self):
        return f'{self.settlement.settlement_number} - {self.order.order_number}'


class Budget(BaseModel):
    """예산 관리 — 계정과목별 월 예산 설정 및 실적 대비"""
    account = models.ForeignKey(
        AccountCode, verbose_name='계정과목',
        on_delete=models.PROTECT, related_name='budgets',
    )
    year = models.PositiveIntegerField('연도')
    month = models.PositiveSmallIntegerField('월')
    budget_amount = models.DecimalField(
        '예산액', max_digits=15, decimal_places=0,
        default=0, validators=[MinValueValidator(0)],
    )
    description = models.CharField('비고', max_length=200, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '예산'
        verbose_name_plural = '예산'
        ordering = ['-year', '-month', 'account__code']
        constraints = [
            models.UniqueConstraint(
                fields=['account', 'year', 'month'],
                name='uq_budget_account_period',
            ),
        ]
        indexes = [
            models.Index(fields=['account', 'year', 'month'], name='idx_budget_acct_yr_mo'),
        ]

    def __str__(self):
        return f'{self.year}-{self.month:02d} [{self.account.code}] {self.account.name}'

    @property
    def actual_amount(self):
        """실적액 — 해당 기간 전표 합산"""
        from django.db.models import Sum
        from datetime import date
        start = date(self.year, self.month, 1)
        if self.month == 12:
            end = date(self.year + 1, 1, 1)
        else:
            end = date(self.year, self.month + 1, 1)

        totals = VoucherLine.objects.filter(
            account=self.account,
            is_active=True,
            voucher__is_active=True,
            voucher__voucher_date__gte=start,
            voucher__voucher_date__lt=end,
        ).aggregate(
            total_debit=Sum('debit'),
            total_credit=Sum('credit'),
        )
        debit = int(totals['total_debit'] or 0)
        credit = int(totals['total_credit'] or 0)
        # 비용 계정: 차변이 실적, 수익 계정: 대변이 실적
        if self.account.account_type == 'EXPENSE':
            return debit
        elif self.account.account_type == 'REVENUE':
            return credit
        return debit - credit

    @property
    def variance(self):
        """차이 (예산 - 실적)"""
        return int(self.budget_amount) - self.actual_amount

    @property
    def execution_rate(self):
        """집행율(%)"""
        budget = int(self.budget_amount)
        if budget <= 0:
            return 0
        return round(self.actual_amount / budget * 100, 1)


class ClosingPeriod(BaseModel):
    """결산 마감 — 월별 회계 마감 관리"""

    year = models.PositiveIntegerField('년도')
    month = models.PositiveIntegerField('월')
    closed_at = models.DateTimeField('마감일시', null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='마감자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='closed_periods',
    )
    is_closed = models.BooleanField('마감여부', default=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '결산마감'
        verbose_name_plural = '결산마감'
        ordering = ['-year', '-month']
        constraints = [
            models.UniqueConstraint(
                fields=['year', 'month'],
                name='uq_closing_year_month',
            ),
        ]

    def __str__(self):
        return f'{self.year}년 {self.month:02d}월 {"마감" if self.is_closed else "미마감"}'


class CostCenter(BaseModel):
    """원가/이익센터"""

    class CenterType(models.TextChoices):
        COST = 'COST', '원가센터'
        PROFIT = 'PROFIT', '이익센터'
        INVESTMENT = 'INVESTMENT', '투자센터'

    code = models.CharField('코드', max_length=20, unique=True)
    name = models.CharField('센터명', max_length=100)
    parent = models.ForeignKey(
        'self', verbose_name='상위센터',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='children',
    )
    center_type = models.CharField(
        '센터유형', max_length=20,
        choices=CenterType.choices, default=CenterType.COST,
    )
    department = models.ForeignKey(
        'hr.Department', verbose_name='부서',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='책임자',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '원가센터'
        verbose_name_plural = '원가센터'
        ordering = ['code']

    def __str__(self):
        return f'[{self.code}] {self.name}'


class DashboardWidget(BaseModel):
    """대시보드 위젯 설정"""

    class WidgetType(models.TextChoices):
        CHART = 'CHART', '차트'
        TABLE = 'TABLE', '테이블'
        KPI = 'KPI', 'KPI'
        PIVOT = 'PIVOT', '피벗'

    name = models.CharField('위젯명', max_length=100)
    widget_type = models.CharField(
        '위젯유형', max_length=20,
        choices=WidgetType.choices,
    )
    config = models.JSONField('설정', default=dict)
    sort_order = models.PositiveIntegerField('정렬순서', default=0)
    is_visible = models.BooleanField('표시여부', default=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='사용자',
        null=True, blank=True, on_delete=models.CASCADE,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '대시보드 위젯'
        verbose_name_plural = '대시보드 위젯'
        ordering = ['sort_order']

    def __str__(self):
        return self.name


# ──── Phase 15: 다중법인/연결회계 ────

class Company(BaseModel):
    """법인(회사)"""
    name = models.CharField('법인명', max_length=100)
    code = models.CharField('법인코드', max_length=20, unique=True)
    legal_name = models.CharField('법적 명칭', max_length=200, blank=True)
    tax_id = models.CharField('사업자등록번호', max_length=20, blank=True)
    country_code = models.CharField('국가코드', max_length=5, default='KR')
    currency = models.ForeignKey(
        Currency, verbose_name='기준통화',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    address = models.TextField('주소', blank=True)
    parent = models.ForeignKey(
        'self', verbose_name='모회사',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='subsidiaries',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '법인'
        verbose_name_plural = '법인'
        ordering = ['code']

    def __str__(self):
        return f'[{self.code}] {self.name}'


class InterCompanyTransaction(BaseModel):
    """내부거래"""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '작성중'
        CONFIRMED = 'CONFIRMED', '확정'
        ELIMINATED = 'ELIMINATED', '제거완료'

    from_company = models.ForeignKey(
        Company, verbose_name='거래 발생 법인',
        on_delete=models.PROTECT, related_name='ic_transactions_from',
    )
    to_company = models.ForeignKey(
        Company, verbose_name='거래 상대 법인',
        on_delete=models.PROTECT, related_name='ic_transactions_to',
    )
    transaction_date = models.DateField('거래일')
    description = models.CharField('적요', max_length=200)
    amount = models.DecimalField(
        '금액', max_digits=15, decimal_places=0,
        validators=[MinValueValidator(0)],
    )
    currency_code = models.CharField('통화', max_length=3, default='KRW')
    voucher_from = models.ForeignKey(
        Voucher, verbose_name='발생법인 전표',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='ic_from',
    )
    voucher_to = models.ForeignKey(
        Voucher, verbose_name='상대법인 전표',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='ic_to',
    )
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.DRAFT,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '내부거래'
        verbose_name_plural = '내부거래'
        ordering = ['-transaction_date', '-pk']

    def __str__(self):
        return f'{self.from_company.code}→{self.to_company.code} {self.amount:,}원'


class ConsolidationPeriod(BaseModel):
    """연결결산 기간"""

    class Status(models.TextChoices):
        OPEN = 'OPEN', '진행중'
        CLOSED = 'CLOSED', '마감'

    year = models.PositiveIntegerField('연도')
    month = models.PositiveSmallIntegerField('월')
    status = models.CharField(
        '상태', max_length=10,
        choices=Status.choices, default=Status.OPEN,
    )
    companies = models.ManyToManyField(
        Company, verbose_name='대상 법인', blank=True,
        related_name='consolidation_periods',
    )
    elimination_entries = models.JSONField('내부거래 제거 내역', default=list, blank=True)
    consolidated_at = models.DateTimeField('연결일시', null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '연결결산기간'
        verbose_name_plural = '연결결산기간'
        ordering = ['-year', '-month']
        constraints = [
            models.UniqueConstraint(
                fields=['year', 'month'],
                name='uq_consolidation_period',
            ),
        ]

    def __str__(self):
        return f'{self.year}년 {self.month:02d}월 연결결산'


class ConsolidatedReport(BaseModel):
    """연결재무보고서"""

    class ReportType(models.TextChoices):
        PL = 'PL', '연결 손익계산서'
        BS = 'BS', '연결 재무상태표'
        CF = 'CF', '연결 현금흐름표'

    period = models.ForeignKey(
        ConsolidationPeriod, verbose_name='연결기간',
        on_delete=models.CASCADE, related_name='reports',
    )
    report_type = models.CharField(
        '보고서 유형', max_length=5,
        choices=ReportType.choices,
    )
    data = models.JSONField('보고서 데이터', default=dict)
    generated_at = models.DateTimeField('생성일시', null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '연결보고서'
        verbose_name_plural = '연결보고서'
        ordering = ['-pk']

    def __str__(self):
        return f'{self.period} - {self.get_report_type_display()}'


# ──── Phase 15: 오픈뱅킹 연동 ────

class BankConnection(BaseModel):
    """은행 연결"""

    class ConnectionType(models.TextChoices):
        OPENBANKING = 'OPENBANKING', '오픈뱅킹'
        SCRAPING = 'SCRAPING', '스크래핑'
        MANUAL = 'MANUAL', '수동'

    class ConnectionStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', '활성'
        INACTIVE = 'INACTIVE', '비활성'
        ERROR = 'ERROR', '오류'

    bank_name = models.CharField('은행명', max_length=50)
    bank_code = models.CharField('은행코드', max_length=10)
    account_number = models.CharField('계좌번호', max_length=50)
    account_holder = models.CharField('예금주', max_length=50)
    connection_type = models.CharField(
        '연결방식', max_length=20,
        choices=ConnectionType.choices, default=ConnectionType.MANUAL,
    )
    api_key_encrypted = models.TextField('API 키(암호화)', blank=True)
    status = models.CharField(
        '상태', max_length=20,
        choices=ConnectionStatus.choices, default=ConnectionStatus.ACTIVE,
    )
    last_sync = models.DateTimeField('마지막 동기화', null=True, blank=True)
    company = models.ForeignKey(
        Company, verbose_name='법인',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='bank_connections',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '은행연결'
        verbose_name_plural = '은행연결'
        ordering = ['bank_name']

    def __str__(self):
        return f'{self.bank_name} {self.account_number}'


class BankStatement(BaseModel):
    """은행 명세서"""

    class Status(models.TextChoices):
        IMPORTED = 'IMPORTED', '가져옴'
        RECONCILED = 'RECONCILED', '대사완료'

    connection = models.ForeignKey(
        BankConnection, verbose_name='은행연결',
        on_delete=models.PROTECT, related_name='statements',
    )
    statement_date = models.DateField('명세일')
    opening_balance = models.DecimalField('기초잔액', max_digits=15, decimal_places=0, default=0)
    closing_balance = models.DecimalField('기말잔액', max_digits=15, decimal_places=0, default=0)
    transaction_count = models.PositiveIntegerField('거래건수', default=0)
    imported_at = models.DateTimeField('가져온 일시', null=True, blank=True)
    status = models.CharField(
        '상태', max_length=20,
        choices=Status.choices, default=Status.IMPORTED,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '은행명세서'
        verbose_name_plural = '은행명세서'
        ordering = ['-statement_date']

    def __str__(self):
        return f'{self.connection.bank_name} {self.statement_date}'


class BankTransaction(BaseModel):
    """은행 거래"""

    class MatchStatus(models.TextChoices):
        UNMATCHED = 'UNMATCHED', '미매칭'
        AUTO_MATCHED = 'AUTO_MATCHED', '자동매칭'
        MANUAL_MATCHED = 'MANUAL_MATCHED', '수동매칭'
        EXCLUDED = 'EXCLUDED', '제외'

    statement = models.ForeignKey(
        BankStatement, verbose_name='명세서',
        on_delete=models.CASCADE, related_name='transactions',
    )
    transaction_date = models.DateField('거래일')
    description = models.CharField('적요', max_length=200)
    amount = models.DecimalField('금액', max_digits=15, decimal_places=0)
    balance_after = models.DecimalField('잔액', max_digits=15, decimal_places=0, default=0)
    counterparty = models.CharField('상대방', max_length=100, blank=True)
    reference_number = models.CharField('참조번호', max_length=50, blank=True)
    matched_voucher = models.ForeignKey(
        Voucher, verbose_name='매칭 전표',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='bank_transactions',
    )
    matched_payment = models.ForeignKey(
        Payment, verbose_name='매칭 입출금',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='bank_transactions',
    )
    match_status = models.CharField(
        '매칭상태', max_length=20,
        choices=MatchStatus.choices, default=MatchStatus.UNMATCHED,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '은행거래'
        verbose_name_plural = '은행거래'
        ordering = ['-transaction_date', '-pk']

    def __str__(self):
        return f'{self.transaction_date} {self.description} {self.amount:,}원'
