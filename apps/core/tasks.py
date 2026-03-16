import io
import os
from datetime import datetime, timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone


@shared_task
def backup_database():
    """Run dumpdata and save a timestamped JSON backup.

    Keeps only the last 7 backup files; older ones are deleted automatically.
    """
    from django.core.management import call_command

    backup_dir = os.path.join(settings.BASE_DIR, 'local', 'backups')
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'erp_backup_{timestamp}.json'
    filepath = os.path.join(backup_dir, filename)

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


@shared_task
def cleanup_old_notifications():
    """Delete Notification records older than 30 days."""
    from apps.core.notification import Notification

    cutoff = timezone.now() - timedelta(days=30)
    deleted_count, _ = Notification.objects.filter(created_at__lt=cutoff).delete()
    return f'Deleted {deleted_count} old notifications'
