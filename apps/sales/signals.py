from datetime import date

from django.db.models.signals import pre_save
from django.dispatch import receiver

from apps.inventory.models import StockMovement, Warehouse


@receiver(pre_save, sender='sales.Order')
def auto_stock_out_on_ship(sender, instance, **kwargs):
    """주문이 출고완료 상태로 변경되면 자동으로 출고 전표 생성"""
    if not instance.pk:
        return

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    # 상태가 '출고완료'로 변경될 때만
    if old.status != 'SHIPPED' and instance.status == 'SHIPPED':
        warehouse = Warehouse.objects.first()
        if not warehouse:
            return

        for item in instance.items.all():
            StockMovement.objects.create(
                movement_number=f'OUT-{instance.order_number}-{item.pk}',
                movement_type='OUT',
                product=item.product,
                warehouse=warehouse,
                quantity=item.quantity,
                unit_price=item.unit_price,
                movement_date=date.today(),
                reference=f'주문 {instance.order_number}',
                created_by=instance.created_by,
            )
