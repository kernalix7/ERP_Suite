"""프로덕션 초기화 management command — 관리자 계정만 생성, 시드 데이터 없음"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = '프로덕션 DB 초기화 (관리자 계정만 생성, 시드 데이터 없음)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username', default='admin',
            help='관리자 아이디 (기본: admin)',
        )
        parser.add_argument(
            '--password', default='admin1234!',
            help='관리자 비밀번호 (기본: admin1234!)',
        )
        parser.add_argument(
            '--name', default='관리자',
            help='관리자 이름 (기본: 관리자)',
        )

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        name = options['name']

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(
                f'사용자 "{username}"이(가) 이미 존재합니다. 건너뜁니다.'
            ))
            return

        user = User(
            username=username,
            name=name,
            role='admin',
            is_auditor=True,
            is_staff=True,
            is_superuser=True,
        )
        user.set_password(password)
        user.save()

        # 비밀번호 검증
        assert user.check_password(password), '비밀번호 설정 실패!'

        self.stdout.write(self.style.SUCCESS(
            f'관리자 생성 완료: {user.username} / {password}'
        ))
