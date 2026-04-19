import logging

from django.db import transaction
from django.db.models import Q, Sum
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.inventory.models import Product, SerialNumber, StockMovement, Warehouse

logger = logging.getLogger(__name__)


def _record_ref_prefix(work_order, record):
    """재고이동 번호 접두사 (PI-/PO- 뒤에 붙는 부분)"""
    return f'{work_order.order_number}-{record.pk}'


def _delete_old_movements(record):
    """해당 생산실적에 연결된 기존 재고이동 soft delete (수정 시 역분개용)

    개별 save() 대신 QuerySet.update()로 bulk 처리하되,
    inventory pre_save 시그널이 발동하지 않으므로 재고 복원을 수동으로 수행.
    StockLot도 함께 처리: PROD_IN LOT soft delete, PROD_OUT LOT remaining_quantity 복원.
    """
    from decimal import Decimal, ROUND_HALF_UP
    from django.db.models import F as F_expr
    from apps.inventory.models import Product, WarehouseStock, StockLot

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
        # 서비스/무형상품은 재고 복원 스킵
        product_obj = Product.all_objects.get(pk=mv.product_id)
        if not product_obj.is_stockable:
            continue

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
            # PROD_IN: 연결된 StockLot soft delete
            StockLot.objects.filter(
                stock_movement=mv, is_active=True,
            ).update(is_active=False)
            # PROD_IN: 이동평균단가 역산
            # 주의: 위에서 current_stock을 이미 F()로 차감했으므로, 원래 재고를 복원하여 계산
            if mv.movement_type == 'PROD_IN' and mv.unit_price:
                product = Product.objects.select_for_update().get(pk=mv.product_id)
                product.refresh_from_db()
                current = product.current_stock + mv.quantity  # 차감 전 원래 재고
                if current > mv.quantity:
                    old_total = (product.cost_price or Decimal('0')) * current
                    removed_total = mv.unit_price * mv.quantity
                    new_stock = current - mv.quantity
                    new_cost = ((old_total - removed_total) / new_stock).quantize(
                        Decimal('1'), rounding=ROUND_HALF_UP,
                    )
                    new_cost = max(new_cost, Decimal('0'))
                    Product.objects.filter(pk=mv.product_id).update(
                        cost_price=new_cost,
                    )
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
            # PROD_OUT: 소진된 StockLot의 remaining_quantity 복원 (소진 역순)
            remaining_to_restore = mv.quantity
            if product_obj.valuation_method == 'LIFO':
                ordering = ['received_date', 'pk']      # LIFO 소진 역순
            else:
                ordering = ['-received_date', '-pk']    # FIFO 소진 역순
            lots = (
                StockLot.objects
                .filter(
                    product_id=mv.product_id,
                    warehouse_id=mv.warehouse_id,
                    is_active=True,
                )
                .exclude(remaining_quantity=F_expr('initial_quantity'))
                .order_by(*ordering)
                .select_for_update()
            )
            for lot in lots:
                if remaining_to_restore <= 0:
                    break
                consumed = lot.initial_quantity - lot.remaining_quantity
                restore_qty = min(consumed, remaining_to_restore)
                remaining_to_restore -= restore_qty
                StockLot.objects.filter(pk=lot.pk).update(
                    remaining_quantity=F_expr('remaining_quantity') + restore_qty,
                )

    # bulk soft delete (시그널 우회)
    movements.update(is_active=False)


def _get_or_create_batch(instance):
    """생산실적에 연결된 ProductionBatch 보장 (없으면 생성)"""
    from apps.production.models import ProductionBatch

    existing = ProductionBatch.objects.filter(production_record=instance).first()
    if existing:
        return existing

    work_order = instance.work_order
    product = work_order.production_plan.product
    from decimal import Decimal as _Dec
    qty = _Dec(str(instance.good_quantity or 0))
    return ProductionBatch.objects.create(
        production_record=instance,
        work_center=work_order.work_center,
        product=product,
        shift=ProductionBatch.Shift.A,
        production_date=instance.record_date,
        total_quantity=qty,
        remaining_quantity=qty,
        created_by=instance.created_by,
    )


def _create_serial_numbers(instance, warehouse, batch=None):
    """시리얼 추적 제품의 생산 시 시리얼번호 자동 생성"""
    from django.utils import timezone
    from django.db.models import Max

    product = instance.work_order.production_plan.product
    if not product.serial_tracking or instance.good_quantity <= 0:
        return

    today_str = timezone.now().strftime('%Y%m%d')
    prefix = product.serial_prefix or ''

    # 해당 제품의 기존 시리얼번호에서 최대 순번 추출
    last_serial = (
        SerialNumber.all_objects
        .filter(product=product)
        .aggregate(max_pk=Max('pk'))
    )
    start_seq = (last_serial['max_pk'] or 0) + 1

    # 실제 순번은 동일 접두사+날짜 패턴의 마지막 번호 기반
    pattern_prefix = f'{prefix}{today_str}-'
    last_in_pattern = (
        SerialNumber.all_objects
        .filter(serial__startswith=pattern_prefix)
        .order_by('-serial')
        .values_list('serial', flat=True)
        .first()
    )
    if last_in_pattern:
        try:
            last_seq = int(last_in_pattern.split('-')[-1])
        except (ValueError, IndexError):
            last_seq = 0
    else:
        last_seq = 0

    serials = []
    for i in range(instance.good_quantity):
        seq = last_seq + i + 1
        serial_str = f'{prefix}{today_str}-{seq:04d}'
        serials.append(SerialNumber(
            serial=serial_str,
            product=product,
            status=SerialNumber.Status.IN_STOCK,
            production_record=instance,
            production_batch=batch,
            production_date=timezone.now().date(),
            warehouse=warehouse,
            created_by=instance.created_by,
        ))

    if serials:
        SerialNumber.objects.bulk_create(serials)
        logger.info(
            'Created %d serial numbers for product %s (record %s)',
            len(serials), product.code, instance.pk,
        )


def _create_movements(instance, warehouse, batch=None):
    """생산실적 기반 재고이동 생성"""
    work_order = instance.work_order
    plan = work_order.production_plan
    product = plan.product

    # 완제품 생산입고 (재고 추적 대상만)
    # unit_price에 BOM 기반 실제 생산원가 반영 (이동평균 정확도 향상)
    if instance.good_quantity > 0 and product.is_stockable:
        prod_unit_price = instance.unit_cost if instance.unit_cost else product.cost_price
        StockMovement.objects.create(
            movement_number=f'PI-{_record_ref_prefix(work_order, instance)}',
            movement_type='PROD_IN',
            product=product,
            warehouse=warehouse,
            quantity=instance.good_quantity,
            unit_price=prod_unit_price,
            movement_date=instance.record_date,
            reference=f'작업지시 {work_order.order_number}',
            production_batch=batch,
            created_by=instance.created_by,
        )

    # BOM 기반 원자재 출고 (재고 추적 대상만)
    # 불량품도 자재를 소모하므로 총수량(양품+불량) 기준으로 소모
    total_produced = instance.good_quantity + instance.defect_quantity
    bom = plan.bom
    for bom_item in bom.items.select_related('material').all():
        consumed = bom_item.effective_quantity * total_produced
        if consumed > 0 and bom_item.material.is_stockable:
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

    # 불량품 로깅 (불량품은 PROD_IN에 포함되지 않으므로 재고 차감 불필요,
    # 원자재 소모는 위의 PROD_OUT에서 total_produced 기준으로 이미 반영됨)
    if instance.defect_quantity > 0:
        logger.info(
            'Scrap recorded: %s x %d for WO %s '
            '(materials consumed for %d total units)',
            product.code, instance.defect_quantity,
            work_order.order_number, total_produced,
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
    from apps.production.models import ProductionRecord

    all_complete = all(
        wo.status == 'COMPLETED'
        for wo in plan.work_orders.all()
    )
    if all_complete and plan.status == 'IN_PROGRESS':
        plan.status = 'COMPLETED'
        records = ProductionRecord.objects.filter(
            work_order__production_plan=plan, is_active=True,
        )
        actual_total = int(sum(
            (r.actual_material_cost or 0)
            + (r.actual_labor_cost or 0)
            + (r.actual_overhead_cost or 0)
            for r in records
        ))
        if actual_total > 0:
            plan.actual_cost = actual_total
        else:
            # 실제원가 미입력 시 BOM 표준원가 기반 폴백
            bom = plan.bom
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

        # ProductionBatch 보장 (없으면 생성) — 신규/수정 모두
        batch = _get_or_create_batch(instance)

        _create_movements(instance, warehouse, batch=batch)

        # 시리얼 추적 제품: 최초 등록 시 시리얼번호 자동 생성
        if created:
            _create_serial_numbers(instance, warehouse, batch=batch)

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


def _auto_version_standard_cost(product):
    """auto_standard_cost 활성화 시 BOM 기반 표준원가 새 버전 자동 생성.

    자재원가만 BOM에서 갱신. 노무비/간접비는 0으로 설정 (수동 관리 영역).
    자재원가 변동이 없으면 스킵 (불필요한 버전 방지).
    save() 호출로 합계 자동 계산 + is_current 토글.
    """
    from apps.production.models import BOM, StandardCost
    from django.utils import timezone

    bom = BOM.objects.filter(
        product=product, is_default=True, is_active=True,
    ).prefetch_related('items__material').first()
    if not bom:
        return

    material_cost = int(bom.total_material_cost or 0)
    if not material_cost:
        return

    # 기존 현행 표준원가
    current_std = StandardCost.objects.filter(
        product=product, is_current=True, is_active=True,
    ).first()

    # 자재원가 변동 없으면 스킵
    if current_std and current_std.material_cost == material_cost:
        return

    # 새 버전 번호 생성
    today_str = timezone.now().strftime('%Y%m%d')
    base_version = f'AUTO-{today_str}'
    existing_count = StandardCost.all_objects.filter(
        product=product, version__startswith=base_version,
    ).count()
    version = f'{base_version}-{existing_count + 1}' if existing_count else base_version

    # 새 버전 생성 — 자재원가만, 노무비/간접비는 0 (수동 관리)
    StandardCost.objects.create(
        product=product,
        version=version,
        effective_date=timezone.now().date(),
        material_cost=material_cost,
        direct_labor_hours=0,
        labor_rate_per_hour=0,
        overhead_rate=0,
        is_current=True,
    )
    logger.info(
        'StandardCost auto-versioned: %s v%s (material: %s, prev: %s)',
        product.code, version, material_cost,
        current_std.version if current_std else 'none',
    )


def _sync_product_cost_price(product):
    """제품 원가 자동 동기화. 우선순위: StandardCost > BOM > 기존값 유지.
    Returns True if cost_price changed.

    auto_standard_cost가 켜져 있으면:
    - 기존 표준원가의 자재원가를 BOM에서 자동 갱신 (갱신 후 표준원가 우선)
    - 표준원가가 없으면 BOM 경로에서 자동 생성
    """
    from apps.production.models import BOM, StandardCost

    # auto_standard_cost: BOM 기반 표준원가 새 버전 자동 생성
    # (자재원가 변동 시만 동작, 변동 없으면 스킵)
    if getattr(product, 'auto_standard_cost', False):
        _auto_version_standard_cost(product)

    old_cost = product.cost_price

    # 1순위: 현행 표준원가 (위에서 auto-version 됐을 수 있음)
    std_cost = StandardCost.objects.filter(
        product=product, is_current=True, is_active=True,
    ).first()
    if std_cost and std_cost.total_standard_cost > 0:
        if old_cost != std_cost.total_standard_cost:
            Product.objects.filter(pk=product.pk).update(
                cost_price=std_cost.total_standard_cost,
            )
            product.cost_price = std_cost.total_standard_cost
            return True
        return False

    # 2순위: 기본 BOM 자재원가
    default_bom = BOM.objects.filter(
        product=product, is_default=True, is_active=True,
    ).prefetch_related('items__material').first()
    if default_bom:
        bom_cost = default_bom.total_material_cost
        if bom_cost and bom_cost > 0 and old_cost != bom_cost:
            Product.objects.filter(pk=product.pk).update(
                cost_price=int(bom_cost),
            )
            product.cost_price = int(bom_cost)
            # auto_standard_cost: 표준원가 자동 생성 (없었으므로 여기서 생성)
            if getattr(product, 'auto_standard_cost', False):
                _auto_version_standard_cost(product)
            return True

    # 3순위: 기존값 유지 (아무것도 안함)
    return False


def _cascade_cost_to_parents(product_id, _visited=None):
    """자재 원가 변경 → 이 자재를 사용하는 상위 BOM 완제품 원가 자동 재계산.

    반제품→완제품 체인인 경우 다단계로 전파.
    _visited 세트로 무한루프 방지.
    """
    if _visited is None:
        _visited = set()
    if product_id in _visited:
        return
    _visited.add(product_id)

    from apps.production.models import BOMItem

    parent_items = BOMItem.objects.filter(
        material_id=product_id,
        bom__is_default=True,
        bom__is_active=True,
        is_active=True,
    ).select_related('bom__product')

    for item in parent_items:
        parent = item.bom.product
        if parent.pk in _visited:
            continue
        changed = _sync_product_cost_price(parent)
        if changed:
            logger.info(
                'Cost cascaded: material %s → product %s (new cost: %s)',
                product_id, parent.code, parent.cost_price,
            )
            _cascade_cost_to_parents(parent.pk, _visited)


@receiver(post_save, sender='production.BOMItem')
def sync_cost_on_bom_item_save(sender, instance, **kwargs):
    """BOMItem 저장 시 해당 BOM 완제품의 cost_price 동기화 + 캐스케이드"""
    bom = instance.bom
    if bom.is_default and bom.is_active:
        _sync_product_cost_price(bom.product)
        _cascade_cost_to_parents(bom.product.pk)


@receiver(post_delete, sender='production.BOMItem')
def sync_cost_on_bom_item_delete(sender, instance, **kwargs):
    """BOMItem 삭제 시 해당 BOM 완제품의 cost_price 동기화 + 캐스케이드"""
    bom = instance.bom
    if bom.is_default and bom.is_active:
        _sync_product_cost_price(bom.product)
        _cascade_cost_to_parents(bom.product.pk)


@receiver(post_save, sender='production.BOM')
def sync_cost_on_bom_save(sender, instance, **kwargs):
    """BOM 저장 시 (is_default 변경 등) 완제품의 cost_price 동기화 + 캐스케이드"""
    if instance.is_default and instance.is_active:
        _sync_product_cost_price(instance.product)
        _cascade_cost_to_parents(instance.product.pk)


@receiver(post_save, sender='production.QualityInspection')
def notify_conditional_approval(sender, instance, created, **kwargs):
    """조건부합격 검수 등록/변경 시 매니저에게 승인 요청 알림"""
    if instance.result != 'CONDITIONAL':
        return
    # 이미 승인된 경우 알림 불필요
    if instance.conditional_approved_by_id:
        return

    from apps.core.notification import create_notification
    create_notification(
        users='manager',
        title=f'조건부합격 승인 요청: {instance.inspection_number}',
        message=(
            f'제품: {instance.product.name}\n'
            f'검수수량: {instance.inspected_quantity}\n'
            f'사유: {instance.conditional_notes or "미입력"}\n'
            f'매니저 승인이 필요합니다.'
        ),
        noti_type='PRODUCTION',
        link=f'/production/qc/{instance.inspection_number}/',
    )


@receiver(post_save, sender='production.StandardCost')
def sync_cost_on_standard_cost_save(sender, instance, **kwargs):
    """StandardCost 저장 시 완제품의 cost_price 동기화 + 캐스케이드"""
    if instance.is_current and instance.is_active:
        _sync_product_cost_price(instance.product)
        _cascade_cost_to_parents(instance.product.pk)
