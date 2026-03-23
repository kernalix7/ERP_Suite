import os

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = '점검 모드 on/off — on: 점검 페이지 표시, off: 정상 운영'

    def add_arguments(self, parser):
        parser.add_argument('mode', choices=['on', 'off'], help='on 또는 off')

    def handle(self, *args, **options):
        flag_file = getattr(
            settings, 'MAINTENANCE_MODE_FILE',
            os.path.join(settings.BASE_DIR, 'local', '.maintenance'),
        )

        if options['mode'] == 'on':
            with open(flag_file, 'w') as f:
                f.write('maintenance')
            self.stdout.write(self.style.WARNING(
                f'점검 모드 ON — {flag_file} 생성됨. 슈퍼유저 외 모든 접근이 점검 페이지로 전환됩니다.'
            ))
        else:
            if os.path.exists(flag_file):
                os.remove(flag_file)
            self.stdout.write(self.style.SUCCESS(
                f'점검 모드 OFF — {flag_file} 제거됨. 정상 운영으로 복귀합니다.'
            ))
