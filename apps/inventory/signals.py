import logging
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

from .models import Product, StockMovement, StockTransfer, StockLot, WarehouseStock


logger = logging.getLogger(__name__)

INBOUND_TYPES = {'IN', 'ADJ_PLUS', 'PROD_IN', 'RETURN'}
OUTBOUND_TYPES = {'OUT', 'ADJ_MINUS', 'PROD_OUT'}
LOT_INBOUND_TYPES = {'IN', 'PROD_IN', 'RETURN'}


def _update_warehouse_stock(warehouse_id, product_id, quantity, add=True):
    """창고별 재고 원자적 갱신 (WarehouseStock upsert)"""
    if add:
        ws, created = WarehouseStock.objects.get_or_create(
            warehouse_id=warehouse_id,
            product_id=product_id,
            defaults={'quantity': quantity},
        )
        if not created:
            WarehouseStock.objects.filter(pk=ws.pk).update(
                quantity=F('quantity') + quantity,
            )
    else:
        try:
            ws = WarehouseStock.objects.get(
                warehouse_id=warehouse_id,
                product_id=product_id,
            )
            WarehouseStock.objects.filter(pk=ws.pk).update(
                quantity=F('quantity') - quantity,
            )
        except WarehouseStock.DoesNotExist:
            # 창고별 재고 없으면 로깅만 (글로벌 재고만 차감)
            logger.warning(
                'WarehouseStock not found for wh=%s product=%s'
                ' — skipping warehouse stock deduction',
                warehouse_id, product_id,
            )


def _update_weighted_avg_cost(product_id, in_qty, in_price):
    """이동평균단가 계산: (기존재고×기존원가 + 입고수량×입고단가) ÷ 총수량

    입고(IN, PROD_IN) 시그널에서 current_stock UPDATE 직전에 호출.
    current_stock은 아직 갱신 전이므로 그대로 '기존재고'로 사용.
    """
    product = Product.objects.select_for_update().get(pk=product_id)
    existing_stock = max(product.current_stock, 0)
    existing_cost = product.cost_price or Decimal('0')

    total_value = (existing_stock * existing_cost
                   + in_qty * Decimal(str(in_price)))
    total_qty = existing_stock + in_qty

    if total_qty > 0:
        new_cost = (total_value / total_qty).quantize(
            Decimal('1'), rounding=ROUND_HALF_UP,
        )
        Product.objects.filter(pk=product_id).update(
            cost_price=new_cost,
        )
        logger.info(
            'Weighted avg cost updated: %s %s → %s '
            '(+%s @ %s)',
            product.code, existing_cost, new_cost,
            in_qty, in_price,
        )


def _generate_lot_number(product, date):
    """LOT번호 자동 채번: LOT-{product.code}-{YYYYMMDD}-{sequence}"""
    date_str = date.strftime('%Y%m%d')
    prefix = f'LOT-{product.code}-{date_str}-'
    last = (
        StockLot.all_objects
        .filter(lot_number__startswith=prefix)
        .order_by('-lot_number')
        .values_list('lot_number', flat=True)
        .first()
    )
    if last:
        seq = int(last.split('-')[-1]) + 1
    else:
        seq = 1
    return f'{prefix}{seq:03d}'


def _create_lot_on_inbound(instance):
    """입고(IN, PROD_IN, RETURN) 시 StockLot 자동 생성"""
    if instance.movement_type not in LOT_INBOUND_TYPES:
        return None

    product = Product.all_objects.get(pk=instance.product_id)
    lot_number = _generate_lot_number(product, instance.movement_date)
    unit_cost = instance.unit_price if instance.unit_price else product.cost_price

    lot = StockLot.objects.create(
        lot_number=lot_number,
        product_id=instance.product_id,
        warehouse_id=instance.warehouse_id,
        initial_quantity=instance.quantity,
        remaining_quantity=instance.quantity,
        unit_cost=unit_cost,
        received_date=instance.movement_date,
        stock_movement=instance,
    )
    logger.info(
        'StockLot created: %s (product=%s, qty=%s, cost=%s)',
        lot.lot_number, product.code, instance.quantity, unit_cost,
    )
    return lot


def _consume_lots_on_outbound(instance):
    """출고(OUT, PROD_OUT, ADJ_MINUS) 시 product.valuation_method에 따라 LOT 소진

    FIFO: received_date ASC 순 (오래된 것부터)
    LIFO: received_date DESC 순 (최근 것부터)
    AVG: received_date ASC 순으로 비례 분배 (LOT 생성만, 소진은 비례)

    Returns:
        출고 원가 (각 LOT unit_cost 기반 가중평균)
    """
    if instance.movement_type not in OUTBOUND_TYPES:
        return None

    product = Product.all_objects.get(pk=instance.product_id)
    remaining_to_consume = instance.quantity

    # LOT 정렬 순서 결정
    if product.valuation_method == 'LIFO':
        ordering = ['-received_date', '-pk']
    else:
        # FIFO 및 AVG 모두 오래된 것부터
        ordering = ['received_date', 'pk']

    lots = (
        StockLot.objects
        .filter(
            product_id=instance.product_id,
            warehouse_id=instance.warehouse_id,
            remaining_quantity__gt=0,
            is_active=True,
        )
        .order_by(*ordering)
        .select_for_update()
    )

    total_cost = Decimal('0')
    total_consumed = Decimal('0')

    for lot in lots:
        if remaining_to_consume <= 0:
            break

        consume_qty = min(lot.remaining_quantity, remaining_to_consume)
        total_cost += consume_qty * lot.unit_cost
        total_consumed += consume_qty
        remaining_to_consume -= consume_qty

        StockLot.objects.filter(pk=lot.pk).update(
            remaining_quantity=F('remaining_quantity') - consume_qty,
        )
        logger.info(
            'LOT consumed: %s -%s (remaining after: %s)',
            lot.lot_number, consume_qty,
            lot.remaining_quantity - consume_qty,
        )

    if remaining_to_consume > 0:
        logger.warning(
            'LOT shortage: product=%s, requested=%s, consumed=%s, deficit=%s',
            product.code, instance.quantity, total_consumed, remaining_to_consume,
        )

    # 가중평균 출고원가 반환
    if total_consumed > 0:
        weighted_avg_cost = (total_cost / total_consumed).quantize(
            Decimal('1'), rounding=ROUND_HALF_UP,
        )
        return weighted_avg_cost
    return None


@receiver(post_save, sender=StockMovement)
def update_stock_on_save(sender, instance, created, **kwargs):
    """입출고 생성 시 F() 표현식으로 원자적 재고 갱신 (레이스 컨디션 방지)"""
    if not created:
        return

    # C1: 출고 시 재고 부족 경고 로깅
    if instance.movement_type in OUTBOUND_TYPES:
        product = Product.all_objects.get(pk=instance.product_id)
        if product.current_stock < instance.quantity:
            logger.warning(
                'Stock going negative: %s (current: %s, out: %s)',
                product.code, product.current_stock, instance.quantity,
            )

    with transaction.atomic():
        if instance.movement_type in INBOUND_TYPES:
            # 이동평균단가 계산 (입고 시 unit_price가 있을 때만)
            # 창고간이동(StockTransfer) IN은 단가 재계산 스킵
            is_transfer = (
                getattr(instance, 'reference', '') == '창고간이동'
                or (instance.reference and '창고이동' in instance.reference)
                or (instance.movement_number
                    and instance.movement_number.startswith('TF-'))
            )
            if (instance.unit_price and instance.unit_price > 0
                    and instance.movement_type in ('IN', 'PROD_IN')
                    and not is_transfer):
                _update_weighted_avg_cost(
                    instance.product_id, instance.quantity,
                    instance.unit_price,
                )
            Product.objects.filter(pk=instance.product_id).update(
                current_stock=F('current_stock') + instance.quantity
            )
            _update_warehouse_stock(
                instance.warehouse_id, instance.product_id,
                instance.quantity, add=True,
            )
            # LOT 자동 생성 (IN, PROD_IN, RETURN)
            _create_lot_on_inbound(instance)

        elif instance.movement_type in OUTBOUND_TYPES:
            Product.objects.filter(pk=instance.product_id).update(
                current_stock=F('current_stock') - instance.quantity
            )
            _update_warehouse_stock(
                instance.warehouse_id, instance.product_id,
                instance.quantity, add=False,
            )
            # LOT 소진 (FIFO/LIFO/AVG)
            _consume_lots_on_outbound(instance)


@receiver(post_delete, sender=StockMovement)
def update_stock_on_delete(sender, instance, **kwargs):
    """입출고 삭제 시 원자적 재고 복원"""
    with transaction.atomic():
        if instance.movement_type in INBOUND_TYPES:
            Product.objects.filter(pk=instance.product_id).update(
                current_stock=F('current_stock') - instance.quantity
            )
            _update_warehouse_stock(
                instance.warehouse_id, instance.product_id,
                instance.quantity, add=False,
            )
        elif instance.movement_type in OUTBOUND_TYPES:
            Product.objects.filter(pk=instance.product_id).update(
                current_stock=F('current_stock') + instance.quantity
            )
            _update_warehouse_stock(
                instance.warehouse_id, instance.product_id,
                instance.quantity, add=True,
            )


def _soft_delete_lots_on_inbound_cancel(movement):
    """입고 soft delete 시 연결된 StockLot도 soft delete"""
    lots = StockLot.objects.filter(
        stock_movement=movement,
        is_active=True,
    )
    for lot in lots:
        lot.is_active = False
        lot.save(update_fields=['is_active', 'updated_at'])
        logger.info(
            'StockLot soft deleted: %s (inbound movement %s cancelled)',
            lot.lot_number, movement.movement_number,
        )


def _restore_lots_on_outbound_cancel(movement):
    """출고 soft delete 시 소진된 StockLot의 remaining_quantity 복원

    consumption과 동일한 순서(FIFO/LIFO)로 LOT를 찾아 복원한다.
    consumed_qty = initial_quantity - remaining_quantity인 LOT에 수량 복원.
    """
    product = Product.all_objects.get(pk=movement.product_id)
    remaining_to_restore = movement.quantity

    # 소진 시 사용한 것과 같은 정렬
    if product.valuation_method == 'LIFO':
        ordering = ['-received_date', '-pk']
    else:
        ordering = ['received_date', 'pk']

    lots = (
        StockLot.objects
        .filter(
            product_id=movement.product_id,
            warehouse_id=movement.warehouse_id,
            is_active=True,
        )
        .exclude(remaining_quantity=F('initial_quantity'))
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
            remaining_quantity=F('remaining_quantity') + restore_qty,
        )
        logger.info(
            'StockLot restored: %s +%s (outbound movement %s cancelled)',
            lot.lot_number, restore_qty, movement.movement_number,
        )

    if remaining_to_restore > 0:
        logger.warning(
            'LOT restore incomplete: product=%s, movement=%s, unrestored=%s',
            product.code, movement.movement_number, remaining_to_restore,
        )


@receiver(pre_save, sender=StockMovement)
def reverse_stock_on_soft_delete(sender, instance, **kwargs):
    """입출고 soft-delete(비활성화) 시 재고 복원"""
    if not instance.pk:
        return
    try:
        old = StockMovement.all_objects.get(pk=instance.pk)
    except StockMovement.DoesNotExist:
        return

    # Only trigger when is_active changes from True to False
    if old.is_active and not instance.is_active:
        with transaction.atomic():
            if old.movement_type in INBOUND_TYPES:
                # 입고 취소 시 이동평균단가 역산
                if (old.unit_price and old.unit_price > 0
                        and old.movement_type in ('IN', 'PROD_IN')):
                    # 창고간이동은 스킵
                    is_transfer = (
                        (old.reference and '창고이동' in old.reference)
                        or (old.movement_number
                            and old.movement_number.startswith('TF-'))
                    )
                    if not is_transfer:
                        product = Product.objects.select_for_update().get(
                            pk=old.product_id,
                        )
                        old_stock = product.current_stock
                        old_cost = product.cost_price or Decimal('0')
                        new_stock = old_stock - old.quantity
                        if new_stock > 0:
                            new_cost = (
                                (old_stock * old_cost
                                 - old.quantity * old.unit_price)
                                / new_stock
                            ).quantize(
                                Decimal('1'), rounding=ROUND_HALF_UP,
                            )
                            Product.objects.filter(
                                pk=old.product_id,
                            ).update(cost_price=new_cost)
                        # new_stock <= 0: cost_price 유지

                Product.objects.filter(pk=old.product_id).update(
                    current_stock=F('current_stock') - old.quantity
                )
                _update_warehouse_stock(
                    old.warehouse_id, old.product_id,
                    old.quantity, add=False,
                )
                # 입고 삭제 시 연결된 StockLot soft delete
                _soft_delete_lots_on_inbound_cancel(old)
            elif old.movement_type in OUTBOUND_TYPES:
                Product.objects.filter(pk=old.product_id).update(
                    current_stock=F('current_stock') + old.quantity
                )
                _update_warehouse_stock(
                    old.warehouse_id, old.product_id,
                    old.quantity, add=True,
                )
                # 출고 삭제 시 소진된 StockLot 복원
                _restore_lots_on_outbound_cancel(old)


@receiver(post_save, sender=StockTransfer)
def create_transfer_movements(sender, instance, created, **kwargs):
    """창고간이동 시 출발창고 OUT + 도착창고 IN 자동 생성"""
    if not created:
        return
    with transaction.atomic():
        # OUT from source warehouse
        StockMovement.objects.create(
            movement_number=f'TF-OUT-{instance.transfer_number}',
            movement_type='OUT',
            product=instance.product,
            warehouse=instance.from_warehouse,
            quantity=instance.quantity,
            unit_price=instance.product.cost_price,
            movement_date=instance.transfer_date,
            reference=f'창고이동 {instance.transfer_number}',
            created_by=instance.created_by,
        )
        # IN to destination warehouse
        StockMovement.objects.create(
            movement_number=f'TF-IN-{instance.transfer_number}',
            movement_type='IN',
            product=instance.product,
            warehouse=instance.to_warehouse,
            quantity=instance.quantity,
            unit_price=instance.product.cost_price,
            movement_date=instance.transfer_date,
            reference=f'창고이동 {instance.transfer_number}',
            created_by=instance.created_by,
        )
