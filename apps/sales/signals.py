import logging
from datetime import date

from django.db import transaction
from django.db.models.signals import pre_save
from django.dispatch import receiver

from apps.inventory.models import Product, StockMovement, Warehouse


logger = logging.getLogger(__name__)


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
            logger.error(
                'No warehouse configured — cannot create stock movement for %s',
                instance,
            )
            return

        # C2: Idempotency — skip if movements already exist for this order
        existing = StockMovement.all_objects.filter(
            reference__startswith=f'주문 {instance.order_number}',
            movement_type='OUT',
        ).exists()
        if existing:
            return

        with transaction.atomic():
            for item in instance.items.all():
                # C1: Stock availability check before creating OUT movement
                product = Product.all_objects.get(pk=item.product_id)
                if product.current_stock < item.quantity:
                    logger.warning(
                        'Insufficient stock for order %s: product %s '
                        '(current: %d, required: %d)',
                        instance.order_number, product.code,
                        product.current_stock, item.quantity,
                    )

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
