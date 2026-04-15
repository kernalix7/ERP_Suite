import logging

from django.db import transaction
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(pre_save, sender='logistics.DeliveryRoute')
def validate_route_status_transition(sender, instance, **kwargs):
    """배송 경로 상태 전환 유효성 검증"""
    if not instance.pk:
        return

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old.status == instance.status:
        return

    valid_transitions = {
        'PLANNED': ['IN_PROGRESS'],
        'IN_PROGRESS': ['COMPLETED'],
        'COMPLETED': [],
    }

    from django.core.exceptions import ValidationError
    allowed = valid_transitions.get(old.status, [])
    if instance.status not in allowed:
        raise ValidationError(
            f'배송 경로 상태를 {old.get_status_display()}에서 '
            f'{instance.get_status_display()}(으)로 변경할 수 없습니다.'
        )


@receiver(post_save, sender='logistics.DeliveryRoute')
def update_vehicle_status_on_route(sender, instance, **kwargs):
    """배송 경로 상태에 따라 차량 상태 자동 업데이트

    - PLANNED → IN_PROGRESS: 차량 상태를 IN_USE로 변경
    - IN_PROGRESS → COMPLETED: 차량 상태를 AVAILABLE로 변경
    """
    from .models import Vehicle

    vehicle = instance.vehicle
    if instance.status == 'IN_PROGRESS' and vehicle.status != Vehicle.VehicleStatus.IN_USE:
        with transaction.atomic():
            Vehicle.objects.filter(pk=vehicle.pk).update(
                status=Vehicle.VehicleStatus.IN_USE,
            )
            logger.info(
                'DeliveryRoute %s IN_PROGRESS → Vehicle %s 상태를 IN_USE로 변경',
                instance.route_number, vehicle.plate_number,
            )

    elif instance.status == 'COMPLETED' and vehicle.status == Vehicle.VehicleStatus.IN_USE:
        with transaction.atomic():
            Vehicle.objects.filter(pk=vehicle.pk).update(
                status=Vehicle.VehicleStatus.AVAILABLE,
            )
            logger.info(
                'DeliveryRoute %s COMPLETED → Vehicle %s 상태를 AVAILABLE로 변경',
                instance.route_number, vehicle.plate_number,
            )


@receiver(pre_save, sender='logistics.RouteStop')
def validate_stop_status_transition(sender, instance, **kwargs):
    """경유지 상태 전환 유효성 검증"""
    if not instance.pk:
        return

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old.status == instance.status:
        return

    valid_transitions = {
        'PENDING': ['ARRIVED', 'SKIPPED'],
        'ARRIVED': ['COMPLETED'],
        'COMPLETED': [],
        'SKIPPED': [],
    }

    from django.core.exceptions import ValidationError
    allowed = valid_transitions.get(old.status, [])
    if instance.status not in allowed:
        raise ValidationError(
            f'경유지 상태를 {old.get_status_display()}에서 '
            f'{instance.get_status_display()}(으)로 변경할 수 없습니다.'
        )
