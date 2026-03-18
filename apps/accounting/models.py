from datetime import date

from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


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
    class InvoiceType(models.TextChoices):
        SALES = 'SALES', '매출'
        PURCHASE = 'PURCHASE', '매입'

    invoice_number = models.CharField('세금계산서번호', max_length=50, unique=True)
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
    supply_amount = models.DecimalField('공급가액', max_digits=15, decimal_places=0)
    tax_amount = models.DecimalField('부가세', max_digits=15, decimal_places=0)
    total_amount = models.DecimalField('합계', max_digits=15, decimal_places=0)
    description = models.TextField('적요', blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '세금계산서'
        verbose_name_plural = '세금계산서'
        ordering = ['-issue_date', '-pk']
        indexes = [
            models.Index(fields=['issue_date'], name='idx_invoice_date'),
            models.Index(fields=['invoice_type'], name='idx_invoice_type'),
        ]

    def __str__(self):
        return f'{self.invoice_number} ({self.get_invoice_type_display()})'


class FixedCost(BaseModel):
    class CostCategory(models.TextChoices):
        RENT = 'RENT', '임대료/시설비'
        LABOR = 'LABOR', '인건비'
        EQUIPMENT = 'EQUIPMENT', '장비/감가상각'
        INSURANCE = 'INSURANCE', '보험료'
        TELECOM = 'TELECOM', '통신비'
        SUBSCRIPTION = 'SUBSCRIPTION', '구독/라이선스'
        OTHER = 'OTHER', '기타 고정비'

    category = models.CharField('비용구분', max_length=20, choices=CostCategory.choices)
    name = models.CharField('비용명', max_length=100)
    amount = models.DecimalField('금액', max_digits=15, decimal_places=0)
    month = models.DateField('해당월')
    is_recurring = models.BooleanField('반복비용', default=True)
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
    gross_amount = models.DecimalField('지급액', max_digits=15, decimal_places=0)
    tax_rate = models.DecimalField('세율(%)', max_digits=5, decimal_places=2)
    tax_amount = models.DecimalField('원천징수액', max_digits=15, decimal_places=0)
    net_amount = models.DecimalField('실지급액', max_digits=15, decimal_places=0)
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

    code = models.CharField('계정코드', max_length=20, unique=True)
    name = models.CharField('계정명', max_length=100)
    account_type = models.CharField('계정유형', max_length=20, choices=AccountType.choices)
    parent = models.ForeignKey('self', verbose_name='상위계정', null=True, blank=True, on_delete=models.SET_NULL)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '계정과목'
        verbose_name_plural = '계정과목'
        ordering = ['code']

    def __str__(self):
        return f'[{self.code}] {self.name}'


class Voucher(BaseModel):
    class VoucherType(models.TextChoices):
        RECEIPT = 'RECEIPT', '입금'
        PAYMENT = 'PAYMENT', '출금'
        TRANSFER = 'TRANSFER', '대체'

    class ApprovalStatus(models.TextChoices):
        DRAFT = 'DRAFT', '작성중'
        SUBMITTED = 'SUBMITTED', '제출'
        APPROVED = 'APPROVED', '승인'
        REJECTED = 'REJECTED', '반려'

    voucher_number = models.CharField('전표번호', max_length=30, unique=True)
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

    @property
    def total_debit(self):
        return sum(line.debit for line in self.lines.all())

    @property
    def total_credit(self):
        return sum(line.credit for line in self.lines.all())

    @property
    def is_balanced(self):
        return self.total_debit == self.total_credit


class VoucherLine(BaseModel):
    voucher = models.ForeignKey(Voucher, verbose_name='전표', on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(AccountCode, verbose_name='계정과목', on_delete=models.PROTECT)
    debit = models.DecimalField('차변', max_digits=15, decimal_places=0, default=0)
    credit = models.DecimalField('대변', max_digits=15, decimal_places=0, default=0)
    description = models.CharField('적요', max_length=200, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '전표항목'
        verbose_name_plural = '전표항목'

    def __str__(self):
        return f'{self.account.name} 차:{self.debit} 대:{self.credit}'


class ApprovalRequest(BaseModel):
    """결재/품의 요청"""

    class DocCategory(models.TextChoices):
        PURCHASE = 'PURCHASE', '구매품의'
        EXPENSE = 'EXPENSE', '지출품의'
        BUDGET = 'BUDGET', '예산신청'
        CONTRACT = 'CONTRACT', '계약체결'
        GENERAL = 'GENERAL', '일반결재'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '작성중'
        SUBMITTED = 'SUBMITTED', '결재요청'
        APPROVED = 'APPROVED', '승인'
        REJECTED = 'REJECTED', '반려'
        CANCELLED = 'CANCELLED', '취소'

    request_number = models.CharField('결재번호', max_length=30, unique=True)
    category = models.CharField('문서종류', max_length=20, choices=DocCategory.choices)
    title = models.CharField('제목', max_length=200)
    content = models.TextField('내용')
    amount = models.DecimalField('금액', max_digits=15, decimal_places=0, default=0)
    status = models.CharField('상태', max_length=20, choices=Status.choices, default=Status.DRAFT)
    requester = models.ForeignKey(
        'accounts.User', verbose_name='요청자',
        on_delete=models.PROTECT, related_name='approval_requests',
    )
    approver = models.ForeignKey(
        'accounts.User', verbose_name='결재자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='approval_assigned',
    )
    submitted_at = models.DateTimeField('제출일', null=True, blank=True)
    approved_at = models.DateTimeField('결재일', null=True, blank=True)
    reject_reason = models.TextField('반려사유', blank=True)
    current_step = models.PositiveIntegerField('현재 결재단계', default=1)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '결재/품의'
        verbose_name_plural = '결재/품의'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['status'], name='idx_approval_status',
            ),
        ]

    def __str__(self):
        return f'{self.request_number} - {self.title}'


class ApprovalStep(BaseModel):
    """결재 단계"""

    class Status(models.TextChoices):
        PENDING = 'PENDING', '대기'
        APPROVED = 'APPROVED', '승인'
        REJECTED = 'REJECTED', '반려'

    request = models.ForeignKey(
        ApprovalRequest, verbose_name='결재요청',
        on_delete=models.CASCADE, related_name='steps',
    )
    step_order = models.PositiveIntegerField('단계순서')
    approver = models.ForeignKey(
        'accounts.User', verbose_name='결재자',
        on_delete=models.PROTECT, related_name='approval_steps',
    )
    status = models.CharField('상태', max_length=20, choices=Status.choices, default=Status.PENDING)
    comment = models.TextField('의견', blank=True)
    acted_at = models.DateTimeField('처리일시', null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '결재단계'
        verbose_name_plural = '결재단계'
        ordering = ['step_order']
        unique_together = [['request', 'step_order']]

    def __str__(self):
        return f'{self.request.request_number} - {self.step_order}단계 ({self.approver})'


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
    amount = models.DecimalField('청구금액', max_digits=15, decimal_places=0)
    paid_amount = models.DecimalField('입금액', max_digits=15, decimal_places=0, default=0)
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
    invoice = models.ForeignKey(
        TaxInvoice, verbose_name='세금계산서',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='payables',
    )
    amount = models.DecimalField('금액', max_digits=15, decimal_places=0)
    paid_amount = models.DecimalField('지급액', max_digits=15, decimal_places=0, default=0)
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


class Payment(BaseModel):
    """입출금 기록"""

    class PaymentType(models.TextChoices):
        RECEIPT = 'RECEIPT', '입금'
        DISBURSEMENT = 'DISBURSEMENT', '출금'

    class PaymentMethod(models.TextChoices):
        BANK_TRANSFER = 'BANK_TRANSFER', '계좌이체'
        CASH = 'CASH', '현금'
        CHECK = 'CHECK', '수표'
        CARD = 'CARD', '카드'

    payment_number = models.CharField('입출금번호', max_length=30, unique=True)
    payment_type = models.CharField('유형', max_length=20, choices=PaymentType.choices)
    partner = models.ForeignKey(
        'sales.Partner', verbose_name='거래처',
        on_delete=models.PROTECT, related_name='payments',
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
    amount = models.DecimalField('금액', max_digits=15, decimal_places=0)
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
