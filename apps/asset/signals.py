import logging
import uuid

from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import DepreciationRecord, FixedAsset

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


@receiver(post_save, sender=DepreciationRecord)
def depreciation_update_asset_and_voucher(sender, instance, created, **kwargs):
    """감가상각 기록 → FixedAsset 원자적 갱신 + 자동전표 생성

    1. FixedAsset.accumulated_depreciation F() 증가
    2. FixedAsset.book_value F() 감소
    3. 감가상각비(차변) / 감가상각누계액(대변) 전표 자동 생성
    """
    if not created:
        return

    with transaction.atomic():
        # 1) FixedAsset 원자적 갱신
        FixedAsset.objects.filter(pk=instance.asset_id).update(
            accumulated_depreciation=F('accumulated_depreciation') + instance.depreciation_amount,
            book_value=F('book_value') - instance.depreciation_amount,
        )

        # 2) 자동전표 생성 (복식부기)
        #    차변: 감가상각비(820), 대변: 감가상각누계액(159)
        depreciation_expense = _get_account_code('820')  # 감가상각비
        accumulated_depr = _get_account_code('159')  # 감가상각누계액

        if not depreciation_expense or not accumulated_depr:
            logger.error(
                'AccountCode 820 or 159 not found — '
                'skipping voucher for DepreciationRecord %s',
                instance.pk,
            )
            return

        from apps.accounting.models import Voucher, VoucherLine

        voucher = Voucher.objects.create(
            voucher_number=_generate_voucher_number(),
            voucher_type='TRANSFER',
            voucher_date=f'{instance.year}-{instance.month:02d}-01',
            description=f'자동전표: {instance.asset.name} 감가상각 ({instance.year}/{instance.month})',
            approval_status='APPROVED',
            created_by=instance.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=depreciation_expense,
            debit=instance.depreciation_amount,
            credit=0,
            description=f'{instance.asset.name} 감가상각비',
            created_by=instance.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=accumulated_depr,
            debit=0,
            credit=instance.depreciation_amount,
            description=f'{instance.asset.name} 감가상각누계액',
            created_by=instance.created_by,
        )
        logger.info(
            'DepreciationRecord %s → FixedAsset %s updated, voucher %s created',
            instance.pk, instance.asset_id, voucher.voucher_number,
        )


@receiver(pre_save, sender=FixedAsset)
def asset_disposal_gain_loss(sender, instance, **kwargs):
    """자산 처분 시 처분손익 자동 전표 생성

    상태가 DISPOSED/SCRAPPED로 변경될 때:
    - 처분금액 > 장부가액 → 유형자산처분이익
    - 처분금액 < 장부가액 → 유형자산처분손실
    """
    if not instance.pk:
        return

    try:
        old = FixedAsset.objects.get(pk=instance.pk)
    except FixedAsset.DoesNotExist:
        return

    # 상태가 ACTIVE → DISPOSED/SCRAPPED로 변경될 때만
    if old.status == FixedAsset.Status.ACTIVE and instance.status in (
        FixedAsset.Status.DISPOSED,
        FixedAsset.Status.SCRAPPED,
    ):
        book_value = old.book_value
        disposal_amount = instance.disposal_amount or 0

        # 차변: 감가상각누계액(159) + 처분금액(현금/미수금)
        # 대변: 자산 취득원가
        # 차이: 처분이익 또는 처분손실
        accumulated_depr = _get_account_code('159')  # 감가상각누계액
        asset_account = _get_account_code('150')  # 유형자산 (비품 등)
        cash_account = _get_account_code('101')  # 현금/보통예금

        if not all([accumulated_depr, asset_account, cash_account]):
            logger.error(
                'AccountCode 159/150/101 not found — '
                'skipping disposal voucher for asset %s',
                instance.asset_number,
            )
            return

        from apps.accounting.models import Voucher, VoucherLine

        gain_loss = disposal_amount - book_value
        disposal_date = instance.disposal_date or instance.updated_at

        with transaction.atomic():
            voucher = Voucher.objects.create(
                voucher_number=_generate_voucher_number(),
                voucher_type='TRANSFER',
                voucher_date=disposal_date,
                description=f'자동전표: {instance.name} 처분 ({instance.get_status_display()})',
                approval_status='APPROVED',
                created_by=instance.created_by,
            )

            # 차변: 감가상각누계액 (기존 누적액 제거)
            VoucherLine.objects.create(
                voucher=voucher,
                account=accumulated_depr,
                debit=old.accumulated_depreciation,
                credit=0,
                description=f'{instance.name} 감가상각누계액 제거',
                created_by=instance.created_by,
            )

            # 차변: 현금/미수금 (처분대금)
            if disposal_amount > 0:
                VoucherLine.objects.create(
                    voucher=voucher,
                    account=cash_account,
                    debit=disposal_amount,
                    credit=0,
                    description=f'{instance.name} 처분대금',
                    created_by=instance.created_by,
                )

            # 대변: 유형자산 (취득원가 제거)
            VoucherLine.objects.create(
                voucher=voucher,
                account=asset_account,
                debit=0,
                credit=old.acquisition_cost,
                description=f'{instance.name} 취득원가 제거',
                created_by=instance.created_by,
            )

            # 처분손익
            if gain_loss > 0:
                gain_account = _get_account_code('901')  # 유형자산처분이익
                if gain_account:
                    VoucherLine.objects.create(
                        voucher=voucher,
                        account=gain_account,
                        debit=0,
                        credit=gain_loss,
                        description=f'{instance.name} 처분이익',
                        created_by=instance.created_by,
                    )
            elif gain_loss < 0:
                loss_account = _get_account_code('951')  # 유형자산처분손실
                if loss_account:
                    VoucherLine.objects.create(
                        voucher=voucher,
                        account=loss_account,
                        debit=abs(gain_loss),
                        credit=0,
                        description=f'{instance.name} 처분손실',
                        created_by=instance.created_by,
                    )

            logger.info(
                'FixedAsset %s disposed — voucher %s created (gain/loss: %s)',
                instance.asset_number, voucher.voucher_number, gain_loss,
            )
