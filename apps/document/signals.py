import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import DocumentApproval, DocumentVersion

logger = logging.getLogger(__name__)


@receiver(post_save, sender=DocumentApproval)
def deactivate_previous_versions_on_approval(sender, instance, **kwargs):
    """문서 결재 승인 시 이전 버전 비활성화 + 문서 상태 APPROVED"""
    if instance.status != DocumentApproval.Status.APPROVED:
        return
    if not instance.is_active:
        return

    document = instance.document
    if not document.is_active:
        return

    with transaction.atomic():
        # 현재 버전보다 낮은 버전 비활성화
        deactivated = DocumentVersion.objects.filter(
            document=document,
            is_active=True,
            version_number__lt=document.version,
        ).update(is_active=False)

        if deactivated > 0:
            logger.info(
                'Document %s v%d approved — %d previous version(s) deactivated',
                document.document_number, document.version, deactivated,
            )

        # 문서 상태를 APPROVED로 변경
        if document.status != document.Status.APPROVED:
            document.status = document.Status.APPROVED
            document.save(update_fields=['status', 'updated_at'])
