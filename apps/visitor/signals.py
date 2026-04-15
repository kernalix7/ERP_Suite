from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import VisitRequest


@receiver(post_save, sender=VisitRequest)
def notify_visit_approved(sender, instance, **kwargs):
    """VisitRequest가 APPROVED 상태로 저장되면 호스트(host)에게 알림."""
    if instance.status != VisitRequest.Status.APPROVED:
        return
    try:
        from apps.core.notification import create_notification
        create_notification(
            users=[instance.host],
            title=f'방문 예약 승인: {instance.visitor.name}',
            message=(
                f'방문 예약 [{instance.visit_number}]이 승인되었습니다.\n'
                f'방문자: {instance.visitor.name} ({instance.visitor.company or "-"})\n'
                f'예정일시: {instance.scheduled_at:%Y-%m-%d %H:%M}'
            ),
            noti_type='SYSTEM',
            link=f'/visitor/visit-request/{instance.pk}/',
        )
    except Exception:
        pass
