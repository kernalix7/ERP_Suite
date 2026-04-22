import logging
from datetime import timedelta

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


@receiver(pre_save, sender='cmms.MaintenanceWorkOrder')
def cache_mwo_old_status(sender, instance, **kwargs):
    """MaintenanceWorkOrder 상태 변경 감지를 위한 이전 상태 캐시"""
    if instance.pk:
        try:
            old = sender.all_objects.get(pk=instance.pk)
            instance._old_status = old.status
        except sender.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender='cmms.MaintenanceWorkOrder')
def mwo_completed_update_equipment(sender, instance, created, **kwargs):
    """보전작업 완료 시 설비상태 ACTIVE 복원 + 다음 PM 일정 자동 생성"""
    if instance.status != 'COMPLETED':
        return

    old_status = getattr(instance, '_old_status', None)
    if old_status == 'COMPLETED':
        return

    with transaction.atomic():
        from apps.cmms.models import Equipment, MaintenanceSchedule

        # 설비 상태를 ACTIVE로 복원
        Equipment.objects.filter(pk=instance.equipment_id).update(
            status=Equipment.Status.ACTIVE,
        )
        logger.info(
            'MWO %s completed — equipment %s status → ACTIVE',
            instance.wo_number, instance.equipment.code,
        )

        # 연결된 보전스케줄이 있으면 다음 예정일 갱신
        schedule = instance.schedule
        if schedule:
            today = timezone.localdate()
            next_due = today + timedelta(days=schedule.frequency_days)
            MaintenanceSchedule.objects.filter(pk=schedule.pk).update(
                last_performed=today,
                next_due=next_due,
            )
            logger.info(
                'Schedule %s updated — last_performed=%s, next_due=%s',
                schedule.pk, today, next_due,
            )


@receiver(pre_save, sender='cmms.Equipment')
def cache_equipment_old_status(sender, instance, **kwargs):
    """Equipment 상태 변경 감지를 위한 이전 상태 캐시"""
    if instance.pk:
        try:
            old = sender.all_objects.get(pk=instance.pk)
            instance._old_status = old.status
        except sender.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender='cmms.Equipment')
def equipment_breakdown_auto_corrective(sender, instance, created, **kwargs):
    """설비 고장(MAINTENANCE) 시 긴급 보전작업지시 자동 생성 + 관리자 알림"""
    if instance.status != 'MAINTENANCE':
        return

    old_status = getattr(instance, '_old_status', None)
    if old_status == 'MAINTENANCE':
        return

    with transaction.atomic():
        from apps.cmms.models import MaintenanceWorkOrder, EquipmentDowntime

        # 긴급 보전 작업지시 생성
        wo = MaintenanceWorkOrder.objects.create(
            equipment=instance,
            status=MaintenanceWorkOrder.Status.OPEN,
            priority=MaintenanceWorkOrder.Priority.EMERGENCY,
            description=f'설비 고장 긴급 보전: {instance.name} ({instance.code})',
            created_by=instance.created_by,
        )
        logger.info(
            'Equipment %s → MAINTENANCE — emergency MWO %s created',
            instance.code, wo.wo_number,
        )

        # 비가동 기록 시작
        EquipmentDowntime.objects.create(
            equipment=instance,
            start_time=timezone.now(),
            reason=f'설비 고장 (자동 기록)',
            work_order=wo,
            created_by=instance.created_by,
        )

        # 관리자 알림
        try:
            from apps.core.notification import create_notification
            create_notification(
                users='admin',
                title=f'설비 고장: {instance.code} {instance.name}',
                message=(
                    f'설비 {instance.code}({instance.name})이 고장 상태로 전환되었습니다.\n'
                    f'긴급 보전작업지시 {wo.wo_number}가 자동 생성되었습니다.'
                ),
                noti_type='SYSTEM',
            )
        except Exception:
            logger.warning(
                'Failed to send breakdown notification for %s',
                instance.code, exc_info=True,
            )
