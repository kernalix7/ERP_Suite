"""K-GAAP 표준 계정과목 시드 데이터.

한국 일반기업회계기준(K-GAAP) 기준의 표준 계정과목 체계를 시드합니다.
이미 존재하는 코드는 갱신하지 않고 skip (사용자 커스터마이즈 보호).

사용:
    python manage.py seed_account_codes
"""
from django.core.management.base import BaseCommand
from apps.accounting.models import AccountCode


# 코드 prefix 규약 (IncomeStatementView K-GAAP 9단계와 정합):
#  1xx 자산 / 2xx 부채 / 3xx 자본 / 4xx 수익 / 5~9xx 비용
SEED = [
    # ── 1xx 자산 (ASSET) ──
    ('101', '현금', 'ASSET', 'OPERATING'),
    ('102', '당좌예금', 'ASSET', 'OPERATING'),
    ('103', '보통예금', 'ASSET', 'OPERATING'),
    ('120', '미수금', 'ASSET', 'OPERATING'),
    ('121', '받을어음', 'ASSET', 'OPERATING'),
    ('135', '선급금', 'ASSET', 'OPERATING'),
    ('136', '선급비용', 'ASSET', 'OPERATING'),
    ('140', '대손충당금', 'ASSET', 'OPERATING'),  # 차감계정
    ('150', '재고자산', 'ASSET', 'OPERATING'),
    ('151', '제품', 'ASSET', 'OPERATING'),
    ('152', '원재료', 'ASSET', 'OPERATING'),
    ('153', '재공품', 'ASSET', 'OPERATING'),
    ('158', '비품', 'ASSET', 'INVESTING'),
    ('159', '감가상각누계액', 'ASSET', 'INVESTING'),  # 차감계정
    ('170', '건물', 'ASSET', 'INVESTING'),
    ('171', '기계장치', 'ASSET', 'INVESTING'),
    ('178', '차량운반구', 'ASSET', 'INVESTING'),
    # ── 2xx 부채 (LIABILITY) ──
    ('200', '외상매입금', 'LIABILITY', 'OPERATING'),
    ('201', '지급어음', 'LIABILITY', 'OPERATING'),
    ('204', '부가세예수금', 'LIABILITY', 'OPERATING'),
    ('205', '부가세대급금', 'ASSET', 'OPERATING'),
    ('210', '미지급금', 'LIABILITY', 'OPERATING'),
    ('211', '미지급비용', 'LIABILITY', 'OPERATING'),
    ('213', '예수금', 'LIABILITY', 'OPERATING'),
    ('214', '선수금', 'LIABILITY', 'OPERATING'),
    ('215', '선수수익', 'LIABILITY', 'OPERATING'),
    ('220', '단기차입금', 'LIABILITY', 'FINANCING'),
    ('260', '장기차입금', 'LIABILITY', 'FINANCING'),
    # ── 3xx 자본 (EQUITY) ──
    ('331', '자본금', 'EQUITY', 'FINANCING'),
    ('332', '자본잉여금', 'EQUITY', 'FINANCING'),
    ('340', '이익잉여금', 'EQUITY', 'FINANCING'),
    # ── 4xx 매출/영업외수익 (REVENUE) ──
    ('401', '매출', 'REVENUE', 'OPERATING'),
    ('402', '제품매출', 'REVENUE', 'OPERATING'),
    ('403', '상품매출', 'REVENUE', 'OPERATING'),
    ('470', '외환차익', 'REVENUE', 'OPERATING'),
    ('471', '이자수익', 'REVENUE', 'INVESTING'),
    ('472', '배당금수익', 'REVENUE', 'INVESTING'),
    ('473', '잡이익', 'REVENUE', 'OPERATING'),
    # ── 5xx 매출원가 / 판관비 (EXPENSE) ──
    ('501', '매입원가', 'EXPENSE', 'OPERATING'),
    ('502', '제품매출원가', 'EXPENSE', 'OPERATING'),
    ('503', '상품매출원가', 'EXPENSE', 'OPERATING'),
    ('521', '급여', 'EXPENSE', 'OPERATING'),
    ('522', '잡급', 'EXPENSE', 'OPERATING'),
    ('523', '상여금', 'EXPENSE', 'OPERATING'),
    ('524', '복리후생비', 'EXPENSE', 'OPERATING'),
    ('525', '여비교통비', 'EXPENSE', 'OPERATING'),
    ('526', '접대비', 'EXPENSE', 'OPERATING'),
    ('527', '통신비', 'EXPENSE', 'OPERATING'),
    ('528', '수도광열비', 'EXPENSE', 'OPERATING'),
    ('529', '세금과공과', 'EXPENSE', 'OPERATING'),
    ('530', '감가상각비', 'EXPENSE', 'OPERATING'),
    ('531', '지급수수료', 'EXPENSE', 'OPERATING'),
    ('532', '광고선전비', 'EXPENSE', 'OPERATING'),
    ('533', '소모품비', 'EXPENSE', 'OPERATING'),
    ('534', '운반비', 'EXPENSE', 'OPERATING'),
    ('535', '차량유지비', 'EXPENSE', 'OPERATING'),
    ('536', '도서인쇄비', 'EXPENSE', 'OPERATING'),
    ('537', '회의비', 'EXPENSE', 'OPERATING'),
    ('538', '교육훈련비', 'EXPENSE', 'OPERATING'),
    ('539', '보험료', 'EXPENSE', 'OPERATING'),
    ('540', '임차료', 'EXPENSE', 'OPERATING'),
    ('541', '수선비', 'EXPENSE', 'OPERATING'),
    ('542', '잡비', 'EXPENSE', 'OPERATING'),
    # ── 9xx 영업외비용 ──
    ('911', '이자비용', 'EXPENSE', 'FINANCING'),
    ('925', '외환차손', 'EXPENSE', 'OPERATING'),
    ('926', '기부금', 'EXPENSE', 'OPERATING'),
    ('927', '기타의대손상각비', 'EXPENSE', 'OPERATING'),
    ('928', '잡손실', 'EXPENSE', 'OPERATING'),
    # ── 998~ 법인세 ──
    ('998', '법인세비용', 'EXPENSE', 'OPERATING'),
    ('999', '법인세등', 'EXPENSE', 'OPERATING'),
]


class Command(BaseCommand):
    help = 'K-GAAP 표준 계정과목 시드 (자산/부채/자본/수익/비용 70여건)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--update', action='store_true',
            help='기존 코드도 name/account_type/cash_flow_category 갱신',
        )

    def handle(self, *args, **options):
        update = options['update']
        created = 0
        skipped = 0
        updated = 0

        for code, name, account_type, cash_flow in SEED:
            obj, was_created = AccountCode.all_objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'account_type': account_type,
                    'cash_flow_category': cash_flow,
                    'is_active': True,
                },
            )
            if was_created:
                created += 1
                continue
            if update:
                changed = False
                if obj.name != name:
                    obj.name, changed = name, True
                if obj.account_type != account_type:
                    obj.account_type, changed = account_type, True
                if obj.cash_flow_category != cash_flow:
                    obj.cash_flow_category, changed = cash_flow, True
                if not obj.is_active:
                    obj.is_active, changed = True, True
                if changed:
                    obj.save()
                    updated += 1
                else:
                    skipped += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f'AccountCode 시드 완료 — 신규 {created}, 갱신 {updated}, 스킵 {skipped}'
        ))
