import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import BOMRevision, Drawing, EngineeringChangeNotice, ProductVersion

logger = logging.getLogger(__name__)


@receiver(post_save, sender=EngineeringChangeNotice)
def ecn_approved_create_bom_revision(sender, instance, **kwargs):
    """ECN 승인(APPROVED) 시 → 관련 제품 BOM의 새 리비전 생성"""
    if not instance.is_active:
        return

    if instance.status != EngineeringChangeNotice.Status.APPROVED:
        return

    from apps.production.models import BOM

    with transaction.atomic():
        products = instance.affected_products.all()
        for product in products:
            boms = BOM.objects.filter(product=product, is_active=True)
            for bom in boms:
                last_rev = BOMRevision.objects.filter(
                    bom=bom, is_active=True,
                ).order_by('-revision_number').first()
                next_rev_num = '1'
                if last_rev:
                    try:
                        next_rev_num = str(int(last_rev.revision_number) + 1)
                    except ValueError:
                        next_rev_num = f'{last_rev.revision_number}.1'

                existing = BOMRevision.objects.filter(
                    bom=bom, revision_number=next_rev_num, is_active=True,
                ).exists()
                if not existing:
                    rev = BOMRevision.objects.create(
                        bom=bom,
                        revision_number=next_rev_num,
                        status=BOMRevision.Status.DRAFT,
                        change_reason=f'ECN {instance.ecn_number}: {instance.title}',
                    )
                    logger.info(
                        'BOMRevision %s created for BOM %s from ECN %s',
                        rev.revision_number, bom, instance.ecn_number,
                    )


@receiver(post_save, sender=ProductVersion)
def product_version_activate(sender, instance, **kwargs):
    """ProductVersion is_active=True 설정 시 → 같은 product의 다른 버전 비활성화"""
    if not instance.is_active:
        return

    with transaction.atomic():
        deactivated = ProductVersion.objects.filter(
            product=instance.product,
            is_active=True,
        ).exclude(pk=instance.pk).update(is_active=False)

        if deactivated:
            logger.info(
                'ProductVersion %s activated — %d other version(s) deactivated '
                'for product %s',
                instance.version_number, deactivated, instance.product,
            )


@receiver(pre_save, sender=Drawing)
def drawing_auto_increment_revision(sender, instance, **kwargs):
    """Drawing 파일 변경 시 revision 자동 +1

    file 필드가 변경된 경우 (기존 레코드) revision을 1 증가시킨다.
    revision이 숫자 형식이면 정수 +1, 알파벳이면 다음 문자로 증가.
    """
    if not instance.pk:
        return

    try:
        old = Drawing.objects.get(pk=instance.pk)
    except Drawing.DoesNotExist:
        return

    if old.file and instance.file and old.file.name != instance.file.name:
        current_rev = instance.revision
        if current_rev.isdigit():
            instance.revision = str(int(current_rev) + 1)
        elif current_rev.isalpha() and len(current_rev) == 1:
            if current_rev.upper() == 'Z':
                instance.revision = 'AA'
            else:
                instance.revision = chr(ord(current_rev) + 1)
        else:
            instance.revision = f'{current_rev}.1'

        logger.info(
            'Drawing %s revision auto-incremented from %s to %s',
            instance.drawing_number, current_rev, instance.revision,
        )
