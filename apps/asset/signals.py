import logging
import uuid

from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import AssetTransfer, Certification, DepreciationRecord, FixedAsset

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
        from apps.accounting.utils import validate_closing_period
        from datetime import date as _date

        # 마감기간 검증 — 감가상각 대상 월
        depr_date = _date(instance.year, instance.month, 1)
        if not validate_closing_period(
            depr_date,
            raise_exception=False,
            notify_user=instance.created_by,
            context=f'DepreciationRecord {instance.asset.name} 감가상각 전표',
        ):
            return

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
        from apps.accounting.utils import validate_closing_period

        gain_loss = disposal_amount - book_value
        disposal_date = instance.disposal_date or instance.updated_at

        # 마감기간 검증 — 처분일 기준 (date 추출)
        _target = disposal_date.date() if hasattr(disposal_date, 'date') else disposal_date
        if not validate_closing_period(
            _target,
            raise_exception=False,
            notify_user=instance.created_by,
            context=f'FixedAsset {instance.asset_number} 처분 전표',
        ):
            return

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


@receiver(post_save, sender=AssetTransfer)
def apply_asset_transfer(sender, instance, created, **kwargs):
    """자산 이관 → FixedAsset 부서/관리자/위치 자동 갱신"""
    if not created:
        return
    FixedAsset.objects.filter(pk=instance.asset_id).update(
        department=instance.to_department,
        responsible_person=instance.to_person,
        location=instance.to_location,
    )


@receiver(post_save, sender=Certification)
def capitalize_certification_cost(sender, instance, created, **kwargs):
    """인증 자본화 → 무형자산(FixedAsset INTANGIBLE) 자동 생성 + 전표

    is_capitalized=True이고 asset이 없으면:
    - FixedAsset(asset_type=INTANGIBLE) 자동 생성
    - useful_life_years = (expiry_date - issue_date).days // 365 (최소 1년)
    - depreciation_method = STRAIGHT
    - acquisition_cost = cost
    - 생성된 asset을 certification.asset에 연결
    - 차변: 무형자산(160), 대변: 현금(101) 전표 자동 생성
    """
    if not created:
        return
    if not instance.is_capitalized or instance.cost <= 0:
        return
    if instance.asset_id:
        return

    with transaction.atomic():
        from apps.core.utils import generate_document_number

        # 내용연수 계산
        if instance.expiry_date and instance.issue_date:
            useful_life = max((instance.expiry_date - instance.issue_date).days // 365, 1)
        else:
            useful_life = 1

        # 무형자산용 카테고리 조회/생성
        from .models import AssetCategory
        intangible_cat, _ = AssetCategory.objects.get_or_create(
            code='INTANGIBLE',
            defaults={
                'name': '무형자산',
                'useful_life_years': useful_life,
                'depreciation_method': 'STRAIGHT',
            },
        )

        asset_number = generate_document_number(FixedAsset, 'asset_number', 'FA')
        asset = FixedAsset.objects.create(
            asset_number=asset_number,
            name=f'{instance.cert_name} (인증 자본화)',
            category=intangible_cat,
            asset_type=FixedAsset.AssetType.INTANGIBLE,
            acquisition_date=instance.issue_date,
            acquisition_cost=instance.cost,
            residual_value=0,
            useful_life_years=useful_life,
            depreciation_method='STRAIGHT',
            created_by=instance.created_by,
        )

        # certification.asset에 연결
        Certification.objects.filter(pk=instance.pk).update(asset=asset)

        # 전표 생성: 차변 무형자산(160), 대변 현금(101)
        intangible_account = _get_account_code('160')
        cash_account = _get_account_code('101')

        if not intangible_account or not cash_account:
            logger.warning(
                'AccountCode 160/101 not found — '
                'skipping capitalization voucher for Certification %s',
                instance.pk,
            )
            return

        from apps.accounting.models import Voucher, VoucherLine
        from apps.accounting.utils import validate_closing_period

        # 마감기간 검증 — 인증 발급일 기준
        if not validate_closing_period(
            instance.issue_date,
            raise_exception=False,
            notify_user=instance.created_by,
            context=f'Certification {instance.cert_name} 자본화 전표',
        ):
            return

        voucher = Voucher.objects.create(
            voucher_number=_generate_voucher_number(),
            voucher_type='TRANSFER',
            voucher_date=instance.issue_date,
            description=f'자본화: {instance.cert_name} 무형자산 취득',
            approval_status='APPROVED',
            created_by=instance.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher, account=intangible_account,
            debit=instance.cost, credit=0,
            description=f'{instance.cert_name} 무형자산 취득',
            created_by=instance.created_by,
        )
        VoucherLine.objects.create(
            voucher=voucher, account=cash_account,
            debit=0, credit=instance.cost,
            description=f'{instance.cert_name} 인증비용 지급',
            created_by=instance.created_by,
        )
        logger.info(
            'Certification %s → IntangibleAsset %s created, voucher %s',
            instance.pk, asset_number, voucher.voucher_number,
        )
