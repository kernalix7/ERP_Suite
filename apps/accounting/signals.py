import logging
import uuid

from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import (
    AccountCode, AccountPayable, AccountReceivable, AccountTransfer,
    BankAccount, CardTransaction, CashReceiptItem, CreditCard, Payment,
    PaymentDistribution, SalesSettlement, Voucher, VoucherLine,
)

logger = logging.getLogger(__name__)


def _get_account_code(code):
    """계정과목 코드로 AccountCode 조회 (없으면 None)"""
    try:
        return AccountCode.objects.get(code=code, is_active=True)
    except AccountCode.DoesNotExist:
        logger.warning('AccountCode %s not found — skipping voucher line', code)
        return None


def _generate_voucher_number():
    """전표번호 자동 생성"""
    from django.utils import timezone
    prefix = timezone.now().strftime('V%Y%m%d')
    suffix = uuid.uuid4().hex[:6].upper()
    return f'{prefix}-{suffix}'


def _validate_closing_period(target_date):
    """마감된 월이면 ValidationError 발생, 아니면 원본 반환"""
    from django.core.exceptions import ValidationError
    from .models import ClosingPeriod
    if ClosingPeriod.objects.filter(
        year=target_date.year,
        month=target_date.month,
        is_closed=True,
        is_active=True,
    ).exists():
        raise ValidationError(
            f'{target_date.year}년 {target_date.month:02d}월은 마감된 기간입니다. 전표를 생성할 수 없습니다.'
        )
    return target_date


def _get_expense_account(reference):
    """출금 reference에 따라 적절한 비용 계정과목 반환"""
    if reference and '수수료' in reference:
        acct = _get_account_code('521')  # 판매비
        if acct:
            return acct
    return _get_account_code('501')  # 매입원가 (기본)


@receiver(post_save, sender=Payment)
def payment_update_balance_and_voucher(sender, instance, created, **kwargs):
    """입출금 → 계좌잔액 원자적 갱신 + 자동전표 생성"""
    if not created:
        return
    if not instance.bank_account:
        return

    with transaction.atomic():
        # Distribution이 있는 Payment는 bank_account 잔액 갱신 스킵
        # (Distribution 시그널에서 각 분배 계좌별로 처리)
        if not instance.distributions.exists():
            if instance.payment_type == 'RECEIPT':
                BankAccount.objects.filter(pk=instance.bank_account_id).update(
                    balance=F('balance') + instance.amount,
                )
            elif instance.payment_type == 'DISBURSEMENT':
                BankAccount.objects.filter(pk=instance.bank_account_id).update(
                    balance=F('balance') - instance.amount,
                )

        # 자동전표 생성 — 복식부기 (차변+대변 2행 이상)
        acct = instance.bank_account
        acct.refresh_from_db()
        if acct.account_code and not instance.voucher:
            try:
                voucher_date = _validate_closing_period(instance.payment_date)
            except Exception:
                logger.warning(
                    'Payment %s — closing period blocked, skipping voucher',
                    instance.payment_number,
                )
                return
            voucher = Voucher.objects.create(
                voucher_number=_generate_voucher_number(),
                voucher_type='RECEIPT' if instance.payment_type == 'RECEIPT' else 'PAYMENT',
                voucher_date=voucher_date,
                description=f'자동전표: {instance.payment_number} ({instance.get_payment_type_display()})',
                approval_status='APPROVED',
                created_by=instance.created_by,
            )

            # 상대 계정과목 조회
            if instance.payment_type == 'RECEIPT':
                counter_acct = _get_account_code('401')  # 매출
            else:
                counter_acct = _get_expense_account(instance.reference)

            if not counter_acct:
                logger.error(
                    'Counter account not found for payment %s — voucher deleted to prevent unbalanced entry',
                    instance.payment_number,
                )
                voucher.delete()
                return

            if instance.payment_type == 'RECEIPT':
                # 차변: 보통예금(은행계좌), 대변: 매출(401) 또는 미수금 관련
                VoucherLine.objects.create(
                    voucher=voucher,
                    account=acct.account_code,
                    debit=instance.amount, credit=0,
                    description=f'{instance.partner} 입금 ({acct.name})',
                    created_by=instance.created_by,
                )
                VoucherLine.objects.create(
                    voucher=voucher,
                    account=counter_acct,
                    debit=0, credit=instance.amount,
                    description=f'{instance.partner} 매출 입금',
                    created_by=instance.created_by,
                )
            else:
                # 차변: 매입/비용(501), 대변: 보통예금(은행계좌)
                VoucherLine.objects.create(
                    voucher=voucher,
                    account=counter_acct,
                    debit=instance.amount, credit=0,
                    description=f'{instance.partner} 출금',
                    created_by=instance.created_by,
                )
                VoucherLine.objects.create(
                    voucher=voucher,
                    account=acct.account_code,
                    debit=0, credit=instance.amount,
                    description=f'{instance.partner} 출금 ({acct.name})',
                    created_by=instance.created_by,
                )

            Payment.objects.filter(pk=instance.pk).update(voucher=voucher)


@receiver(post_save, sender=AccountTransfer)
def transfer_update_balance_and_voucher(sender, instance, created, **kwargs):
    """계좌이체 → 양쪽 잔액 원자적 갱신 + 대체전표 생성"""
    if not created:
        return

    with transaction.atomic():
        BankAccount.objects.filter(pk=instance.from_account_id).update(
            balance=F('balance') - instance.amount,
        )
        BankAccount.objects.filter(pk=instance.to_account_id).update(
            balance=F('balance') + instance.amount,
        )

        # 양쪽 모두 계정과목이 있으면 대체전표 생성
        from_acct = instance.from_account
        to_acct = instance.to_account
        from_acct.refresh_from_db()
        to_acct.refresh_from_db()

        if from_acct.account_code and to_acct.account_code and not instance.voucher:
            try:
                voucher_date = _validate_closing_period(instance.transfer_date)
            except Exception:
                logger.warning(
                    'AccountTransfer %s — closing period blocked, skipping voucher',
                    instance.transfer_number,
                )
                return
            voucher = Voucher.objects.create(
                voucher_number=_generate_voucher_number(),
                voucher_type='TRANSFER',
                voucher_date=voucher_date,
                description=f'자동전표: 계좌이체 {from_acct.name} → {to_acct.name}',
                approval_status='APPROVED',
                created_by=instance.created_by,
            )
            VoucherLine.objects.create(
                voucher=voucher,
                account=to_acct.account_code,
                debit=instance.amount,
                credit=0,
                description=f'{to_acct.name} 입금',
                created_by=instance.created_by,
            )
            VoucherLine.objects.create(
                voucher=voucher,
                account=from_acct.account_code,
                debit=0,
                credit=instance.amount,
                description=f'{from_acct.name} 출금',
                created_by=instance.created_by,
            )
            AccountTransfer.objects.filter(pk=instance.pk).update(voucher=voucher)


@receiver(post_save, sender=PaymentDistribution)
def distribution_update_balance(sender, instance, created, **kwargs):
    """결제분배 → 대상계좌 잔액 갱신"""
    if not created:
        return

    payment = instance.payment
    with transaction.atomic():
        if payment.payment_type == 'RECEIPT':
            BankAccount.objects.filter(pk=instance.bank_account_id).update(
                balance=F('balance') + instance.amount,
            )
        elif payment.payment_type == 'DISBURSEMENT':
            BankAccount.objects.filter(pk=instance.bank_account_id).update(
                balance=F('balance') - instance.amount,
            )


@receiver(pre_save, sender=Payment)
def payment_soft_delete_restore_balance(sender, instance, **kwargs):
    """Payment soft delete (is_active True→False) 시 잔액 복원

    - AR/AP paid_amount 차감 + status 재계산
    - BankAccount 잔액 복원 (입금→차감, 출금→가산)
    - _skip_balance_restore 플래그로 중복 복원 방지
      (sales 시그널 등에서 수동 복원 후 플래그 설정 시 스킵)
    """
    if not instance.pk:
        return

    # _skip_balance_restore 플래그 확인
    if getattr(instance, '_skip_balance_restore', False):
        return

    try:
        old = Payment.objects.get(pk=instance.pk)
    except Payment.DoesNotExist:
        return

    # is_active True → False 전환만 처리
    if old.is_active and not instance.is_active:
        with transaction.atomic():
            # 1. AR paid_amount 복원 + status 재계산
            if old.receivable_id:
                AccountReceivable.objects.filter(pk=old.receivable_id).update(
                    paid_amount=F('paid_amount') - old.amount,
                )
                _recalculate_ar_status(old.receivable_id)

            # 2. AP paid_amount 복원 + status 재계산
            if old.payable_id:
                AccountPayable.objects.filter(pk=old.payable_id).update(
                    paid_amount=F('paid_amount') - old.amount,
                )
                _recalculate_ap_status(old.payable_id)

            # 3. BankAccount 잔액 복원
            if old.bank_account_id:
                if old.payment_type == 'RECEIPT':
                    # 입금 취소 → 잔액 차감
                    BankAccount.objects.filter(pk=old.bank_account_id).update(
                        balance=F('balance') - old.amount,
                    )
                elif old.payment_type == 'DISBURSEMENT':
                    # 출금 취소 → 잔액 가산
                    BankAccount.objects.filter(pk=old.bank_account_id).update(
                        balance=F('balance') + old.amount,
                    )

        logger.info(
            'Payment %s soft-deleted — restored AR/AP/bank balance (amount=%s)',
            old.payment_number, old.amount,
        )


def _recalculate_ar_status(ar_id):
    """AR의 paid_amount 기반 status 재계산"""
    ar = AccountReceivable.objects.get(pk=ar_id)
    if ar.paid_amount <= 0:
        new_status = 'PENDING'
    elif ar.paid_amount >= ar.amount:
        new_status = 'PAID'
    else:
        new_status = 'PARTIAL'
    if ar.status != new_status:
        AccountReceivable.objects.filter(pk=ar_id).update(status=new_status)


def _recalculate_ap_status(ap_id):
    """AP의 paid_amount 기반 status 재계산"""
    ap = AccountPayable.objects.get(pk=ap_id)
    if ap.paid_amount <= 0:
        new_status = 'PENDING'
    elif ap.paid_amount >= ap.amount:
        new_status = 'PAID'
    else:
        new_status = 'PARTIAL'
    if ap.status != new_status:
        AccountPayable.objects.filter(pk=ap_id).update(status=new_status)


# === 카드 거래 시그널 ===

# 카테고리별 비용 계정과목 코드 매핑
CARD_CATEGORY_ACCOUNT_MAP = {
    'PURCHASE': '501',       # 매입원가
    'TRAVEL': '524',         # 여비교통비
    'ENTERTAINMENT': '523',  # 접대비
    'SUPPLIES': '525',       # 사무용품비
    'FUEL': '526',           # 유류비
    'SUBSCRIPTION': '527',   # 정기구독비
    'OTHER': '529',          # 기타비용
}


def _get_card_expense_account(category):
    """카드 카테고리에 해당하는 비용 계정과목 반환"""
    code = CARD_CATEGORY_ACCOUNT_MAP.get(category, '529')
    acct = _get_account_code(code)
    if not acct and code != '529':
        acct = _get_account_code('529')  # fallback to 기타비용
    return acct


@receiver(post_save, sender=CardTransaction)
def card_transaction_voucher(sender, instance, created, **kwargs):
    """카드 거래 생성 → used_amount 원자적 증가 + 자동전표 생성"""
    if not created:
        return

    with transaction.atomic():
        # 1. CreditCard.used_amount F() 원자적 증가
        CreditCard.objects.filter(pk=instance.card_id).update(
            used_amount=F('used_amount') + instance.amount,
        )

        # 2. 자동전표 생성 (차변: 비용, 대변: 미지급금 253)
        expense_acct = _get_card_expense_account(instance.category)
        payable_acct = _get_account_code('253')  # 미지급금

        if not expense_acct or not payable_acct:
            logger.warning(
                'CardTransaction %s — missing account codes, skipping voucher',
                instance.pk,
            )
            return

        try:
            voucher_date = _validate_closing_period(instance.transaction_date)
        except Exception:
            logger.warning(
                'CardTransaction %s — closing period blocked, skipping voucher',
                instance.pk,
            )
            return
        voucher = Voucher.objects.create(
            voucher_number=_generate_voucher_number(),
            voucher_type='PAYMENT',
            voucher_date=voucher_date,
            description=f'카드전표: {instance.card.name} {instance.merchant_name}',
            approval_status='APPROVED',
            created_by=instance.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=expense_acct,
            debit=instance.amount, credit=0,
            description=f'{instance.merchant_name} 카드결제',
            created_by=instance.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=payable_acct,
            debit=0, credit=instance.amount,
            description=f'{instance.card.name} 미지급금',
            created_by=instance.created_by,
        )

        # 3. voucher FK 연결
        CardTransaction.objects.filter(pk=instance.pk).update(voucher=voucher)


@receiver(pre_save, sender=CardTransaction)
def card_transaction_cancel(sender, instance, **kwargs):
    """카드 거래 취소 (is_cancelled False→True) → used_amount 감소 + 역전표"""
    if not instance.pk:
        return

    try:
        old = CardTransaction.objects.get(pk=instance.pk)
    except CardTransaction.DoesNotExist:
        return

    # is_cancelled False → True 전환만 처리
    if old.is_cancelled or not instance.is_cancelled:
        return

    with transaction.atomic():
        # 1. CreditCard.used_amount F() 원자적 감소
        CreditCard.objects.filter(pk=instance.card_id).update(
            used_amount=F('used_amount') - old.amount,
        )

        # 2. 역전표 생성 (차변/대변 반대)
        expense_acct = _get_card_expense_account(old.category)
        payable_acct = _get_account_code('253')

        if not expense_acct or not payable_acct:
            logger.warning(
                'CardTransaction %s cancel — missing account codes, skipping reverse voucher',
                instance.pk,
            )
            return

        cancel_date = instance.cancelled_date or instance.transaction_date
        try:
            voucher_date = _validate_closing_period(cancel_date)
        except Exception:
            logger.warning(
                'CardTransaction %s cancel — closing period blocked, skipping reverse voucher',
                instance.pk,
            )
            return
        voucher = Voucher.objects.create(
            voucher_number=_generate_voucher_number(),
            voucher_type='PAYMENT',
            voucher_date=voucher_date,
            description=f'카드취소전표: {old.card.name} {old.merchant_name}',
            approval_status='APPROVED',
            created_by=instance.created_by,
        )
        # 역전표: 차변=미지급금, 대변=비용
        VoucherLine.objects.create(
            voucher=voucher,
            account=payable_acct,
            debit=old.amount, credit=0,
            description=f'{old.merchant_name} 카드결제 취소',
            created_by=instance.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=expense_acct,
            debit=0, credit=old.amount,
            description=f'{old.card.name} 미지급금 취소',
            created_by=instance.created_by,
        )


# === AR/AP 자동전표 시그널 ===

@receiver(post_save, sender=AccountReceivable)
def ar_auto_voucher_on_create(sender, instance, created, **kwargs):
    """AR 생성 시 자동전표: 차변 120(미수금) / 대변 401(매출)"""
    if not created or not instance.is_active:
        return

    with transaction.atomic():
        acct_120 = _get_account_code('120')  # 미수금
        acct_401 = _get_account_code('401')  # 매출

        if not acct_120 or not acct_401:
            logger.warning(
                'AR %s — missing account codes (120 or 401), skipping auto voucher',
                instance.pk,
            )
            return

        try:
            voucher_date = _validate_closing_period(instance.due_date)
        except Exception:
            logger.warning(
                'AR %s — closing period blocked, skipping auto voucher',
                instance.pk,
            )
            return

        voucher = Voucher.objects.create(
            voucher_number=_generate_voucher_number(),
            voucher_type='RECEIPT',
            voucher_date=voucher_date,
            description=f'자동전표: 미수금 발생 ({instance.partner})',
            approval_status='APPROVED',
            created_by=instance.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=acct_120,
            debit=instance.amount, credit=0,
            description=f'{instance.partner} 미수금',
            created_by=instance.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=acct_401,
            debit=0, credit=instance.amount,
            description=f'{instance.partner} 매출',
            created_by=instance.created_by,
        )


@receiver(post_save, sender=VoucherLine)
def check_budget_overspend_on_voucher_line(sender, instance, created, **kwargs):
    """전표항목 저장 시 해당 계정의 예산 초과 여부 체크

    VoucherLine의 account가 Budget에 등록된 계정이면,
    해당 월 실적이 예산을 초과할 때 경고 로깅.
    """
    if not created or not instance.is_active:
        return
    if not instance.voucher or not instance.account:
        return

    from .models import Budget
    from django.utils.dateparse import parse_date

    voucher_date = instance.voucher.voucher_date
    if isinstance(voucher_date, str):
        voucher_date = parse_date(voucher_date)
    if not voucher_date:
        return
    year = voucher_date.year
    month = voucher_date.month

    budgets = Budget.objects.filter(
        year=year, month=month, is_active=True,
        account=instance.account,
    ).select_related('account')

    for budget in budgets:
        actual = budget.actual_amount
        if actual > budget.budget_amount:
            overspend = actual - budget.budget_amount
            logger.warning(
                'Budget overspend: [%s] %s — %d년 %02d월 예산 %s원 초과 (예산: %s, 실적: %s)',
                budget.account.code, budget.account.name,
                year, month, overspend,
                budget.budget_amount, actual,
            )


@receiver(post_save, sender=AccountPayable)
def ap_auto_voucher_on_create(sender, instance, created, **kwargs):
    """AP 생성 시 자동전표: 차변 501(매입원가) / 대변 253(미지급금)"""
    if not created or not instance.is_active:
        return

    with transaction.atomic():
        acct_501 = _get_account_code('501')  # 매입원가
        acct_253 = _get_account_code('253')  # 미지급금

        if not acct_501 or not acct_253:
            logger.warning(
                'AP %s — missing account codes (501 or 253), skipping auto voucher',
                instance.pk,
            )
            return

        try:
            voucher_date = _validate_closing_period(instance.due_date)
        except Exception:
            logger.warning(
                'AP %s — closing period blocked, skipping auto voucher',
                instance.pk,
            )
            return

        voucher = Voucher.objects.create(
            voucher_number=_generate_voucher_number(),
            voucher_type='PAYMENT',
            voucher_date=voucher_date,
            description=f'자동전표: 미지급금 발생 ({instance.partner})',
            approval_status='APPROVED',
            created_by=instance.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=acct_501,
            debit=instance.amount, credit=0,
            description=f'{instance.partner} 매입원가',
            created_by=instance.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=acct_253,
            debit=0, credit=instance.amount,
            description=f'{instance.partner} 미지급금',
            created_by=instance.created_by,
        )


# === 매출 정산 수수료/배송비 자동전표 ===

@receiver(post_save, sender=SalesSettlement)
def auto_voucher_on_settlement(sender, instance, **kwargs):
    """SalesSettlement 저장 시 배송비/플랫폼수수료 자동전표 생성

    - commission_voucher가 이미 있으면 스킵 (중복 방지)
    - total_shipping 또는 total_platform_commission이 0보다 클 때만 전표 생성
    - 차변: 판매수수료(521) + 운반비(524), 대변: 미지급금(253)
    """
    if instance.commission_voucher_id:
        return

    shipping = instance.total_shipping or 0
    commission = instance.total_platform_commission or 0

    if shipping <= 0 and commission <= 0:
        return

    with transaction.atomic():
        acct_521 = _get_account_code('521')  # 판매수수료
        acct_524 = _get_account_code('524')  # 운반비(배송비)
        acct_253 = _get_account_code('253')  # 미지급금

        if not acct_253:
            logger.warning(
                'SalesSettlement %s — missing account 253 (미지급금), skipping voucher',
                instance.settlement_number,
            )
            return

        if commission > 0 and not acct_521:
            logger.warning(
                'SalesSettlement %s — missing account 521 (판매수수료), skipping voucher',
                instance.settlement_number,
            )
            return

        if shipping > 0 and not acct_524:
            logger.warning(
                'SalesSettlement %s — missing account 524 (운반비), skipping voucher',
                instance.settlement_number,
            )
            return

        try:
            voucher_date = _validate_closing_period(instance.settlement_date)
        except Exception:
            logger.warning(
                'SalesSettlement %s — closing period blocked, skipping voucher',
                instance.settlement_number,
            )
            return

        total_amount = commission + shipping

        voucher = Voucher.objects.create(
            voucher_number=_generate_voucher_number(),
            voucher_type='TRANSFER',
            voucher_date=voucher_date,
            description=f'자동전표: 정산 수수료/배송비 ({instance.settlement_number})',
            approval_status='APPROVED',
            created_by=instance.created_by,
        )

        if commission > 0:
            VoucherLine.objects.create(
                voucher=voucher,
                account=acct_521,
                debit=commission, credit=0,
                description=f'플랫폼수수료 ({instance.settlement_number})',
                created_by=instance.created_by,
            )

        if shipping > 0:
            VoucherLine.objects.create(
                voucher=voucher,
                account=acct_524,
                debit=shipping, credit=0,
                description=f'배송비 ({instance.settlement_number})',
                created_by=instance.created_by,
            )

        VoucherLine.objects.create(
            voucher=voucher,
            account=acct_253,
            debit=0, credit=total_amount,
            description=f'수수료/배송비 미지급금 ({instance.settlement_number})',
            created_by=instance.created_by,
        )

        SalesSettlement.objects.filter(pk=instance.pk).update(
            commission_voucher=voucher,
        )


@receiver(post_delete, sender=CashReceiptItem)
def recalc_cash_receipt_on_item_delete(sender, instance, **kwargs):
    """CashReceiptItem 삭제 시 부모 CashReceipt 합계 재계산"""
    if instance.receipt_id:
        try:
            receipt = instance.receipt
        except sender._meta.get_field('receipt').related_model.DoesNotExist:
            return
        receipt.recalculate_totals()
