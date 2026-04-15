import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def check_preventive_maintenance():
    """매일 실행: 예방보전 예정일 도래 시 WorkOrder 자동 생성"""
    from apps.cmms.models import MaintenanceSchedule, MaintenanceWorkOrder

    today = timezone.now().date()
    due_schedules = MaintenanceSchedule.objects.filter(
        is_active=True,
        next_due__lte=today,
    ).select_related('equipment', 'assigned_to')

    created_count = 0
    for schedule in due_schedules:
        # 이미 미완료 작업지시가 있으면 스킵
        existing_open = MaintenanceWorkOrder.objects.filter(
            schedule=schedule,
            status__in=['OPEN', 'IN_PROGRESS'],
            is_active=True,
        ).exists()
        if existing_open:
            continue

        wo = MaintenanceWorkOrder.objects.create(
            schedule=schedule,
            equipment=schedule.equipment,
            status=MaintenanceWorkOrder.Status.OPEN,
            priority=MaintenanceWorkOrder.Priority.NORMAL,
            description=f'예방보전: {schedule.title}',
            assigned_to=schedule.assigned_to,
        )
        created_count += 1
        logger.info(
            'PM WorkOrder %s created for schedule %s (equipment=%s, due=%s)',
            wo.wo_number, schedule.pk, schedule.equipment.code, schedule.next_due,
        )

    logger.info(
        'check_preventive_maintenance completed — %d work orders created',
        created_count,
    )
    return created_count
