import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.accounts.models import User

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=User)
def sync_ad_on_user_deactivation(sender, instance, **kwargs):
    """ERP 사용자가 비활성화되면 AD 매핑도 비활성화 상태로 전환"""
    if not instance.pk:
        return

    try:
        old_user = User.objects.get(pk=instance.pk)
    except User.DoesNotExist:
        return

    if old_user.is_active and not instance.is_active:
        # 사용자가 비활성화됨 → AD 매핑 상태 갱신
        from .models import ADUserMapping
        ADUserMapping.objects.filter(user=instance).update(
            sync_status='DISABLED',
        )
        logger.info('AD 매핑 비활성화: user=%s', instance.username)
