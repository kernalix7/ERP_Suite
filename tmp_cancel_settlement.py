"""정산 일괄 취소 — 정산+입출금+전표 전부 롤백"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.db import transaction
from django.db.models import F
from apps.accounting.models import (
    SalesSettlement, SalesSettlementOrder, Payment, BankAccount,
)
from apps.sales.models import Order

TARGETS = ['SS-20260329-005']

for snum in TARGETS:
    settlement = SalesSettlement.objects.filter(settlement_number=snum).first()
    if not settlement:
        print(f'{snum} 없음 — 스킵')
        continue

    print(f'\n[{settlement.settlement_number}]')
    print(f'  매출: {settlement.total_revenue:,}원 / 수수료: {settlement.total_commission:,}원')

    with transaction.atomic():
        payments = Payment.objects.filter(
            reference__contains=settlement.settlement_number, is_active=True,
        )
        for p in payments:
            if p.bank_account:
                if p.payment_type == 'RECEIPT':
                    BankAccount.objects.filter(pk=p.bank_account_id).update(balance=F('balance') - p.amount)
                    print(f'  입금 복원: {p.bank_account.name} -{p.amount:,}원')
                elif p.payment_type == 'DISBURSEMENT':
                    BankAccount.objects.filter(pk=p.bank_account_id).update(balance=F('balance') + p.amount)
                    print(f'  출금 복원: {p.bank_account.name} +{p.amount:,}원')
                if p.voucher:
                    p.voucher.is_active = False
                    p.voucher.save(update_fields=['is_active', 'updated_at'])
                    print(f'  전표 삭제: {p.voucher.voucher_number}')
            p.is_active = False
            p.save(update_fields=['is_active', 'updated_at'])

        if settlement.commission_voucher:
            settlement.commission_voucher.is_active = False
            settlement.commission_voucher.save(update_fields=['is_active', 'updated_at'])

        order_ids = list(SalesSettlementOrder.objects.filter(
            settlement=settlement,
        ).values_list('order_id', flat=True))
        Order.objects.filter(pk__in=order_ids).update(is_settled=False)
        print(f'  주문 {len(order_ids)}건 정산 해제')

        SalesSettlementOrder.objects.filter(settlement=settlement).update(is_active=False)
        settlement.is_active = False
        settlement.save(update_fields=['is_active', 'updated_at'])

    print(f'  취소 완료')

print('\n전부 완료')
