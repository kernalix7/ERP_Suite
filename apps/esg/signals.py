import logging

from django.db.models import Sum
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import CarbonEmission, ESGMetric

logger = logging.getLogger(__name__)


@receiver(post_save, sender=CarbonEmission)
def carbon_emission_target_check(sender, instance, created, **kwargs):
    """탄소 배출 기록 시 해당 기간의 누적 배출량 vs 목표 비교 알림"""
    if not created:
        return
    if not instance.is_active:
        return

    # 탄소배출 관련 ESG 지표 중 목표값이 설정된 것 조회
    carbon_metrics = ESGMetric.objects.filter(
        is_active=True,
        category__category_type='ENVIRONMENTAL',
        target_value__isnull=False,
    ).select_related('category')

    if not carbon_metrics.exists():
        return

    # 같은 기간(연도)의 총 배출량
    year = instance.period.year
    yearly_total = CarbonEmission.objects.filter(
        is_active=True,
        period__year=year,
    ).aggregate(total=Sum('amount_kg'))['total'] or 0

    for metric in carbon_metrics:
        if metric.target_value and yearly_total > metric.target_value:
            _notify_carbon_exceeded(metric, yearly_total, year)


def _notify_carbon_exceeded(metric, actual, year):
    """탄소 배출 목표 초과 알림 — 관리자에게 발송"""
    try:
        from apps.core.notification import create_notification
        create_notification(
            users='manager',
            title=f'탄소배출 목표 초과 경고 ({year}년)',
            message=(
                f'ESG 지표 [{metric.name}] 연간 목표 {metric.target_value}kg 대비 '
                f'현재 누적 {actual}kg ({actual - metric.target_value}kg 초과)'
            ),
            noti_type='SYSTEM',
            link='/esg/carbon/',
        )
    except Exception:
        logger.warning(
            'Carbon emission notification failed — metric=%s, actual=%s',
            metric.code, actual, exc_info=True,
        )
