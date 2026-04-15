import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


@receiver(pre_save, sender='helpdesk.Ticket')
def validate_ticket_status_transition(sender, instance, **kwargs):
    """티켓 상태 전환 유효성 검증"""
    if not instance.pk:
        return

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old.status == instance.status:
        return

    valid_transitions = {
        'OPEN': ['ASSIGNED', 'IN_PROGRESS', 'CLOSED'],
        'ASSIGNED': ['IN_PROGRESS', 'WAITING', 'OPEN'],
        'IN_PROGRESS': ['WAITING', 'RESOLVED', 'OPEN'],
        'WAITING': ['IN_PROGRESS', 'RESOLVED'],
        'RESOLVED': ['CLOSED', 'IN_PROGRESS'],
        'CLOSED': [],
    }

    from django.core.exceptions import ValidationError
    allowed = valid_transitions.get(old.status, [])
    if instance.status not in allowed:
        raise ValidationError(
            f'티켓 상태를 {old.get_status_display()}에서 '
            f'{instance.get_status_display()}(으)로 변경할 수 없습니다.'
        )


@receiver(post_save, sender='helpdesk.Ticket')
def notify_on_ticket_assignment(sender, instance, created, **kwargs):
    """담당자 배정 또는 변경 시 알림 발송"""
    if not instance.assigned_to_id:
        return

    if created:
        # 신규 티켓에 담당자가 있으면 알림
        _send_ticket_notification(instance, instance.assigned_to)
        return

    # 담당자 변경 감지는 pre_save에서 처리하지 않고 post_save에서 단순화
    # (update_fields로 저장된 경우 등 edge case 방지)


def _send_ticket_notification(ticket, user):
    """티켓 알림 발송 헬퍼"""
    try:
        from apps.core.notification import send_notification
        send_notification(
            user=user,
            title=f'헬프데스크 티켓 배정: {ticket.ticket_number}',
            message=f'[{ticket.get_priority_display()}] {ticket.title}',
            link=f'/helpdesk/{ticket.pk}/',
        )
    except Exception:
        logger.exception('티켓 알림 발송 실패: %s', ticket.ticket_number)


@receiver(post_save, sender='helpdesk.Ticket')
def auto_set_sla_due_on_create(sender, instance, created, **kwargs):
    """티켓 생성 시 SLA 기한 자동 설정"""
    if not created or not instance.sla_id:
        return
    if instance.sla_response_due and instance.sla_resolution_due:
        return

    now = timezone.now()
    updates = {}
    if not instance.sla_response_due:
        updates['sla_response_due'] = now + timezone.timedelta(
            hours=instance.sla.response_time_hours,
        )
    if not instance.sla_resolution_due:
        updates['sla_resolution_due'] = now + timezone.timedelta(
            hours=instance.sla.resolution_time_hours,
        )

    if updates:
        with transaction.atomic():
            sender.objects.filter(pk=instance.pk).update(**updates)
