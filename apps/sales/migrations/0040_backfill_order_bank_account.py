"""주문의 비어있는 bank_account를 거래처 기본계좌로 채움.

- bank_account가 NULL인 주문만 대상
- 거래처에 default_bank_account가 설정된 경우만 적용
- 기존 bank_account가 있는 주문은 절대 변경하지 않음
"""
from django.db import migrations


def backfill_bank_account(apps, schema_editor):
    Order = apps.get_model('sales', 'Order')
    orders = Order.objects.filter(
        is_active=True,
        bank_account__isnull=True,
        partner__default_bank_account__isnull=False,
    ).select_related('partner')
    for order in orders:
        Order.objects.filter(pk=order.pk).update(
            bank_account=order.partner.default_bank_account,
        )


def reverse_backfill(apps, schema_editor):
    pass  # 역방향은 원복 불가 (원래 NULL이었던 것만 되돌릴 기준 없음)


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0039_add_partner_default_bank_account'),
    ]

    operations = [
        migrations.RunPython(backfill_bank_account, reverse_backfill),
    ]
