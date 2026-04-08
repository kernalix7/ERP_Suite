import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def update_overdue_receivables():
    """매일 AR/AP 연체 상태 자동 전환"""
    from datetime import date

    from apps.accounting.models import AccountPayable, AccountReceivable

    today = date.today()

    # AR 연체 전환
    ar_count = AccountReceivable.objects.filter(
        is_active=True,
        due_date__lt=today,
        status__in=['PENDING', 'PARTIAL'],
    ).update(status='OVERDUE')

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
