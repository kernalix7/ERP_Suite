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
    partner = Partner.objects.filter(
        name=instance.customer.name, is_active=True,
    ).first()
    if not partner:
        logger.warning(
            'ServiceRequest %s: 고객 "%s"에 매칭된 거래처 없음 — AR 미생성',
            instance.request_number, instance.customer.name,
        )
        return

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
