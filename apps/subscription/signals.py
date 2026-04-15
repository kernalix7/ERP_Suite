import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(pre_save, sender='subscription.Subscription')
def validate_subscription_status_transition(sender, instance, **kwargs):
    """구독 상태 전환 유효성 검증"""
    if not instance.pk:
        return

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old.status == instance.status:
        return

    valid_transitions = {
        'TRIAL': ['ACTIVE', 'CANCELLED'],
        'ACTIVE': ['PAUSED', 'CANCELLED'],
        'PAUSED': ['ACTIVE', 'CANCELLED'],
        'CANCELLED': [],
        'EXPIRED': [],
    }

    from django.core.exceptions import ValidationError
    allowed = valid_transitions.get(old.status, [])
    if instance.status not in allowed:
        raise ValidationError(
            f'구독 상태를 {old.get_status_display()}에서 '
            f'{instance.get_status_display()}(으)로 변경할 수 없습니다.'
        )


@receiver(pre_save, sender='subscription.BillingRecord')
def validate_billing_status_transition(sender, instance, **kwargs):
    """과금 기록 상태 전환 유효성 검증"""
    if not instance.pk:
        return

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old.status == instance.status:
        return

    valid_transitions = {
        'PENDING': ['INVOICED', 'OVERDUE'],
        'INVOICED': ['PAID', 'OVERDUE'],
        'OVERDUE': ['PAID'],
        'PAID': [],
    }

    from django.core.exceptions import ValidationError
    allowed = valid_transitions.get(old.status, [])
    if instance.status not in allowed:
        raise ValidationError(
            f'과금 기록 상태를 {old.get_status_display()}에서 '
            f'{instance.get_status_display()}(으)로 변경할 수 없습니다.'
        )


@receiver(post_save, sender='subscription.Subscription')
def notify_on_subscription_cancelled(sender, instance, **kwargs):
    """구독 해지 시 알림"""
    update_fields = kwargs.get('update_fields')
    if update_fields and 'status' not in update_fields:
        return

    if instance.status != 'CANCELLED':
        return

    logger.info(
        'Subscription %s CANCELLED (거래처: %s, 사유: %s)',
        instance.subscription_number,
        instance.partner.name if instance.partner_id else '미설정',
        instance.cancel_reason or '없음',
    )

    try:
        from apps.core.notification import send_notification
        from apps.accounts.models import User
        admins = User.objects.filter(role__in=['admin', 'manager'], is_active=True)
        for admin in admins:
            send_notification(
                user=admin,
                title=f'구독 해지: {instance.subscription_number}',
                message=f'{instance.partner.name if instance.partner_id else ""} 구독이 해지되었습니다.',
                link=f'/subscription/{instance.pk}/',
            )
    except Exception:
        logger.exception('구독 해지 알림 발송 실패: %s', instance.subscription_number)
