from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import Product, StockMovement


INBOUND_TYPES = {'IN', 'ADJ_PLUS', 'PROD_IN', 'RETURN'}
OUTBOUND_TYPES = {'OUT', 'ADJ_MINUS', 'PROD_OUT'}


@receiver(post_save, sender=StockMovement)
def update_stock_on_save(sender, instance, created, **kwargs):
    """입출고 생성 시 F() 표현식으로 원자적 재고 갱신 (레이스 컨디션 방지)"""
    if not created:
        return
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
