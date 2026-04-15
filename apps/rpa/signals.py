import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.rpa.models import AutomationRule, AutomationSchedule

logger = logging.getLogger(__name__)


@receiver(post_save, sender=AutomationRule)
def update_schedule_on_rule_toggle(sender, instance, **kwargs):
    """Rule 활성화/비활성화 시 연결된 스케줄 상태 업데이트"""
    try:
        schedule = instance.schedule
    except AutomationSchedule.DoesNotExist:
        return

    if not instance.is_active and not schedule.is_paused:
        schedule.is_paused = True
        schedule.save(update_fields=['is_paused', 'updated_at'])
        logger.info('Schedule paused: rule=%s deactivated', instance.name)
    elif instance.is_active and schedule.is_paused:
        schedule.is_paused = False
        schedule.save(update_fields=['is_paused', 'updated_at'])
        logger.info('Schedule resumed: rule=%s activated', instance.name)
