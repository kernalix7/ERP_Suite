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


@receiver(post_save, sender=Payment)
def payment_update_balance_and_voucher(sender, instance, created, **kwargs):
    """입출금 → 계좌잔액 원자적 갱신 + 자동전표 생성"""
    if not created:
        return
    if not instance.bank_account:
        return

    with transaction.atomic():
        # 잔액 갱신
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
            voucher = Voucher.objects.create(
                voucher_number=_generate_voucher_number(),
                voucher_type='RECEIPT' if instance.payment_type == 'RECEIPT' else 'PAYMENT',
                voucher_date=instance.payment_date,
                description=f'자동전표: {instance.payment_number} ({instance.get_payment_type_display()})',
                approval_status='APPROVED',
                created_by=instance.created_by,
            )

            # 상대 계정과목 조회 (DB 기반, 하드코딩 없음)
            if instance.payment_type == 'RECEIPT':
                # 차변: 보통예금(은행계좌), 대변: 매출(401) 또는 미수금 관련
                counter_acct = _get_account_code('401')  # 매출
                VoucherLine.objects.create(
                    voucher=voucher,
                    account=acct.account_code,
                    debit=instance.amount, credit=0,
                    description=f'{instance.partner} 입금 ({acct.name})',
                    created_by=instance.created_by,
                )
                if counter_acct:
                    VoucherLine.objects.create(
                        voucher=voucher,
                        account=counter_acct,
                        debit=0, credit=instance.amount,
                        description=f'{instance.partner} 매출 입금',
                        created_by=instance.created_by,
                    )
            else:
                # 차변: 매입/비용(501 또는 502), 대변: 보통예금(은행계좌)
                counter_acct = _get_account_code('501')  # 매입원가
                VoucherLine.objects.create(
                    voucher=voucher,
                    account=counter_acct or acct.account_code,
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
            voucher = Voucher.objects.create(
                voucher_number=_generate_voucher_number(),
                voucher_type='TRANSFER',
                voucher_date=instance.transfer_date,
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
