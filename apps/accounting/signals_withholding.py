"""원천징수(WithholdingTax) 자동전표 시그널.

지급 발생 시 복식부기 전표 자동 생성:

    (차) 지급수수료/급여   gross_amount
        (대) 예수금(원천세) tax_amount
        (대) 현금성자산      net_amount

- 마감된 월의 경우 ClosingPeriod 검증에 따라 생성 스킵 + 관리자 알림
- 자동전표 FK는 update로 기록(시그널 재귀 방지)
- WithholdingTax 신규 생성 시에만 동작 (update에서는 skip)
"""
import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AccountCode, Voucher, VoucherLine, WithholdingTax
from .signals import _generate_voucher_number

logger = logging.getLogger(__name__)


# 계정과목 코드 (기본 K-GAAP)
# - 지급수수료(531): 사업·기타소득 대응
# - 예수금(213): 원천세 납부 전 단기부채
# - 보통예금(102): 실지급 상대 계정
ACCT_EXPENSE = '531'
ACCT_WITHHOLDING_LIABILITY = '213'
ACCT_CASH = '102'


def _get_code(code):
    try:
        return AccountCode.objects.get(code=code, is_active=True)
    except AccountCode.DoesNotExist:
        logger.warning(
            'WithholdingTax signal: AccountCode %s not found — skip auto-voucher',
            code,
        )
        return None


@receiver(post_save, sender=WithholdingTax)
def withholding_create_voucher(sender, instance, created, **kwargs):
    """원천징수 등록 → 복식부기 자동전표 생성."""
    # 재귀 방지: voucher 필드 업데이트에 의한 save는 무시
    update_fields = kwargs.get('update_fields') or set()
    if update_fields and set(update_fields) <= {'voucher', 'updated_at'}:
        return

    if not created:
        return
    if instance.voucher_id:
        return
    if instance.gross_amount <= 0:
        return

    expense_acct = _get_code(ACCT_EXPENSE)
    liability_acct = _get_code(ACCT_WITHHOLDING_LIABILITY)
    cash_acct = _get_code(ACCT_CASH)
    if not (expense_acct and liability_acct and cash_acct):
        return

    # 마감월 검증 (silent skip + 알림)
    from apps.accounting.utils import validate_closing_period
    if not validate_closing_period(
        instance.payment_date,
        raise_exception=False,
        notify_user=instance.created_by,
        context=f'원천징수 {instance.payee_name} ({instance.payment_date}) 자동전표',
    ):
        return

    with transaction.atomic():
        voucher = Voucher.objects.create(
            voucher_number=_generate_voucher_number(),
            voucher_type='PAYMENT',
            voucher_date=instance.payment_date,
            description=f'원천징수: {instance.payee_name} ({instance.get_tax_type_display()})',
            approval_status='APPROVED',
            created_by=instance.created_by,
        )

        # 차변: 지급수수료 전액 (총지급액)
        VoucherLine.objects.create(
            voucher=voucher,
            account=expense_acct,
            debit=instance.gross_amount,
            credit=0,
            description=f'{instance.payee_name} 지급수수료',
            created_by=instance.created_by,
        )
        # 대변1: 예수금(원천세)
        VoucherLine.objects.create(
            voucher=voucher,
            account=liability_acct,
            debit=0,
            credit=instance.tax_amount,
            description=f'{instance.payee_name} 원천징수({instance.tax_rate}%)',
            created_by=instance.created_by,
        )
        # 대변2: 현금/보통예금 (실지급액)
        VoucherLine.objects.create(
            voucher=voucher,
            account=cash_acct,
            debit=0,
            credit=instance.net_amount,
            description=f'{instance.payee_name} 실지급',
            created_by=instance.created_by,
        )

        # 재귀 방지: update()로 저장 (save 시그널 재호출 안 함)
        WithholdingTax.objects.filter(pk=instance.pk).update(voucher=voucher)
