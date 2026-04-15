"""Security signals: password history recording on password change."""
import logging

from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save
from django.dispatch import receiver

logger = logging.getLogger('django.security')
User = get_user_model()


@receiver(pre_save, sender=User)
def record_password_history(sender, instance, **kwargs):
    """비밀번호 변경 시 이력 기록"""
    if not instance.pk:
        return
    try:
        old_user = User.objects.get(pk=instance.pk)
    except User.DoesNotExist:
        return
    if old_user.password != instance.password:
        from apps.accounts.models import PasswordHistory
        PasswordHistory.objects.create(
            user=instance,
            password_hash=instance.password,
        )
