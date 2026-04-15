import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


@receiver(pre_save, sender='edi.EDITransaction')
def validate_edi_status_transition(sender, instance, **kwargs):
    """EDI 트랜잭션 상태 전환 유효성 검증"""
    if not instance.pk:
        return

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old.status == instance.status:
        return

    valid_transitions = {
        'PENDING': ['SENT', 'RECEIVED', 'ERROR'],
        'SENT': ['PROCESSED', 'ERROR'],
        'RECEIVED': ['PROCESSED', 'ERROR'],
        'PROCESSED': [],
        'ERROR': ['PENDING'],
    }

    from django.core.exceptions import ValidationError
    allowed = valid_transitions.get(old.status, [])
    if instance.status not in allowed:
        raise ValidationError(
            f'EDI 트랜잭션 상태를 {old.get_status_display()}에서 '
            f'{instance.get_status_display()}(으)로 변경할 수 없습니다.'
        )


@receiver(post_save, sender='edi.EDITransaction')
def set_processed_at_on_complete(sender, instance, **kwargs):
    """EDI 트랜잭션 PROCESSED 상태 전환 시 처리일시 자동 설정"""
    update_fields = kwargs.get('update_fields')
    if instance.status != 'PROCESSED':
        return
    if instance.processed_at:
        return
    if update_fields and 'processed_at' in update_fields:
        return

    with transaction.atomic():
        sender.objects.filter(pk=instance.pk).update(
            processed_at=timezone.now(),
        )
        logger.info(
            'EDITransaction %s PROCESSED → processed_at 자동 설정',
            instance.transaction_id,
        )


@receiver(post_save, sender='edi.EDITransaction')
def notify_on_edi_error(sender, instance, **kwargs):
    """EDI 트랜잭션 오류 발생 시 알림"""
    if instance.status != 'ERROR':
        return

    logger.warning(
        'EDITransaction %s ERROR: %s',
        instance.transaction_id,
        instance.error_message or '오류 메시지 없음',
    )
