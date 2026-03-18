import logging

from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

from .models import Product, StockMovement, StockTransfer


logger = logging.getLogger(__name__)

INBOUND_TYPES = {'IN', 'ADJ_PLUS', 'PROD_IN', 'RETURN'}
OUTBOUND_TYPES = {'OUT', 'ADJ_MINUS', 'PROD_OUT'}


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
                'Stock going negative: %s (current: %d, out: %d)',
                product.code, product.current_stock, instance.quantity,
            )

    with transaction.atomic():
        if instance.movement_type in INBOUND_TYPES:
            Product.objects.filter(pk=instance.product_id).update(
                current_stock=F('current_stock') + instance.quantity
            )
        elif instance.movement_type in OUTBOUND_TYPES:
            Product.objects.filter(pk=instance.product_id).update(
                current_stock=F('current_stock') - instance.quantity
            )


@receiver(post_delete, sender=StockMovement)
def update_stock_on_delete(sender, instance, **kwargs):
    """입출고 삭제 시 원자적 재고 복원"""
    with transaction.atomic():
        if instance.movement_type in INBOUND_TYPES:
            Product.objects.filter(pk=instance.product_id).update(
                current_stock=F('current_stock') - instance.quantity
            )
        elif instance.movement_type in OUTBOUND_TYPES:
            Product.objects.filter(pk=instance.product_id).update(
                current_stock=F('current_stock') + instance.quantity
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
                Product.objects.filter(pk=old.product_id).update(
                    current_stock=F('current_stock') - old.quantity
                )
            elif old.movement_type in OUTBOUND_TYPES:
                Product.objects.filter(pk=old.product_id).update(
                    current_stock=F('current_stock') + old.quantity
                )


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
