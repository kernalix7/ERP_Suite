import logging
from datetime import date, timedelta

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def check_certification_expiry():
    """만료 30일 전 인증 알림 생성"""
    from apps.asset.models import Certification
    from apps.core.notification import Notification

    target_date = date.today() + timedelta(days=30)
    expiring = Certification.objects.filter(
        expiry_date=target_date, is_active=True,
    )
    count = 0
    for cert in expiring:
        if not cert.created_by:
            continue
        Notification.objects.create(
            title=f'인증 만료 예정: {cert.cert_name}',
            message=(
                f'{cert.get_cert_type_display()} "{cert.cert_name}" '
                f'(인증번호: {cert.cert_number})이 {cert.expiry_date}에 만료됩니다.'
            ),
            noti_type=Notification.NotiType.SYSTEM,
            user=cert.created_by,
        )
        count += 1
    logger.info('인증 만료 알림 %d건 생성', count)
    return count


@shared_task
def generate_lease_monthly_vouchers():
    """월 리스료 자동 전표 생성"""
    from django.db import transaction

    from apps.accounting.models import AccountCode, Voucher, VoucherLine
    from apps.asset.models import LeaseContract

    today = date.today()
    current_year = today.year
    current_month = today.month

    contracts = LeaseContract.objects.filter(
        auto_voucher=True,
        is_active=True,
        start_date__lte=today,
        end_date__gte=today,
    ).select_related('asset')

    # 계정과목 조회
    try:
        rent_account = AccountCode.objects.get(code='6200')  # 임차료
    except AccountCode.DoesNotExist:
        logger.warning('임차료 계정과목(6200)이 없습니다. 리스 전표 생성 중단.')
        return 0

    try:
        cash_account = AccountCode.objects.get(code='1110')  # 보통예금
    except AccountCode.DoesNotExist:
        try:
            cash_account = AccountCode.objects.get(code='1100')  # 현금및현금성자산
        except AccountCode.DoesNotExist:
            logger.warning('현금 계정과목(1110/1100)이 없습니다. 리스 전표 생성 중단.')
            return 0

    # 금융리스 부채 계정 (없으면 미지급금으로 대체)
    lease_liability_account = None
    try:
        lease_liability_account = AccountCode.objects.get(code='2400')  # 리스부채
    except AccountCode.DoesNotExist:
        try:
            lease_liability_account = AccountCode.objects.get(code='2200')  # 미지급금
        except AccountCode.DoesNotExist:
            pass

    count = 0
    for contract in contracts:
        # 중복 방지: 해당 월에 이미 생성된 전표가 있으면 스킵
        existing = Voucher.objects.filter(
            description__contains=contract.contract_number,
            voucher_date__year=current_year,
            voucher_date__month=current_month,
            is_active=True,
        ).exists()
        if existing:
            continue

        if contract.lease_type == LeaseContract.LeaseType.FINANCE:
            if not lease_liability_account:
                logger.warning(
                    '금융리스 부채 계정(2400/2200)이 없습니다. 계약 %s 스킵.',
                    contract.contract_number,
                )
                continue
            debit_account = lease_liability_account
            desc_prefix = '금융리스료'
        else:
            debit_account = rent_account
            desc_prefix = '운용리스료'

        description = f'{desc_prefix} - {contract.asset.name} ({contract.contract_number})'
        amount = contract.monthly_payment

        with transaction.atomic():
            voucher = Voucher.objects.create(
                voucher_type=Voucher.VoucherType.PAYMENT,
                voucher_date=today,
                description=description,
            )
            VoucherLine.objects.create(
                voucher=voucher,
                account=debit_account,
                debit=amount,
                credit=0,
                description=description,
            )
            VoucherLine.objects.create(
                voucher=voucher,
                account=cash_account,
                debit=0,
                credit=amount,
                description=description,
            )
        count += 1

    logger.info('리스 월 전표 %d건 생성', count)
    return count


@shared_task
def run_monthly_depreciation():
    """감가상각 월별 자동실행 (당월)"""
    from django.db.models import F
    from django.db import transaction

    from apps.asset.models import DepreciationRecord, FixedAsset

    today = date.today()
    year = today.year
    month = today.month

    assets = FixedAsset.objects.filter(
        is_active=True,
        status=FixedAsset.Status.ACTIVE,
    )

    created_count = 0
    skipped_count = 0

    with transaction.atomic():
        for asset in assets:
            if DepreciationRecord.objects.filter(asset=asset, year=year, month=month).exists():
                skipped_count += 1
                continue

            if asset.is_fully_depreciated:
                skipped_count += 1
                continue

            dep_amount = asset.monthly_depreciation
            if dep_amount <= 0:
                skipped_count += 1
                continue

            max_depreciable = asset.book_value - asset.residual_value
            if dep_amount > max_depreciable:
                dep_amount = int(max_depreciable)

            if dep_amount <= 0:
                skipped_count += 1
                continue

            new_accumulated = asset.accumulated_depreciation + dep_amount
            new_book_value = asset.acquisition_cost - new_accumulated

            DepreciationRecord.objects.create(
                asset=asset,
                year=year,
                month=month,
                depreciation_amount=dep_amount,
                accumulated_amount=new_accumulated,
                book_value_after=new_book_value,
            )

            FixedAsset.all_objects.filter(pk=asset.pk).update(
                accumulated_depreciation=F('accumulated_depreciation') + dep_amount,
                book_value=F('book_value') - dep_amount,
            )

            created_count += 1

    logger.info(
        '%d년 %d월 감가상각 완료: %d건 처리, %d건 건너뜀',
        year, month, created_count, skipped_count,
    )
    return created_count
