import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(soft_time_limit=300, time_limit=360)
def update_overdue_receivables():
    """매일 AR/AP 연체 상태 자동 전환 + 담당자 이메일 알림"""
    from datetime import date

    from apps.accounting.models import AccountPayable, AccountReceivable
    from apps.core.notification import create_notification

    today = date.today()

    # AR 연체 전환 — 개별 조회하여 알림 발송
    overdue_ars = list(
        AccountReceivable.objects.filter(
            is_active=True,
            due_date__lt=today,
            status__in=['PENDING', 'PARTIAL'],
        ).select_related('created_by')
    )
    ar_count = len(overdue_ars)
    if overdue_ars:
        AccountReceivable.objects.filter(
            pk__in=[ar.pk for ar in overdue_ars],
        ).update(status='OVERDUE')

        # 담당자(created_by)에게 알림 + 이메일 (OVERDUE 유형 → 이메일 자동 발송)
        notify_users = list({ar.created_by for ar in overdue_ars if ar.created_by_id})
        if notify_users:
            create_notification(
                notify_users,
                f'AR 연체 {ar_count}건 발생',
                f'오늘({today}) 기준 {ar_count}건의 매출채권이 연체 상태로 전환되었습니다.',
                noti_type='OVERDUE',
                link='/accounting/ar/',
            )

    # AP 연체 전환
    ap_count = AccountPayable.objects.filter(
        is_active=True,
        due_date__lt=today,
        status__in=['PENDING', 'PARTIAL'],
    ).update(status='OVERDUE')

    logger.info(
        'Overdue update: %d AR(s), %d AP(s) marked as OVERDUE',
        ar_count, ap_count,
    )
    return {'ar_updated': ar_count, 'ap_updated': ap_count}


@shared_task
def create_monthly_card_billing():
    """매월 1일 전월 카드별 거래 합산 -> CardBilling 자동 생성"""
    from datetime import date

    from django.db.models import Sum

    from apps.accounting.models import CardBilling, CardTransaction, CreditCard

    today = date.today()
    # 전월 계산
    if today.month == 1:
        billing_year, billing_month = today.year - 1, 12
    else:
        billing_year, billing_month = today.year, today.month - 1

    billing_date = date(billing_year, billing_month, 1)

    for card in CreditCard.objects.filter(is_active=True):
        # 이미 청구서 있으면 스킵
        if CardBilling.objects.filter(card=card, billing_month=billing_date).exists():
            continue

        # 전월 거래 합산
        total = CardTransaction.objects.filter(
            card=card, is_active=True, is_cancelled=False,
            transaction_date__year=billing_year,
            transaction_date__month=billing_month,
            billing__isnull=True,
        ).aggregate(total=Sum('amount'))['total'] or 0

        if total <= 0:
            continue

        # 결제기한: 당월 결제일
        payment_due = date(today.year, today.month, min(card.billing_day, 28))

        billing = CardBilling.objects.create(
            card=card,
            billing_month=billing_date,
            total_amount=total,
            payment_due_date=payment_due,
        )

        # 거래에 billing 연결
        CardTransaction.objects.filter(
            card=card, is_active=True, is_cancelled=False,
            transaction_date__year=billing_year,
            transaction_date__month=billing_month,
            billing__isnull=True,
        ).update(billing=billing)

    logger.info('Monthly card billing creation completed')


@shared_task
def reset_card_used_amount():
    """매월 1일 CreditCard.used_amount = 0 초기화"""
    from apps.accounting.models import CreditCard

    count = CreditCard.objects.filter(is_active=True).update(used_amount=0)
    logger.info('Reset used_amount for %d cards', count)
    return count


@shared_task(soft_time_limit=600, time_limit=660)
def auto_bad_debt_allowance():
    """매월 1일 실행 — 연체 AR 스캔 후 대손충당금 자동 계상"""
    from datetime import date

    from django.db import transaction

    from apps.accounting.models import AccountCode, AccountReceivable, Voucher, VoucherLine
    from apps.accounting.models_baddebt import AgingBucket, BadDebtAllowance

    today = date.today()

    # K-GAAP 표준 계정과목 get_or_create (없으면 생성)
    expense_account, _ = AccountCode.objects.get_or_create(
        code='524',
        defaults={
            'name': '대손상각비',
            'account_type': AccountCode.AccountType.EXPENSE,
        },
    )
    allowance_account, _ = AccountCode.objects.get_or_create(
        code='109',
        defaults={
            'name': '대손충당금',
            'account_type': AccountCode.AccountType.ASSET,
        },
    )

    overdue_ars = (
        AccountReceivable.objects.filter(
            is_active=True,
            status__in=['UNPAID', 'OVERDUE', 'PENDING', 'PARTIAL'],
            due_date__lt=today,
        )
        .select_related('partner')
    )

    # 충당률 매트릭스: (연체일 하한, 연체일 상한, 충당률%)
    rate_matrix = [
        (30, 59, 1),
        (60, 89, 3),
        (90, 179, 5),
        (180, 364, 10),
        (365, 99999, 100),
    ]

    created_count = 0
    skipped_count = 0

    for ar in overdue_ars:
        days = (today - ar.due_date).days
        rate = next((r for lo, hi, r in rate_matrix if lo <= days <= hi), 0)
        if rate == 0:
            continue

        balance = ar.amount - ar.paid_amount
        if balance <= 0:
            continue

        allowance = int(balance * rate / 100)
        if allowance <= 0:
            continue

        # 중복 방지: 해당 AR의 이번달 BDA 있으면 skip
        if BadDebtAllowance.objects.filter(
            receivable=ar,
            estimated_date__year=today.year,
            estimated_date__month=today.month,
            is_active=True,
        ).exists():
            skipped_count += 1
            continue

        if days < 60:
            bucket = AgingBucket.DAYS_30
        elif days < 90:
            bucket = AgingBucket.DAYS_60
        elif days < 180:
            bucket = AgingBucket.DAYS_90
        elif days < 365:
            bucket = AgingBucket.DAYS_180
        else:
            bucket = AgingBucket.DAYS_365

        with transaction.atomic():
            voucher = Voucher.objects.create(
                voucher_type=Voucher.VoucherType.TRANSFER,
                voucher_date=today,
                description=f'대손충당금 계상 — {ar.partner.name} ({days}일 연체)',
                approval_status=Voucher.ApprovalStatus.DRAFT,
            )
            # 차변: 대손상각비(판관비 524)
            VoucherLine.objects.create(
                voucher=voucher,
                account=expense_account,
                debit=allowance,
                credit=0,
                description=f'대손상각비 — {ar.partner.name}',
            )
            # 대변: 대손충당금(자산차감 109)
            VoucherLine.objects.create(
                voucher=voucher,
                account=allowance_account,
                debit=0,
                credit=allowance,
                description=f'대손충당금 — {ar.partner.name}',
            )

            BadDebtAllowance.objects.create(
                receivable=ar,
                estimated_date=today,
                allowance_amount=allowance,
                allowance_rate=rate,
                aging_bucket=bucket,
                voucher=voucher,
            )
            created_count += 1

    logger.info(
        'BadDebt allowance: %d created, %d skipped (already exists this month)',
        created_count,
        skipped_count,
    )
    return {'created': created_count, 'skipped': skipped_count}
