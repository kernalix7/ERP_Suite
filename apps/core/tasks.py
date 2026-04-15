import io
import os
from datetime import datetime, timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def backup_database(self):
    """Create a compressed database backup using the backup_db management command.

    Retention: 7 daily, 4 weekly, 3 monthly backups.
    """
    from django.core.management import call_command

    try:
        call_command('backup_db')
        return 'Backup completed successfully'
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task
def cleanup_old_notifications():
    """Soft-delete (mark is_read) Notification records older than 90 days,
    then hard-delete records older than 180 days to reclaim storage."""
    from apps.core.notification import Notification

    # 90일 이상: 읽음 처리 (soft archive)
    soft_cutoff = timezone.now() - timedelta(days=90)
    archived_count = Notification.objects.filter(
        created_at__lt=soft_cutoff, is_read=False,
    ).update(is_read=True)

    # 180일 이상: 물리 삭제 (storage 확보)
    hard_cutoff = timezone.now() - timedelta(days=180)
    deleted_count, _ = Notification.objects.filter(
        created_at__lt=hard_cutoff,
    ).delete()

    return f'Archived {archived_count}, deleted {deleted_count} old notifications'
