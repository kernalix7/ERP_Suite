import logging

from django.db import transaction
from django.db.models import Q, Sum
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.inventory.models import StockMovement, Warehouse

logger = logging.getLogger(__name__)


def _record_ref_prefix(work_order, record):
    """재고이동 번호 접두사 (PI-/PO- 뒤에 붙는 부분)"""
    return f'{work_order.order_number}-{record.pk}'


def _delete_old_movements(record):
    """해당 생산실적에 연결된 기존 재고이동 soft delete (수정 시 역분개용)"""
    prefix = _record_ref_prefix(record.work_order, record)
    movements = StockMovement.all_objects.filter(
        movement_type__in=['PROD_IN', 'PROD_OUT'],
        is_active=True,
    ).filter(
        Q(movement_number=f'PI-{prefix}')
        | Q(movement_number__startswith=f'PO-{prefix}')
    )
    for movement in movements:
        movement.is_active = False
        movement.save()


def _create_movements(instance, warehouse):
    """생산실적 기반 재고이동 생성"""
    work_order = instance.work_order
    plan = work_order.production_plan
    product = plan.product

    # 완제품 생산입고
    if instance.good_quantity > 0:
        StockMovement.objects.create(
            movement_number=f'PI-{_record_ref_prefix(work_order, instance)}',
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
    for bom_item in bom.items.select_related('material').all():
        consumed = bom_item.effective_quantity * instance.good_quantity
        if consumed > 0:
            StockMovement.objects.create(
                movement_number=(
                    f'PO-{_record_ref_prefix(work_order, instance)}'
                    f'-{bom_item.pk}'
                ),
                movement_type='PROD_OUT',
                product=bom_item.material,
                warehouse=warehouse,
                quantity=consumed,
                unit_price=bom_item.material.cost_price,
                movement_date=instance.record_date,
                reference=f'작업지시 {work_order.order_number} 자재소모',
                created_by=instance.created_by,
            )


def _update_work_order_status(work_order):
    """작업지시 상태 자동 전환"""
    total_produced = work_order.records.aggregate(
        total=Sum('good_quantity'),
    )['total'] or 0
    if total_produced >= work_order.quantity:
        if work_order.status != 'COMPLETED':
            from django.utils import timezone
            work_order.status = 'COMPLETED'
            work_order.completed_at = timezone.now()
            work_order.save(update_fields=[
                'status', 'completed_at', 'updated_at',
            ])
    else:
        if work_order.status == 'COMPLETED':
            work_order.status = 'IN_PROGRESS'
            work_order.completed_at = None
            work_order.save(update_fields=[
                'status', 'completed_at', 'updated_at',
            ])


def _update_plan_status(plan):
    """생산계획 상태 자동 전환"""
    all_complete = all(
        wo.status == 'COMPLETED'
        for wo in plan.work_orders.all()
    )
    if all_complete and plan.status == 'IN_PROGRESS':
        bom = plan.bom
        plan.status = 'COMPLETED'
        plan.actual_cost = int(
            bom.total_material_cost * plan.produced_quantity
        )
        plan.save(update_fields=[
            'status', 'actual_cost', 'updated_at',
        ])
    elif not all_complete and plan.status == 'COMPLETED':
        plan.status = 'IN_PROGRESS'
        plan.save(update_fields=['status', 'updated_at'])


@receiver(post_save, sender='production.ProductionRecord')
def auto_stock_on_production(sender, instance, created, **kwargs):
    """생산실적 등록/수정 시 재고이동 자동 처리"""
    # unit_cost 저장으로 인한 재진입 방지
    if kwargs.get('update_fields') and set(kwargs['update_fields']) <= {
        'unit_cost', 'updated_at',
    }:
        return

    warehouse = instance.warehouse or Warehouse.get_default()
    if not warehouse:
        logger.error(
            'No warehouse configured — cannot create '
            'stock movement for %s', instance,
        )
        return

    work_order = instance.work_order
    plan = work_order.production_plan

    with transaction.atomic():
        # 생산단가 스냅샷 (최초 등록 시: BOM 기반 실제 생산원가)
        if created and not instance.unit_cost:
            bom = plan.bom
            unit_cost = int(bom.total_material_cost) if bom else 0
            from apps.production.models import ProductionRecord
            ProductionRecord.objects.filter(pk=instance.pk).update(
                unit_cost=unit_cost,
            )
            instance.unit_cost = unit_cost

        # 원자재 부족 체크 (경고 로깅)
        if created:
            bom = plan.bom
            shortages = bom.check_material_availability(
                instance.good_quantity,
            )
            if shortages:
                for s in shortages:
                    logger.warning(
                        'Material shortage: %s needs %s '
                        '(available %s, short %s) '
                        'for WO %s',
                        s['material'].code,
                        s['required'],
                        s['available'],
                        s['shortage'],
                        work_order.order_number,
                    )

        if not created:
            _delete_old_movements(instance)

        _create_movements(instance, warehouse)
        _update_work_order_status(work_order)
        _update_plan_status(plan)


def _cancel_production_records_stock(work_orders):
    """작업지시 목록에 연결된 생산실적의 재고이동을 soft delete"""
    from apps.production.models import ProductionRecord

    records = ProductionRecord.objects.filter(
        work_order__in=work_orders,
        is_active=True,
    )
    cancelled_count = 0
    for record in records:
        prefix = _record_ref_prefix(record.work_order, record)
        movements = StockMovement.objects.filter(
            is_active=True,
        ).filter(
            Q(movement_number=f'PI-{prefix}')
            | Q(movement_number__startswith=f'PO-{prefix}')
        )
        for mv in movements:
            mv.is_active = False
            mv.save(update_fields=['is_active', 'updated_at'])
            cancelled_count += 1

    return cancelled_count


@receiver(pre_save, sender='production.ProductionPlan')
def cancel_plan_cascade(sender, instance, **kwargs):
    """생산계획 취소 시 관련 생산실적의 재고이동 자동 취소"""
    if not instance.pk:
        return

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old.status != 'CANCELLED' and instance.status == 'CANCELLED':
        with transaction.atomic():
            work_orders = instance.work_orders.filter(is_active=True)
            count = _cancel_production_records_stock(work_orders)
            logger.info(
                'ProductionPlan %s cancelled — %d stock movements reversed',
                instance.plan_number, count,
            )


@receiver(pre_save, sender='production.WorkOrder')
def cancel_work_order_cascade(sender, instance, **kwargs):
    """작업지시 취소 시 관련 생산실적의 재고이동 자동 취소"""
    if not instance.pk:
        return

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old.status != 'CANCELLED' and instance.status == 'CANCELLED':
        with transaction.atomic():
            count = _cancel_production_records_stock([instance])
            logger.info(
                'WorkOrder %s cancelled — %d stock movements reversed',
                instance.order_number, count,
            )
