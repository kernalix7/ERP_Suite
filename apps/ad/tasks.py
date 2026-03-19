import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def sync_all_domains(self):
    """모든 활성 AD 도메인 동기화 (Celery Beat 스케줄)"""
    from .models import ADDomain
    from .services import ADService

    domains = ADDomain.objects.filter(is_active=True, sync_enabled=True)
    results = []

    for domain in domains:
        try:
            service = ADService(domain)
            sync_log = service.sync(sync_type='INCREMENTAL')
            results.append(
                f'{domain.name}: {sync_log.get_status_display()} '
                f'({sync_log.total_processed}건)'
            )
        except (OSError, ConnectionError, ValueError) as e:
            results.append(f'{domain.name}: 실패 - {str(e)}')
            logger.error('AD 동기화 실패 (domain=%s): %s',
                         domain.name, str(e), exc_info=True)

    return '; '.join(results)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_domain(self, domain_id, sync_type='FULL', triggered_by_id=None):
    """특정 도메인 동기화 (비동기 실행)"""
    from apps.accounts.models import User
    from .models import ADDomain
    from .services import ADService

    try:
        domain = ADDomain.objects.get(pk=domain_id)
    except ADDomain.DoesNotExist:
        return f'도메인 ID {domain_id} 없음'

    triggered_by = None
    if triggered_by_id:
        triggered_by = User.objects.filter(pk=triggered_by_id).first()

    service = ADService(domain)
    sync_log = service.sync(sync_type=sync_type, triggered_by=triggered_by)
    return (
        f'{domain.name}: {sync_log.get_status_display()} '
        f'(생성 {sync_log.users_created}, 수정 {sync_log.users_updated}, '
        f'비활성 {sync_log.users_disabled}, 오류 {sync_log.errors_count})'
    )
