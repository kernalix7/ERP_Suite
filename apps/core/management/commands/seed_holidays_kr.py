"""한국 법정공휴일 시드 — 2026~2027 + 음력 기반 기본값.

운영 시 매년 신규 시드 추가 또는 admin에서 수동 등록.
"""
from datetime import date

from django.core.management.base import BaseCommand


# 한국 공휴일 (양력 고정 + 음력은 매년 다름 — 본 시드는 양력 변환된 값)
HOLIDAYS = [
    # 2026
    (date(2026, 1, 1), '신정', 'PUBLIC', False),
    (date(2026, 2, 16), '설날 연휴', 'PUBLIC', True),
    (date(2026, 2, 17), '설날', 'PUBLIC', True),
    (date(2026, 2, 18), '설날 연휴', 'PUBLIC', True),
    (date(2026, 3, 1), '삼일절', 'PUBLIC', False),
    (date(2026, 3, 2), '대체공휴일(삼일절)', 'SUBSTITUTE', False),
    (date(2026, 5, 5), '어린이날', 'PUBLIC', False),
    (date(2026, 5, 24), '석가탄신일', 'PUBLIC', True),
    (date(2026, 5, 25), '대체공휴일(석가탄신일)', 'SUBSTITUTE', False),
    (date(2026, 6, 6), '현충일', 'PUBLIC', False),
    (date(2026, 8, 15), '광복절', 'PUBLIC', False),
    (date(2026, 8, 17), '대체공휴일(광복절)', 'SUBSTITUTE', False),
    (date(2026, 9, 24), '추석 연휴', 'PUBLIC', True),
    (date(2026, 9, 25), '추석', 'PUBLIC', True),
    (date(2026, 9, 26), '추석 연휴', 'PUBLIC', True),
    (date(2026, 10, 3), '개천절', 'PUBLIC', False),
    (date(2026, 10, 5), '대체공휴일(개천절)', 'SUBSTITUTE', False),
    (date(2026, 10, 9), '한글날', 'PUBLIC', False),
    (date(2026, 12, 25), '크리스마스', 'PUBLIC', False),
    # 2027
    (date(2027, 1, 1), '신정', 'PUBLIC', False),
    (date(2027, 2, 6), '설날 연휴', 'PUBLIC', True),
    (date(2027, 2, 7), '설날', 'PUBLIC', True),
    (date(2027, 2, 8), '설날 연휴', 'PUBLIC', True),
    (date(2027, 3, 1), '삼일절', 'PUBLIC', False),
    (date(2027, 5, 5), '어린이날', 'PUBLIC', False),
    (date(2027, 5, 13), '석가탄신일', 'PUBLIC', True),
    (date(2027, 6, 6), '현충일', 'PUBLIC', False),
    (date(2027, 8, 15), '광복절', 'PUBLIC', False),
    (date(2027, 8, 16), '대체공휴일(광복절)', 'SUBSTITUTE', False),
    (date(2027, 9, 14), '추석 연휴', 'PUBLIC', True),
    (date(2027, 9, 15), '추석', 'PUBLIC', True),
    (date(2027, 9, 16), '추석 연휴', 'PUBLIC', True),
    (date(2027, 10, 3), '개천절', 'PUBLIC', False),
    (date(2027, 10, 4), '대체공휴일(개천절)', 'SUBSTITUTE', False),
    (date(2027, 10, 9), '한글날', 'PUBLIC', False),
    (date(2027, 10, 11), '대체공휴일(한글날)', 'SUBSTITUTE', False),
    (date(2027, 12, 25), '크리스마스', 'PUBLIC', False),
]


class Command(BaseCommand):
    help = '한국 법정공휴일 시드 (2026~2027)'

    def handle(self, *args, **options):
        from apps.core.models import Holiday

        created = 0
        skipped = 0
        for d, name, htype, is_lunar in HOLIDAYS:
            obj, was_created = Holiday.all_objects.get_or_create(
                date=d,
                defaults={
                    'name': name,
                    'holiday_type': htype,
                    'is_recurring_lunar': is_lunar,
                },
            )
            if was_created:
                created += 1
            else:
                skipped += 1
        self.stdout.write(self.style.SUCCESS(
            f'한국 공휴일 시드 완료 — 신규 {created}, 스킵 {skipped}'
        ))
