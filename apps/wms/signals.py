import logging
from datetime import date

from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.inventory.models import Product, StockMovement, Warehouse

logger = logging.getLogger(__name__)


@receiver(post_save, sender='wms.PutAwayTask')
def putaway_completed_stock_in(sender, instance, created, **kwargs):
    """입고적치 완료 시 StockMovement(IN) 생성 + Product.current_stock 갱신"""
    if not instance.status == 'COMPLETED':
        return
    # 상태 변경 시에만 동작 (이미 COMPLETED였으면 스킵)
    if not created:
        try:
            old = sender.all_objects.get(pk=instance.pk)
        except sender.DoesNotExist:
            return
        # pre_save에서 캐시한 이전 상태 활용
        old_status = getattr(instance, '_old_status', None)
        if old_status == 'COMPLETED':
            return

    product = Product.all_objects.get(pk=instance.product_id)
    if not product.is_stockable:
        return

    # actual_bin이 있으면 해당 bin의 zone→warehouse, 없으면 기본 창고
    warehouse = None
    actual_bin = instance.actual_bin or instance.suggested_bin
    if actual_bin:
        warehouse = actual_bin.zone.warehouse
    if not warehouse:
        warehouse = Warehouse.get_default()
    if not warehouse:
        logger.error(
            'No warehouse for PutAwayTask %s — cannot create stock movement',
            instance.pk,
        )
        return

    with transaction.atomic():
        ref = f'입고적치 {instance.pk}'
        if instance.goods_receipt_id:
            ref = f'입고적치 GR-{instance.goods_receipt_id}'

        StockMovement.objects.create(
            movement_type='IN',
            product=instance.product,
            warehouse=warehouse,
            quantity=instance.quantity,
            unit_price=product.cost_price or 0,
            movement_date=date.today(),
            reference=ref,
            created_by=instance.created_by,
        )
        logger.info(
            'PutAwayTask %s completed — IN StockMovement created '
            '(product=%s, qty=%s, warehouse=%s)',
            instance.pk, product.code, instance.quantity, warehouse.code,
        )

        # bin 사용중 마킹
        if actual_bin:
            from apps.wms.models import BinLocation
            BinLocation.objects.filter(pk=actual_bin.pk).update(is_occupied=True)


@receiver(pre_save, sender='wms.PutAwayTask')
def cache_putaway_old_status(sender, instance, **kwargs):
    """PutAwayTask 상태 변경 감지를 위한 이전 상태 캐시"""
    if instance.pk:
        try:
            old = sender.all_objects.get(pk=instance.pk)
            instance._old_status = old.status
        except sender.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender='wms.PickOrder')
def pickorder_completed_stock_out(sender, instance, created, **kwargs):
    """피킹 완료(PACKED/SHIPPED) 시 PickOrderItem별 StockMovement(OUT) 생성"""
    if instance.status not in ('PACKED', 'SHIPPED'):
        return

    old_status = getattr(instance, '_old_status', None)
    if old_status in ('PACKED', 'SHIPPED'):
        return

    with transaction.atomic():
        for item in instance.items.select_related('product', 'bin_location').all():
            product = item.product
            if not product.is_stockable:
                continue

            pick_qty = item.picked_qty if item.picked_qty > 0 else item.quantity
            # bin의 zone→warehouse, 없으면 기본 창고
            warehouse = None
            if item.bin_location:
                warehouse = item.bin_location.zone.warehouse
            if not warehouse:
                warehouse = Warehouse.get_default()
            if not warehouse:
                logger.error(
                    'No warehouse for PickOrderItem %s — skipping',
                    item.pk,
                )
                continue

            StockMovement.objects.create(
                movement_type='OUT',
                product=product,
                warehouse=warehouse,
                quantity=pick_qty,
                unit_price=product.cost_price or 0,
                movement_date=date.today(),
                reference=f'피킹오더 {instance.pick_number}',
                created_by=instance.created_by,
            )
            logger.info(
                'PickOrder %s item — OUT StockMovement '
                '(product=%s, qty=%s)',
                instance.pick_number, product.code, pick_qty,
            )


@receiver(pre_save, sender='wms.PickOrder')
def cache_pickorder_old_status(sender, instance, **kwargs):
    """PickOrder 상태 변경 감지를 위한 이전 상태 캐시"""
    if instance.pk:
        try:
            old = sender.all_objects.get(pk=instance.pk)
            instance._old_status = old.status
        except sender.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender='wms.WavePlan')
def waveplan_released_assign_picking(sender, instance, created, **kwargs):
    """웨이브 확정(RELEASED) 시 연결된 피킹오더 → PICKING 상태 전환"""
    if instance.status != 'RELEASED':
        return

    old_status = getattr(instance, '_old_status', None)
    if old_status == 'RELEASED':
        return

    with transaction.atomic():
        pick_orders = instance.pick_orders.filter(
            status='PENDING', is_active=True,
        )
        updated = pick_orders.update(status='PICKING')
        logger.info(
            'WavePlan %s released — %d pick orders set to PICKING',
            instance.wave_number, updated,
        )


@receiver(pre_save, sender='wms.WavePlan')
def cache_waveplan_old_status(sender, instance, **kwargs):
    """WavePlan 상태 변경 감지를 위한 이전 상태 캐시"""
    if instance.pk:
        try:
            old = sender.all_objects.get(pk=instance.pk)
            instance._old_status = old.status
        except sender.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None
