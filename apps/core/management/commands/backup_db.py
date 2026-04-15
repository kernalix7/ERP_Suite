"""Database backup management command.

Supports PostgreSQL (pg_dump) and SQLite (file copy).
Produces gzip-compressed backups with configurable retention policy.
"""
import gzip
import os
import re
import shutil
import subprocess
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create a compressed database backup with retention policy'

    def add_arguments(self, parser):
        parser.add_argument(
            '--retention-daily',
            type=int,
            default=7,
            help='Number of daily backups to keep (default: 7)',
        )
        parser.add_argument(
            '--retention-weekly',
            type=int,
            default=4,
            help='Number of weekly backups to keep (default: 4)',
        )
        parser.add_argument(
            '--retention-monthly',
            type=int,
            default=3,
            help='Number of monthly backups to keep (default: 3)',
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            default=None,
            help='Backup output directory (default: local/backups/)',
        )

    def handle(self, *args, **options):
        backup_dir = options['output_dir'] or os.path.join(
            settings.BASE_DIR, 'local', 'backups',
        )
        os.makedirs(backup_dir, exist_ok=True)

        db_config = settings.DATABASES['default']
        engine = db_config['ENGINE']
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if 'postgresql' in engine or 'postgis' in engine:
            filepath = self._backup_postgresql(db_config, backup_dir, timestamp)
        elif 'sqlite' in engine:
            filepath = self._backup_sqlite(db_config, backup_dir, timestamp)
        else:
            raise CommandError(f'Unsupported database engine: {engine}')

        self.stdout.write(self.style.SUCCESS(f'Backup saved: {filepath}'))

        self._apply_retention(
            backup_dir,
            daily=options['retention_daily'],
            weekly=options['retention_weekly'],
            monthly=options['retention_monthly'],
        )

        return filepath

    def _backup_postgresql(self, db_config, backup_dir, timestamp):
        """Run pg_dump and gzip the output."""
        filename = f'backup_{timestamp}.sql.gz'
        filepath = os.path.join(backup_dir, filename)

        env = os.environ.copy()
        if db_config.get('PASSWORD'):
            env['PGPASSWORD'] = db_config['PASSWORD']

        cmd = [
            'pg_dump',
            '--host', db_config.get('HOST', 'localhost'),
            '--port', str(db_config.get('PORT', '5432')),
            '--username', db_config.get('USER', 'postgres'),
            '--dbname', db_config['NAME'],
            '--format=plain',
            '--no-owner',
            '--no-privileges',
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                env=env,
                check=True,
                timeout=600,
            )
        except FileNotFoundError:
            raise CommandError('pg_dump not found. Is PostgreSQL client installed?')
        except subprocess.CalledProcessError as exc:
            raise CommandError(f'pg_dump failed: {exc.stderr.decode()}')
        except subprocess.TimeoutExpired:
            raise CommandError('pg_dump timed out after 600 seconds')

        with gzip.open(filepath, 'wb') as f:
            f.write(result.stdout)

        return filepath

    def _backup_sqlite(self, db_config, backup_dir, timestamp):
        """Copy SQLite database file and gzip it."""
        db_path = str(db_config['NAME'])

        # In-memory databases or test databases cannot be file-copied
        if ':memory:' in db_path or 'mode=memory' in db_path:
            raise CommandError(
                'Cannot backup in-memory SQLite database. '
                'Use a file-based database for backups.',
            )

        if not os.path.exists(db_path):
            raise CommandError(f'SQLite database not found: {db_path}')

        filename = f'backup_{timestamp}.sqlite3.gz'
        filepath = os.path.join(backup_dir, filename)

        with open(db_path, 'rb') as f_in, gzip.open(filepath, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

        return filepath

    def _apply_retention(self, backup_dir, daily, weekly, monthly):
        """Apply retention policy: keep N daily, N weekly, N monthly backups.

        Files are classified by their timestamp:
        - All files from the last `daily` days are kept.
        - One file per week for the last `weekly` weeks is kept.
        - One file per month for the last `monthly` months is kept.
        - Everything else is deleted.
        """
        pattern = re.compile(r'^backup_(\d{8})_\d{6}\.(sql|sqlite3)\.gz$')
        backups = []

        for name in os.listdir(backup_dir):
            match = pattern.match(name)
            if match:
                date_str = match.group(1)
                try:
                    file_date = datetime.strptime(date_str, '%Y%m%d')
                    filepath = os.path.join(backup_dir, name)
                    mtime = os.path.getmtime(filepath)
                    backups.append((filepath, file_date, mtime))
                except ValueError:
                    continue

        if not backups:
            return

        # Sort newest first
        backups.sort(key=lambda x: x[2], reverse=True)

        keep = set()
        now = datetime.now()

        # Keep daily backups (most recent N by file count)
        for filepath, _, _ in backups[:daily]:
            keep.add(filepath)

        # Keep weekly (one per calendar week, up to `weekly` weeks)
        seen_weeks = set()
        for filepath, file_date, _ in backups:
            week_key = file_date.strftime('%Y-%W')
            if week_key not in seen_weeks and len(seen_weeks) < weekly:
                keep.add(filepath)
                seen_weeks.add(week_key)

        # Keep monthly (one per calendar month, up to `monthly` months)
        seen_months = set()
        for filepath, file_date, _ in backups:
            month_key = file_date.strftime('%Y-%m')
            if month_key not in seen_months and len(seen_months) < monthly:
                keep.add(filepath)
                seen_months.add(month_key)

        # Delete everything not in keep set
        deleted = 0
        for filepath, _, _ in backups:
            if filepath not in keep:
                os.remove(filepath)
                deleted += 1

        if deleted:
            self.stdout.write(f'Retention cleanup: removed {deleted} old backup(s)')
