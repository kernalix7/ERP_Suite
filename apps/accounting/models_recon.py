"""대사(Reconciliation) 자동매칭 규칙 + 전표 승인 정책.

- BankReconRule: 입금자명·금액·일자 허용오차 기반 BankTransaction ↔ Payment 자동매칭
- CardReconRule: 카드사·승인번호·금액 기반 CardTransaction ↔ Payment 자동매칭
- VoucherApprovalConfig: 자동전표/수동전표 승인 정책 (금액 한도)
"""
from django.core.validators import MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class BankReconRule(BaseModel):
    """은행거래 자동매칭 규칙 — 우선순위 순으로 평가."""

    BUSINESS_KEY_FIELD = 'name'

    class MatchField(models.TextChoices):
        DEPOSITOR_NAME = 'DEPOSITOR_NAME', '입금자명'
        AMOUNT_EXACT = 'AMOUNT_EXACT', '금액 정확일치'
        AMOUNT_RANGE = 'AMOUNT_RANGE', '금액 범위'
        REFERENCE = 'REFERENCE', '적요/메모'

    name = models.CharField('규칙명', max_length=100, unique=True)
    priority = models.PositiveIntegerField(
        '우선순위', default=100,
        help_text='작을수록 먼저 평가',
    )
    bank_account = models.ForeignKey(
        'accounting.BankAccount', verbose_name='적용 계좌',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='recon_rules',
        help_text='공란 시 모든 계좌',
    )
    match_field = models.CharField(
        '매칭 기준', max_length=24,
        choices=MatchField.choices, default=MatchField.DEPOSITOR_NAME,
    )
    pattern = models.CharField(
        '매칭 패턴', max_length=200,
        help_text='입금자명/적요 substring (대소문자 무시), 금액은 숫자',
    )
    amount_tolerance = models.DecimalField(
        '금액 허용오차', max_digits=15, decimal_places=0,
        default=0, validators=[MinValueValidator(0)],
        help_text='AMOUNT_RANGE 시 ±오차',
    )
    date_tolerance_days = models.PositiveIntegerField(
        '일자 허용 오차(일)', default=3,
    )
    target_partner = models.ForeignKey(
        'sales.Partner', verbose_name='대상 거래처',
        null=True, blank=True, on_delete=models.SET_NULL,
        help_text='매칭 시 자동 연결할 거래처',
    )
    is_active_rule = models.BooleanField('규칙 활성', default=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '은행거래 매칭규칙'
        verbose_name_plural = '은행거래 매칭규칙'
        ordering = ['priority', 'name']

    def __str__(self):
        return f'[P{self.priority}] {self.name}'

    def matches(self, txn) -> bool:
        """BankTransaction 1건과 매칭 여부 평가.

        bank_account는 BankTransaction.statement.bank_account 경유.
        """
        if self.bank_account_id:
            stmt_bank_id = getattr(
                getattr(txn, 'statement', None), 'bank_account_id', None,
            )
            if stmt_bank_id != self.bank_account_id:
                return False
        if self.match_field == self.MatchField.DEPOSITOR_NAME:
            return self.pattern.lower() in (txn.counterparty or '').lower()
        if self.match_field == self.MatchField.AMOUNT_EXACT:
            try:
                target = int(self.pattern)
            except (TypeError, ValueError):
                return False
            return int(txn.amount or 0) == target
        if self.match_field == self.MatchField.AMOUNT_RANGE:
            try:
                target = int(self.pattern)
            except (TypeError, ValueError):
                return False
            tol = int(self.amount_tolerance or 0)
            return abs(int(txn.amount or 0) - target) <= tol
        if self.match_field == self.MatchField.REFERENCE:
            return self.pattern.lower() in (txn.description or '').lower()
        return False


class CardReconRule(BaseModel):
    """카드거래 자동매칭 규칙 — CardTransaction ↔ Payment(DISBURSEMENT) 매칭."""

    BUSINESS_KEY_FIELD = 'name'

    name = models.CharField('규칙명', max_length=100, unique=True)
    priority = models.PositiveIntegerField('우선순위', default=100)
    card = models.ForeignKey(
        'accounting.CreditCard', verbose_name='적용 카드',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='recon_rules',
    )
    merchant_pattern = models.CharField(
        '가맹점 패턴', max_length=200, blank=True,
        help_text='가맹점명 substring (대소문자 무시)',
    )
    target_partner = models.ForeignKey(
        'sales.Partner', verbose_name='대상 거래처',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    target_account = models.ForeignKey(
        'accounting.AccountCode', verbose_name='대상 계정',
        null=True, blank=True, on_delete=models.SET_NULL,
        help_text='매칭 시 자동 분개할 비용 계정',
    )
    is_active_rule = models.BooleanField('규칙 활성', default=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '카드거래 매칭규칙'
        verbose_name_plural = '카드거래 매칭규칙'
        ordering = ['priority', 'name']

    def __str__(self):
        return f'[P{self.priority}] {self.name}'

    def matches(self, txn) -> bool:
        """CardTransaction 1건과 매칭 여부 평가."""
        if self.card_id and txn.card_id != self.card_id:
            return False
        if self.merchant_pattern:
            merchant = (
                getattr(txn, 'merchant_name', '')
                or getattr(txn, 'description', '')
                or ''
            )
            return self.merchant_pattern.lower() in merchant.lower()
        return True  # 카드 한정 + 패턴 없음 → 모두 매칭


class VoucherApprovalConfig(BaseModel):
    """전표 승인 정책 — 금액 한도 + 자동전표 정책.

    싱글톤 패턴으로 운영 (admin이 1건 생성, 이후 수정만).
    """

    auto_voucher_default_status = models.CharField(
        '자동전표 기본상태', max_length=15,
        choices=[
            ('DRAFT', 'DRAFT (작성중)'),
            ('SUBMITTED', 'SUBMITTED (제출)'),
            ('APPROVED', 'APPROVED (즉시 승인)'),
        ],
        default='APPROVED',
        help_text='시그널 자동생성 전표의 기본 승인상태',
    )
    auto_approval_amount_threshold = models.DecimalField(
        '자동승인 금액한도', max_digits=15, decimal_places=0, default=0,
        validators=[MinValueValidator(0)],
        help_text='이 금액 초과 시 자동전표도 SUBMITTED 강제 (0=한도없음)',
    )
    manual_approval_amount_threshold = models.DecimalField(
        '수동전표 결재필수 한도', max_digits=15, decimal_places=0,
        default=0, validators=[MinValueValidator(0)],
        help_text='수동 입력 전표가 이 금액 초과 시 ApprovalRequest 자동생성',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '전표 승인 정책'
        verbose_name_plural = '전표 승인 정책'

    def __str__(self):
        return f'전표승인정책 (자동={self.auto_voucher_default_status})'

    @classmethod
    def get_active(cls):
        """활성 설정 1건 조회 — 없으면 기본값 인스턴스 반환 (저장 안함)."""
        obj = cls.objects.filter(is_active=True).first()
        if obj:
            return obj
        return cls(
            auto_voucher_default_status='APPROVED',
            auto_approval_amount_threshold=0,
            manual_approval_amount_threshold=0,
        )
