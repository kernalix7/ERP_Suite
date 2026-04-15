import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='portal.PortalNotification')
def send_portal_notification_email(sender, instance, created, **kwargs):
    """포털 알림 생성 시 이메일 발송 (선택적)"""
    if not created:
        return

    try:
        from apps.core.notification import send_notification
        send_notification(
            user=instance.portal_user.user,
            title=instance.title,
            message=instance.message,
            link=instance.link or '/portal/',
        )
    except Exception:
        logger.exception(
            '포털 알림 이메일 발송 실패: PortalNotification pk=%s', instance.pk,
        )


@receiver(post_save, sender='portal.PortalUser')
def notify_portal_user_verified(sender, instance, **kwargs):
    """포털 사용자 인증 완료 시 환영 알림 생성"""
    if not instance.pk:
        return

    update_fields = kwargs.get('update_fields')
    if update_fields and 'is_verified' not in update_fields:
        return

    if not instance.is_verified:
        return

    from .models import PortalNotification
    if PortalNotification.objects.filter(
        portal_user=instance,
        title__contains='인증 완료',
        is_active=True,
    ).exists():
        return

    try:
        PortalNotification.objects.create(
            portal_user=instance,
            title='포털 인증 완료',
            message=f'{instance.user.get_full_name() or instance.user.username}님, 포털 인증이 완료되었습니다.',
            link='/portal/',
            created_by=instance.created_by,
        )
    except Exception:
        logger.exception('포털 환영 알림 생성 실패: PortalUser pk=%s', instance.pk)
