import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.notification import create_notification

from .models import AuditFinding, CAPA, NonConformance

logger = logging.getLogger(__name__)


@receiver(post_save, sender='production.QualityInspection')
def inspection_result_handler(sender, instance, **kwargs):
    """품질검수 결과 처리

    - FAIL → NonConformance 자동 생성
    - CONDITIONAL → Manager 역할 사용자에게 알림
    """
    if not instance.is_active:
        return

    update_fields = kwargs.get('update_fields')

    result = instance.result

    if result == 'FAIL':
        with transaction.atomic():
            nc, created = NonConformance.objects.get_or_create(
                notes=f'QI-{instance.pk}',
                is_active=True,
                defaults={
                    'title': f'검수 불합격 - {instance.inspection_number}',
                    'description': (
                        f'검수번호: {instance.inspection_number}\n'
                        f'제품: {instance.product}\n'
                        f'검수수량: {instance.inspected_quantity}\n'
                        f'불합격수량: {instance.fail_quantity}\n'
                        f'불량내용: {instance.defect_description}'
                    ),
                    'source': NonConformance.Source.INTERNAL,
                    'severity': NonConformance.Severity.MAJOR,
                    'product': instance.product,
                    'detected_by': instance.inspector,
                    'status': NonConformance.Status.OPEN,
                },
            )
            if created:
                logger.info(
                    'NonConformance %s auto-created from inspection %s (FAIL)',
                    nc.nc_number, instance.inspection_number,
                )

    elif result == 'CONDITIONAL':
        create_notification(
            'manager',
            f'조건부합격 검토 필요 - {instance.inspection_number}',
            (
                f'검수번호 {instance.inspection_number}이(가) '
                f'조건부합격으로 판정되었습니다. 검토가 필요합니다.\n'
                f'사유: {instance.conditional_notes}'
            ),
            noti_type='SYSTEM',
        )
        logger.info(
            'Conditional inspection %s — manager notification sent',
            instance.inspection_number,
        )


@receiver(post_save, sender=NonConformance)
def nc_open_create_capa(sender, instance, created, **kwargs):
    """부적합 등록(OPEN) 시 → CAPA(시정조치) 자동 생성"""
    if not instance.is_active:
        return

    if instance.status != NonConformance.Status.OPEN:
        return

    with transaction.atomic():
        existing = CAPA.objects.filter(nc=instance, is_active=True).exists()
        if not existing:
            capa = CAPA.objects.create(
                nc=instance,
                type=CAPA.Type.CORRECTIVE,
                description=f'부적합 {instance.nc_number}에 대한 시정조치',
                status=CAPA.Status.OPEN,
            )
            logger.info(
                'CAPA %s auto-created from NonConformance %s',
                capa.capa_number, instance.nc_number,
            )


@receiver(post_save, sender=CAPA)
def capa_closed_resolve_nc(sender, instance, **kwargs):
    """CAPA 종결(CLOSED) 시 → 관련 NCR status를 RESOLVED로 갱신"""
    if not instance.is_active:
        return

    if instance.status != CAPA.Status.CLOSED:
        return

    nc = instance.nc
    if nc and nc.is_active and nc.status != NonConformance.Status.RESOLVED:
        with transaction.atomic():
            NonConformance.objects.filter(
                pk=nc.pk, is_active=True,
            ).exclude(
                status=NonConformance.Status.RESOLVED,
            ).update(status=NonConformance.Status.RESOLVED)
            logger.info(
                'NonConformance %s resolved after CAPA %s closed',
                nc.nc_number, instance.capa_number,
            )


@receiver(post_save, sender=AuditFinding)
def audit_finding_nc_create_ncr(sender, instance, created, **kwargs):
    """감사 발견사항 중 부적합(MAJOR_NC/MINOR_NC) 시 NCR 자동 생성"""
    if not created:
        return
    if not instance.is_active:
        return
    if instance.finding_type not in ('MAJOR_NC', 'MINOR_NC'):
        return

    with transaction.atomic():
        severity = (
            NonConformance.Severity.MAJOR
            if instance.finding_type == 'MAJOR_NC'
            else NonConformance.Severity.MINOR
        )
        ncr = NonConformance.objects.create(
            title=f'감사 부적합: {instance.audit.title}',
            description=instance.description,
            source=NonConformance.Source.INTERNAL,
            severity=severity,
            status=NonConformance.Status.OPEN,
            created_by=instance.created_by,
        )
        # NCR → CAPA 시그널이 자동 생성하므로 CAPA 연결
        capa = ncr.capas.first()
        if capa:
            AuditFinding.objects.filter(pk=instance.pk).update(capa=capa)

        logger.info(
            'AuditFinding %s (type=%s) — NCR %s auto-created (severity=%s)',
            instance.pk, instance.finding_type,
            ncr.nc_number, severity,
        )
