import logging

from datetime import date

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ExpenseClaim

logger = logging.getLogger(__name__)

# 경비 카테고리 코드 → 계정과목 코드 매핑
EXPENSE_ACCOUNT_MAP = {
    'TRANS': '524',      # 교통비 → 여비교통비
    'BIZ-T': '524',      # 출장비 → 여비교통비
    'MEAL': '522',       # 식비 → 복리후생비
    'SUPPLIES': '525',   # 사무용품비
    'ENTERTAINMENT': '523',  # 접대비
    'FUEL': '526',       # 유류비
    'COMMUNICATION': '528',  # 통신비
    'SUBSCRIPTION': '527',   # 정기구독비
}
DEFAULT_EXPENSE_ACCOUNT_CODE = '529'  # 기타비용 (매핑 없을 때)
CASH_ACCOUNT_CODE = '101'  # 현금 (대변 계정)


def _get_account_safe(code):
    """계정과목 코드로 조회. 없으면 None + 경고 로깅."""
    from apps.accounting.models import AccountCode
    try:
        return AccountCode.objects.get(code=code, is_active=True)
    except AccountCode.DoesNotExist:
        logger.warning('AccountCode %s not found', code)
        return None


@receiver(post_save, sender=ExpenseClaim)
def expense_claim_approved_voucher(sender, instance, **kwargs):
    """경비 청구 승인 시 회계 전표 자동 생성"""
    if instance.status != ExpenseClaim.Status.APPROVED:
        return
    if not instance.is_active:
        return
    if not instance.total_amount or instance.total_amount <= 0:
        return

    from apps.accounting.models import Voucher, VoucherLine

    # 중복 방지: claim FK로 검증 (문자열 비교 대신 구조적 검증)
    existing = Voucher.objects.filter(
        is_active=True,
        description__contains=instance.claim_number,
    ).exists()
    if existing:
        return

    # voucher_date null 방지: approved_date → submitted_date → today 순
    voucher_date = instance.approved_date or instance.submitted_date or date.today()

    # 대변 계정(현금/보통예금) 조회
    cash_account = _get_account_safe(CASH_ACCOUNT_CODE)
    if not cash_account:
        logger.error(
            'ExpenseClaim %s — 현금 계정(%s) 없음, 전표 생성 스킵',
            instance.claim_number, CASH_ACCOUNT_CODE,
        )
        return

    with transaction.atomic():
        voucher = Voucher.objects.create(
            voucher_type=Voucher.VoucherType.PAYMENT,
            voucher_date=voucher_date,
            description=f'경비청구 승인: {instance.claim_number} ({instance.title})',
            created_by=instance.approved_by,
        )

        # 경비 항목별 카테고리 → 계정과목 매핑으로 차변 생성
        items = instance.items.filter(is_active=True).select_related('category')
        total_debited = 0

        for item in items:
            cat_code = item.category.code if item.category else None
            acct_code = EXPENSE_ACCOUNT_MAP.get(cat_code, DEFAULT_EXPENSE_ACCOUNT_CODE)
            expense_account = _get_account_safe(acct_code)
            if not expense_account:
                expense_account = _get_account_safe(DEFAULT_EXPENSE_ACCOUNT_CODE)
            if not expense_account:
                logger.warning(
                    'ExpenseClaim %s item %s — 비용 계정 없음, 해당 항목 스킵',
                    instance.claim_number, item.pk,
                )
                continue

            VoucherLine.objects.create(
                voucher=voucher,
                account=expense_account,
                debit=item.amount,
                credit=0,
                description=f'경비: {item.description}',
                created_by=instance.approved_by,
            )
            total_debited += item.amount

        # 항목이 없으면 총액으로 기타비용 차변 생성 (fallback)
        if total_debited == 0:
            fallback_account = _get_account_safe(DEFAULT_EXPENSE_ACCOUNT_CODE)
            if fallback_account:
                VoucherLine.objects.create(
                    voucher=voucher,
                    account=fallback_account,
                    debit=instance.total_amount,
                    credit=0,
                    description=f'경비: {instance.title}',
                    created_by=instance.approved_by,
                )
                total_debited = instance.total_amount

        if total_debited > 0:
            # 대변: 현금/보통예금 (차변 합계와 일치)
            VoucherLine.objects.create(
                voucher=voucher,
                account=cash_account,
                debit=0,
                credit=total_debited,
                description=f'경비지급: {instance.claim_number}',
                created_by=instance.approved_by,
            )
        else:
            # 차변이 0이면 불완전 전표 — soft delete
            logger.error(
                'ExpenseClaim %s — 비용 계정을 찾을 수 없어 전표 취소',
                instance.claim_number,
            )
            voucher.is_active = False
            voucher.save(update_fields=['is_active', 'updated_at'])
