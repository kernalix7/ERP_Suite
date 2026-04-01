import logging
import uuid

from django.db import transaction
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from .models import Distribution

logger = logging.getLogger(__name__)


def _get_account_code(code):
    """계정과목 코드로 AccountCode 조회 (없으면 None)"""
    from apps.accounting.models import AccountCode
    try:
        return AccountCode.objects.get(code=code, is_active=True)
    except AccountCode.DoesNotExist:
        logger.warning('AccountCode %s not found — skipping voucher creation', code)
        return None


def _generate_voucher_number():
    """전표번호 자동 생성"""
    from django.utils import timezone
    prefix = timezone.now().strftime('V%Y%m%d')
    suffix = uuid.uuid4().hex[:6].upper()
    return f'{prefix}-{suffix}'


def _voucher_ref(instance):
    """배당 전표 description에 사용할 고유 참조 문자열"""
    return f'배당#{instance.pk}'


def _create_pending_voucher(instance):
    """배당 확정(PENDING) → 배당금 지급 의무 전표 생성"""
    from apps.accounting.models import Voucher, VoucherLine

    retained_earnings = _get_account_code('330')  # 이익잉여금
    dividend_payable = _get_account_code('270')  # 미지급배당금

    if not retained_earnings or not dividend_payable:
        logger.error(
            'AccountCode 330 or 270 not found — '
            'skipping distribution voucher for Distribution %s',
            instance.pk,
        )
        return

    # 중복 방지: 이미 동일 배당에 대한 TRANSFER 전표가 있으면 스킵
    ref = _voucher_ref(instance)
    if Voucher.objects.filter(
        description__contains=ref,
        voucher_type='TRANSFER',
        is_active=True,
    ).exists():
        logger.info(
            'Distribution %s PENDING voucher already exists — skipping',
            instance.pk,
        )
        return

    with transaction.atomic():
        desc = (
            f'자동전표: {instance.investor.name} '
            f'{instance.get_distribution_type_display()} '
            f'({instance.fiscal_year}) [{ref}]'
        )
        voucher = Voucher.objects.create(
            voucher_number=_generate_voucher_number(),
            voucher_type='TRANSFER',
            voucher_date=instance.scheduled_date,
            description=desc,
            approval_status='APPROVED',
            created_by=instance.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=retained_earnings,
            debit=instance.amount,
            credit=0,
            description=f'{instance.investor.name} 배당 결의',
            created_by=instance.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=dividend_payable,
            debit=0,
            credit=instance.amount,
            description=f'{instance.investor.name} 미지급배당금',
            created_by=instance.created_by,
        )
        logger.info(
            'Distribution %s (PENDING) → voucher %s created',
            instance.pk, voucher.voucher_number,
        )


def _create_paid_voucher(instance):
    """배당 지급 완료(PAID) → 지급 전표 생성"""
    from apps.accounting.models import Voucher, VoucherLine

    dividend_payable = _get_account_code('270')  # 미지급배당금
    cash_account = _get_account_code('101')  # 보통예금

    if not dividend_payable or not cash_account:
        logger.error(
            'AccountCode 270 or 101 not found — '
            'skipping payment voucher for Distribution %s',
            instance.pk,
        )
        return

    # 중복 방지: 이미 동일 배당에 대한 PAYMENT 전표가 있으면 스킵
    ref = _voucher_ref(instance)
    if Voucher.objects.filter(
        description__contains=ref,
        voucher_type='PAYMENT',
        is_active=True,
    ).exists():
        logger.info(
            'Distribution %s PAID voucher already exists — skipping',
            instance.pk,
        )
        return

    with transaction.atomic():
        desc = (
            f'자동전표: {instance.investor.name} '
            f'{instance.get_distribution_type_display()} 지급완료 '
            f'({instance.fiscal_year}) [{ref}]'
        )
        voucher = Voucher.objects.create(
            voucher_number=_generate_voucher_number(),
            voucher_type='PAYMENT',
            voucher_date=instance.paid_date or instance.scheduled_date,
            description=desc,
            approval_status='APPROVED',
            created_by=instance.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=dividend_payable,
            debit=instance.amount,
            credit=0,
            description=f'{instance.investor.name} 미지급배당금 소멸',
            created_by=instance.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=cash_account,
            debit=0,
            credit=instance.amount,
            description=f'{instance.investor.name} 배당금 지급',
            created_by=instance.created_by,
        )
        logger.info(
            'Distribution %s (PAID) → voucher %s created',
            instance.pk, voucher.voucher_number,
        )


@receiver(pre_save, sender=Distribution)
def distribution_detect_status_change(sender, instance, **kwargs):
    """상태 변경 감지 — post_save에서 전표 생성 여부를 판단하기 위해 이전 상태 저장"""
    if not instance.pk:
        instance._previous_status = None
        return
    try:
        old = Distribution.objects.get(pk=instance.pk)
        instance._previous_status = old.status
    except Distribution.DoesNotExist:
        instance._previous_status = None


@receiver(post_save, sender=Distribution)
def distribution_create_voucher(sender, instance, created, **kwargs):
    """배당/분배 상태 전환 시 자동 전표 생성

    배당금 지급 의무 발생 시 (→ PENDING):
    - 차변: 이익잉여금(330) — 이익배당
    - 대변: 미지급배당금(270) — 지급 의무

    배당 지급 완료 시 (→ PAID):
    - 차변: 미지급배당금(270) — 의무 소멸
    - 대변: 보통예금(101) — 현금 유출
    """
    previous = getattr(instance, '_previous_status', None)

    if created and instance.status == Distribution.PaymentStatus.PENDING:
        # 새로 생성된 Distribution이 이미 PENDING인 경우
        _create_pending_voucher(instance)

    elif not created and instance.status == Distribution.PaymentStatus.PENDING:
        # SCHEDULED → PENDING 전환 시에만 (이미 PENDING이면 스킵)
        if previous != Distribution.PaymentStatus.PENDING:
            _create_pending_voucher(instance)

    elif not created and instance.status == Distribution.PaymentStatus.PAID:
        # PENDING → PAID 전환 시에만 (이미 PAID이면 스킵)
        if previous != Distribution.PaymentStatus.PAID:
            _create_paid_voucher(instance)
