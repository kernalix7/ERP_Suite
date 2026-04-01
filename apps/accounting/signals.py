import logging
import uuid

from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import (
    AccountCode, AccountTransfer, BankAccount, Payment, PaymentDistribution,
    Voucher, VoucherLine,
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


def _get_closing_safe_date(target_date):
    """마감된 월이면 다음 월 1일자 반환, 아니면 원본 반환"""
    from .models import ClosingPeriod
    if ClosingPeriod.objects.filter(
        year=target_date.year,
        month=target_date.month,
        is_closed=True,
        is_active=True,
    ).exists():
        if target_date.month == 12:
            from datetime import date
            return date(target_date.year + 1, 1, 1)
        else:
            from datetime import date
            return date(target_date.year, target_date.month + 1, 1)
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
            voucher_date = _get_closing_safe_date(instance.payment_date)
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
            voucher_date = _get_closing_safe_date(instance.transfer_date)
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
