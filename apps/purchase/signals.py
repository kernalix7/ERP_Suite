from django.db import transaction
from django.db.models import F, Sum
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import GoodsReceiptItem, PurchaseOrder


@receiver(post_save, sender=GoodsReceiptItem)
def handle_goods_receipt(sender, instance, created, **kwargs):
    """입고항목 생성 시 재고 입고(StockMovement IN) 및 발주 상태 갱신"""
    if not created:
        return

    with transaction.atomic():
        po_item = instance.po_item
        goods_receipt = instance.goods_receipt
        po = goods_receipt.purchase_order

        # 1. StockMovement(IN) 자동 생성
        from apps.inventory.models import StockMovement, Warehouse

        warehouse = Warehouse.objects.first()
        if warehouse:
            # 고유한 movement_number 생성
            movement_number = f'GR-{goods_receipt.receipt_number}-{instance.pk}'
            StockMovement.objects.create(
                movement_number=movement_number,
                movement_type='IN',
                product=po_item.product,
                warehouse=warehouse,
                quantity=instance.received_quantity,
                unit_price=po_item.unit_price,
                movement_date=goods_receipt.receipt_date,
                reference=f'발주입고: {po.po_number}',
            )

        # 2. PurchaseOrderItem.received_quantity 갱신
        total_received = po_item.receipt_items.aggregate(
            total=Sum('received_quantity')
        )['total'] or 0
        po_item.received_quantity = total_received
        po_item.save(update_fields=['received_quantity', 'updated_at'])

        # 3. PurchaseOrder 상태 갱신
        all_items = po.items.all()
        fully_received = all(
            item.received_quantity >= item.quantity for item in all_items
        )
        partially_received = any(
            item.received_quantity > 0 for item in all_items
        )

        if fully_received:
            po.status = PurchaseOrder.Status.RECEIVED
        elif partially_received:
            po.status = PurchaseOrder.Status.PARTIAL_RECEIVED
        po.save(update_fields=['status', 'updated_at'])
