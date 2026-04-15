import logging

from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.bi.models import Report

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Report)
def invalidate_report_cache(sender, instance, **kwargs):
    """Report 생성/수정 시 관련 캐시 무효화"""
    cache_key = f'bi_report_{instance.pk}'
    cache.delete(cache_key)
    # 대시보드 차트 캐시도 무효화 (리포트 데이터 변경 반영)
    cache.delete('dashboard_chart_data')
    logger.debug('Report cache invalidated: pk=%s', instance.pk)
