import io
import os
from datetime import datetime, timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def backup_database(self):
    """Run dumpdata and save a timestamped JSON backup.

    Keeps only the last 7 backup files; older ones are deleted automatically.
    """
    from django.core.management import call_command

    backup_dir = os.path.join(settings.BASE_DIR, 'local', 'backups')
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'erp_backup_{timestamp}.json'
    filepath = os.path.join(backup_dir, filename)

    try:
        output = io.StringIO()
        call_command(
            'dumpdata',
            '--exclude=contenttypes',
            '--exclude=auth.permission',
            '--indent=2',
            stdout=output,
        )

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(output.getvalue())

        # Keep only the last 7 backups
        backups = sorted(
            [
                os.path.join(backup_dir, f)
                for f in os.listdir(backup_dir)
                if f.startswith('erp_backup_') and f.endswith('.json')
            ],
            key=os.path.getmtime,
        )
        for old_backup in backups[:-7]:
            os.remove(old_backup)

        return f'Backup saved: {filename}'
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
