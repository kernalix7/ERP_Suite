import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.inventory.models import StockMovement, Warehouse

logger = logging.getLogger(__name__)


@receiver(post_save, sender='production.ProductionRecord')
def auto_stock_on_production(sender, instance, created, **kwargs):
    """생산실적 등록 시 완제품 입고 + 원자재 출고 자동 처리 (트랜잭션 보장)"""
    if not created:
        return

    warehouse = Warehouse.objects.first()
    if not warehouse:
        logger.error(
            'No warehouse configured — cannot create stock movement for %s',
            instance,
        )
        return

    work_order = instance.work_order
    plan = work_order.production_plan
    product = plan.product

    with transaction.atomic():
        # 완제품 생산입고
        if instance.good_quantity > 0:
            StockMovement.objects.create(
                movement_number=f'PI-{work_order.order_number}-{instance.pk}',
                movement_type='PROD_IN',
                product=product,
                warehouse=warehouse,
                quantity=instance.good_quantity,
                unit_price=product.cost_price,
                movement_date=instance.record_date,
                reference=f'작업지시 {work_order.order_number}',
                created_by=instance.created_by,
            )

        # BOM 기반 원자재 출고
        bom = plan.bom
        for bom_item in bom.items.all():
            consumed = int(bom_item.effective_quantity * instance.good_quantity)
            if consumed > 0:
                StockMovement.objects.create(
                    movement_number=f'PO-{work_order.order_number}-{instance.pk}-{bom_item.pk}',
                    movement_type='PROD_OUT',
                    product=bom_item.material,
                    warehouse=warehouse,
                    quantity=consumed,
                    unit_price=bom_item.material.cost_price,
                    movement_date=instance.record_date,
                    reference=f'작업지시 {work_order.order_number} 자재소모',
                    created_by=instance.created_by,
                )

        # 작업지시 상태 자동 전환
        total_produced = sum(r.good_quantity for r in work_order.records.all())
        if total_produced >= work_order.quantity:
            from django.utils import timezone
            work_order.status = 'COMPLETED'
            work_order.completed_at = timezone.now()
            work_order.save(update_fields=['status', 'completed_at', 'updated_at'])

        # 생산계획 상태 자동 전환
        all_complete = all(
            wo.status == 'COMPLETED' for wo in plan.work_orders.all()
        )
        if all_complete and plan.status == 'IN_PROGRESS':
            plan.status = 'COMPLETED'
            plan.actual_cost = int(bom.total_material_cost * plan.produced_quantity)
            plan.save(update_fields=['status', 'actual_cost', 'updated_at'])
