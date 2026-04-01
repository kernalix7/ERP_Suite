"""
작성자(created_by) 일괄 재할당 커맨드

Usage:
    python manage.py reassign_creator --from admin --to user@example.com
    python manage.py reassign_creator --from admin --to user@example.com --dry-run
"""
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User


class Command(BaseCommand):
    help = 'created_by를 한 사용자에서 다른 사용자로 일괄 재할당합니다.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--from', dest='from_user', required=True,
            help='기존 작성자 (username 또는 email)',
        )
        parser.add_argument(
            '--to', dest='to_user', required=True,
            help='변경할 작성자 (username 또는 email)',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='실제 변경 없이 영향 범위만 확인',
        )

    def _find_user(self, identifier):
        try:
            return User.objects.get(username=identifier)
        except User.DoesNotExist:
            pass
        try:
            return User.objects.get(email=identifier)
        except User.DoesNotExist:
            raise CommandError(f'사용자를 찾을 수 없습니다: {identifier}')

    def handle(self, *args, **options):
        from_user = self._find_user(options['from_user'])
        to_user = self._find_user(options['to_user'])
        dry_run = options['dry_run']

        self.stdout.write(f'\n  FROM: {from_user} (pk={from_user.pk})')
        self.stdout.write(f'  TO:   {to_user} (pk={to_user.pk})')
        if dry_run:
            self.stdout.write(self.style.WARNING('  [DRY-RUN 모드]\n'))
        self.stdout.write('')

        total_updated = 0
        results = []

        all_models = apps.get_models()
        for model in all_models:
            if not hasattr(model, 'created_by'):
                continue
            # Historical 모델 제외
            if model.__name__.startswith('Historical'):
                continue

            count = model._default_manager.filter(created_by=from_user).count()
            if count == 0:
                continue

            label = f'{model._meta.app_label}.{model.__name__}'
            results.append((label, count))
            total_updated += count

        if not results:
            self.stdout.write(self.style.SUCCESS(
                f'  {from_user}이(가) 작성자인 레코드가 없습니다.',
            ))
            return

        # 결과 표시
        self.stdout.write(f'  {"모델":<40} {"건수":>8}')
        self.stdout.write(f'  {"─" * 40} {"─" * 8}')
        for label, count in sorted(results):
            self.stdout.write(f'  {label:<40} {count:>8,}')
        self.stdout.write(f'  {"─" * 40} {"─" * 8}')
        self.stdout.write(self.style.NOTICE(
            f'  {"합계":<40} {total_updated:>8,}건',
        ))
        self.stdout.write('')

        if dry_run:
            self.stdout.write(self.style.WARNING(
                '  [DRY-RUN] 실제 변경되지 않았습니다. '
                '--dry-run 제거 후 다시 실행하세요.',
            ))
            return

        # 실행
        with transaction.atomic():
            for model in all_models:
                if not hasattr(model, 'created_by'):
                    continue
                if model.__name__.startswith('Historical'):
                    continue
                updated = model._default_manager.filter(
                    created_by=from_user,
                ).update(created_by=to_user)
                if updated:
                    self.stdout.write(
                        f'  {model._meta.app_label}.{model.__name__}: '
                        f'{updated}건 변경',
                    )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'  완료: {total_updated:,}건 재할당 '
            f'({from_user} → {to_user})',
        ))
