import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='inquiry.InquiryReply')
def auto_update_inquiry_status_on_reply(sender, instance, created, **kwargs):
    """답변 등록 시 문의 상태 자동 전환

    - 새 답변이 생성되었을 때만
    - RECEIVED/WAITING → REPLIED 자동 전환
    """
    if not created:
        return

    inquiry = instance.inquiry
    if inquiry.status in ('RECEIVED', 'WAITING'):
        from apps.inquiry.models import Inquiry
        Inquiry.objects.filter(pk=inquiry.pk).update(status='REPLIED')
        logger.info(
            'Inquiry %s: 답변 등록 → 상태 REPLIED 자동 전환',
            inquiry.pk,
        )
