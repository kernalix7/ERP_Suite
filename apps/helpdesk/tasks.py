import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

_PRIORITY_ESCALATION = {
    'LOW': 'MEDIUM',
    'MEDIUM': 'HIGH',
    'HIGH': 'URGENT',
    'URGENT': 'URGENT',
}


@shared_task(soft_time_limit=300, time_limit=600)
def check_sla_breaches():
    """
    열린 티켓의 SLA 기준시간 초과 여부를 점검하고,
    위반 시 SLABreach 생성, priority 상향, 알림 발송.
    """
    from apps.helpdesk.models import SLABreach, Ticket
    from apps.core.notification import create_notification
    from apps.accounts.models import User

    now = timezone.now()
    open_statuses = [Ticket.Status.OPEN, Ticket.Status.IN_PROGRESS, Ticket.Status.ASSIGNED]

    tickets = (
        Ticket.objects
        .filter(status__in=open_statuses, is_active=True, sla__isnull=False)
        .select_related('sla', 'assigned_to', 'reporter')
    )

    breached_count = 0

    for ticket in tickets:
        sla = ticket.sla
        _check_response_breach(ticket, sla, now, breached_count)
        _check_resolution_breach(ticket, sla, now, breached_count)

    logger.info('SLA 점검 완료: %d건 위반 감지', breached_count)
    return breached_count


def _check_response_breach(ticket, sla, now, counter):
    from apps.helpdesk.models import SLABreach
    from apps.core.notification import create_notification
    from apps.accounts.models import User

    if ticket.sla_response_due and now > ticket.sla_response_due:
        _, created = SLABreach.objects.get_or_create(
            ticket=ticket,
            breach_type=SLABreach.BreachType.RESPONSE,
            defaults={'sla': sla},
        )
        if created:
            _escalate_priority(ticket)
            _notify_admins(ticket, 'RESPONSE', create_notification, User)
            counter += 1


def _check_resolution_breach(ticket, sla, now, counter):
    from apps.helpdesk.models import SLABreach
    from apps.core.notification import create_notification
    from apps.accounts.models import User

    if ticket.sla_resolution_due and now > ticket.sla_resolution_due:
        _, created = SLABreach.objects.get_or_create(
            ticket=ticket,
            breach_type=SLABreach.BreachType.RESOLUTION,
            defaults={'sla': sla},
        )
        if created:
            _escalate_priority(ticket)
            _notify_admins(ticket, 'RESOLUTION', create_notification, User)
            counter += 1


def _escalate_priority(ticket):
    new_priority = _PRIORITY_ESCALATION.get(ticket.priority, ticket.priority)
    if new_priority != ticket.priority:
        ticket.priority = new_priority
        ticket.save(update_fields=['priority', 'updated_at'])
        logger.info(
            '티켓 %s priority 상향: %s → %s',
            ticket.ticket_number, ticket.priority, new_priority,
        )


def _notify_admins(ticket, breach_type_label, create_notification, User):
    from apps.helpdesk.models import SLABreach

    type_display = 'SLA 응답시간' if breach_type_label == 'RESPONSE' else 'SLA 해결시간'
    title = f'[SLA 위반] {ticket.ticket_number} - {type_display} 초과'
    message = (
        f'티켓 {ticket.ticket_number}({ticket.title})의 {type_display}이 초과되었습니다.\n'
        f'우선순위가 {ticket.priority}로 상향 조정되었습니다.'
    )
    admins = User.objects.filter(role__in=['admin', 'manager'], is_active=True)
    if admins.exists():
        create_notification(
            users=list(admins),
            title=title,
            message=message,
            noti_type='SLA_BREACH',
            link=f'/helpdesk/tickets/{ticket.pk}/',
        )
