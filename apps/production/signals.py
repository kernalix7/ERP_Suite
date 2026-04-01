import logging

from django.db import transaction
from django.db.models import Q, Sum
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.inventory.models import Product, StockMovement, Warehouse

logger = logging.getLogger(__name__)


def _record_ref_prefix(work_order, record):
    """재고이동 번호 접두사 (PI-/PO- 뒤에 붙는 부분)"""
    return f'{work_order.order_number}-{record.pk}'


def _delete_old_movements(record):
    """해당 생산실적에 연결된 기존 재고이동 soft delete (수정 시 역분개용)

    개별 save() 대신 QuerySet.update()로 bulk 처리하되,
    inventory pre_save 시그널이 발동하지 않으므로 재고 복원을 수동으로 수행.
    """
    from django.db.models import F as F_expr
    from apps.inventory.models import Product, WarehouseStock

    prefix = _record_ref_prefix(record.work_order, record)
    movements = StockMovement.all_objects.filter(
        movement_type__in=['PROD_IN', 'PROD_OUT'],
        is_active=True,
    ).filter(
        Q(movement_number=f'PI-{prefix}')
        | Q(movement_number__startswith=f'PO-{prefix}')
    )

    # 재고 복원을 위해 먼저 movement 목록 수집
    INBOUND = {'IN', 'ADJ_PLUS', 'PROD_IN', 'RETURN'}
    OUTBOUND = {'OUT', 'ADJ_MINUS', 'PROD_OUT'}
    for mv in movements:
        if mv.movement_type in INBOUND:
            Product.objects.filter(pk=mv.product_id).update(
                current_stock=F_expr('current_stock') - mv.quantity,
            )
            try:
                ws = WarehouseStock.objects.get(
                    warehouse_id=mv.warehouse_id,
                    product_id=mv.product_id,
                )
                WarehouseStock.objects.filter(pk=ws.pk).update(
                    quantity=F_expr('quantity') - mv.quantity,
                )
            except WarehouseStock.DoesNotExist:
                pass
        elif mv.movement_type in OUTBOUND:
            Product.objects.filter(pk=mv.product_id).update(
                current_stock=F_expr('current_stock') + mv.quantity,
            )
            try:
                ws = WarehouseStock.objects.get(
                    warehouse_id=mv.warehouse_id,
                    product_id=mv.product_id,
                )
                WarehouseStock.objects.filter(pk=ws.pk).update(
                    quantity=F_expr('quantity') + mv.quantity,
                )
            except WarehouseStock.DoesNotExist:
                pass

    # bulk soft delete (시그널 우회)
    movements.update(is_active=False)


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
        # 생산단가 + 실제원가 스냅샷 (최초 등록 시)
        if created and not instance.unit_cost:
            bom = plan.bom
            unit_cost = int(bom.total_material_cost) if bom else 0
            qty = instance.good_quantity or 1
            update_fields = {'unit_cost': unit_cost}

            # 표준원가 기반 실제원가 자동 세팅
            from apps.production.models import StandardCost, ProductionRecord
            std = StandardCost.objects.filter(
                product=plan.product, is_current=True, is_active=True,
            ).first()
            if std:
                update_fields['actual_material_cost'] = std.material_cost * qty
                update_fields['actual_labor_cost'] = std.labor_cost * qty
                update_fields['actual_overhead_cost'] = std.overhead_cost * qty

            ProductionRecord.objects.filter(pk=instance.pk).update(
                **update_fields,
            )
            for k, v in update_fields.items():
                setattr(instance, k, v)

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
    """작업지시 목록에 연결된 생산실적 + 재고이동을 soft delete"""
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

        # 생산실적도 soft delete (QuerySet.update로 post_save 시그널 우회)
        ProductionRecord.objects.filter(pk=record.pk).update(is_active=False)

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
            # 관련 작업지시도 CANCELLED로 변경
            work_orders.exclude(status='CANCELLED').update(
                status='CANCELLED',
            )
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


# ── BOM/StandardCost → Product.cost_price 자동 동기화 ────────────


def _sync_product_cost_price(product):
    """제품 원가 자동 동기화. 우선순위: StandardCost > BOM > 기존값 유지"""
    from apps.production.models import BOM, StandardCost

    # 1순위: 현행 표준원가
    std_cost = StandardCost.objects.filter(
        product=product, is_current=True, is_active=True,
    ).first()
    if std_cost and std_cost.total_standard_cost > 0:
        if product.cost_price != std_cost.total_standard_cost:
            Product.objects.filter(pk=product.pk).update(
                cost_price=std_cost.total_standard_cost,
            )
        return

    # 2순위: 기본 BOM 자재원가
    default_bom = BOM.objects.filter(
        product=product, is_default=True, is_active=True,
    ).prefetch_related('items__material').first()
    if default_bom:
        bom_cost = default_bom.total_material_cost
        if bom_cost and bom_cost > 0 and product.cost_price != bom_cost:
            Product.objects.filter(pk=product.pk).update(
                cost_price=int(bom_cost),
            )
        return

    # 3순위: 기존값 유지 (아무것도 안함)


@receiver(post_save, sender='production.BOMItem')
def sync_cost_on_bom_item_save(sender, instance, **kwargs):
    """BOMItem 저장 시 해당 BOM 완제품의 cost_price 동기화"""
    bom = instance.bom
    if bom.is_default and bom.is_active:
        _sync_product_cost_price(bom.product)


@receiver(post_delete, sender='production.BOMItem')
def sync_cost_on_bom_item_delete(sender, instance, **kwargs):
    """BOMItem 삭제 시 해당 BOM 완제품의 cost_price 동기화"""
    bom = instance.bom
    if bom.is_default and bom.is_active:
        _sync_product_cost_price(bom.product)


@receiver(post_save, sender='production.BOM')
def sync_cost_on_bom_save(sender, instance, **kwargs):
    """BOM 저장 시 (is_default 변경 등) 완제품의 cost_price 동기화"""
    if instance.is_default and instance.is_active:
        _sync_product_cost_price(instance.product)


@receiver(post_save, sender='production.StandardCost')
def sync_cost_on_standard_cost_save(sender, instance, **kwargs):
    """StandardCost 저장 시 완제품의 cost_price 동기화"""
    if instance.is_current and instance.is_active:
        _sync_product_cost_price(instance.product)
