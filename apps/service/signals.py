import logging
from datetime import date, timedelta

from django.db import transaction
from django.db.models.signals import pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(pre_save, sender='service.ServiceRequest')
def auto_ar_on_service_completed(sender, instance, **kwargs):
    """AS 요청 완료 시 유상수리 비용 AR 자동 생성

    - COMPLETED 상태로 전환될 때만
    - is_warranty=False (유상수리)일 때만
    - 수리비용 합계 > 0일 때만
    - 고객에 연결된 Partner가 있어야 AR 생성 가능
    """
    if not instance.pk:
        return

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old.status == 'COMPLETED' or instance.status != 'COMPLETED':
        return

    if instance.is_warranty:
        logger.info(
            'ServiceRequest %s: 보증수리 — AR 미생성',
            instance.request_number,
        )
        return

    # 수리비용 합계 계산
    total_cost = sum(
        int(r.cost) for r in instance.repairs.all() if r.cost > 0
    )
    if total_cost <= 0:
        return

    from apps.accounting.models import AccountReceivable
    from apps.sales.models import Partner

    # 고객 → Partner 매칭 (고객명 기준)
    partners = Partner.objects.filter(
        name=instance.customer.name, is_active=True,
    )
    partner_count = partners.count()
    if partner_count == 0:
        logger.warning(
            'ServiceRequest %s: 고객 "%s"에 매칭된 거래처 없음 — AR 미생성',
            instance.request_number, instance.customer.name,
        )
        return
    if partner_count > 1:
        logger.warning(
            'ServiceRequest %s: 고객 "%s"에 매칭된 거래처가 %d건 — 첫 번째 사용',
            instance.request_number, instance.customer.name, partner_count,
        )
    partner = partners.first()

    # 이미 AR이 있으면 스킵 (중복 방지)
    if AccountReceivable.objects.filter(
        partner=partner,
        notes__contains=instance.request_number,
        is_active=True,
    ).exists():
        return

    with transaction.atomic():
        AccountReceivable.objects.create(
            partner=partner,
            amount=total_cost,
            due_date=date.today() + timedelta(days=30),
            status='PENDING',
            notes=f'AS {instance.request_number} 유상수리 비용',
            created_by=instance.created_by,
        )
        logger.info(
            'ServiceRequest %s COMPLETED → AR 자동 생성: %s원 (거래처: %s)',
            instance.request_number, total_cost, partner.name,
        )


@receiver(pre_save, sender='service.ServiceRequest')
def cancel_ar_on_service_cancelled(sender, instance, **kwargs):
    """AS 요청 취소 시 관련 AR/전표 soft delete

    - CANCELLED 상태로 전환될 때만
    - notes에 request_number가 포함된 AR을 soft delete
    - AR에 연결된 전표도 soft delete
    """
    if not instance.pk:
        return

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old.status == 'CANCELLED' or instance.status != 'CANCELLED':
        return

    from apps.accounting.models import AccountReceivable, Voucher

    with transaction.atomic():
        # request_number로 연결된 AR 찾기
        ars = AccountReceivable.objects.filter(
            notes__contains=instance.request_number,
            is_active=True,
        )
        for ar in ars:
            # AR에 연결된 전표 soft delete
            vouchers = Voucher.objects.filter(
                description__contains=instance.request_number,
                is_active=True,
            )
            for v in vouchers:
                v.is_active = False
                v.save(update_fields=['is_active', 'updated_at'])

            ar.is_active = False
            ar.save(update_fields=['is_active', 'updated_at'])
            logger.info(
                'ServiceRequest %s CANCELLED → AR soft deleted (pk=%s)',
                instance.request_number, ar.pk,
            )
