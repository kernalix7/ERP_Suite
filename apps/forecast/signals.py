import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import DemandForecast, SOPMeeting

logger = logging.getLogger(__name__)


@receiver(post_save, sender=DemandForecast)
def update_forecast_accuracy(sender, instance, created, **kwargs):
    """실적 수량 입력 시 정확도 자동 재계산"""
    if not created and instance.actual_qty and instance.forecast_qty:
        old_accuracy = instance.accuracy_pct
        instance.calculate_accuracy()
        if instance.accuracy_pct != old_accuracy:
            DemandForecast.objects.filter(pk=instance.pk).update(
                accuracy_pct=instance.accuracy_pct,
            )
            logger.info(
                'forecast=%s accuracy updated: %s%%',
                instance.pk, instance.accuracy_pct,
            )


@receiver(post_save, sender=SOPMeeting)
def notify_sop_status_change(sender, instance, created, **kwargs):
    """S&OP 회의 상태 변경 시 알림 생성"""
    if created:
        return

    if instance.status == SOPMeeting.Status.APPROVED:
        try:
            from apps.core.notification import create_notification
            create_notification(
                users='managers',
                title=f'S&OP 회의 승인: {instance.title}',
                message=f'{instance.title} ({instance.meeting_date}) 회의가 승인되었습니다.',
            )
        except Exception:
            logger.exception('SOP meeting notification failed for pk=%s', instance.pk)
