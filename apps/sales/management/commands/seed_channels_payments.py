"""SalesChannel + PaymentMethod 시드 — 기존 enum 값을 DB로 마이그.

사용:
    python manage.py seed_channels_payments
"""
from django.core.management.base import BaseCommand


SALES_CHANNELS = [
    # (code, name, is_marketplace, sort_order)
    ('DIRECT', '자사몰', False, 10),
    ('NAVER', '네이버 스마트스토어', True, 20),
    ('COUPANG', '쿠팡', True, 30),
    ('OFFLINE', '오프라인', False, 80),
    ('PHONE', '전화/카카오', False, 85),
    ('OTHER', '기타', False, 999),
]


PAYMENT_METHODS = [
    # (code, name, is_card, is_cash_equivalent, sort_order)
    ('CARD', '신용카드', True, False, 10),
    ('BANK_TRANSFER', '계좌이체', False, True, 20),
    ('CASH', '현금', False, True, 30),
    ('VIRTUAL_ACCOUNT', '가상계좌', False, True, 40),
    ('NAVER_PAY', '네이버페이', True, False, 50),
    ('KAKAO_PAY', '카카오페이', True, False, 55),
    ('PLATFORM', '플랫폼 정산', False, False, 90),
    ('OTHER', '기타', False, False, 999),
]


class Command(BaseCommand):
    help = '판매채널/결제수단 마스터 시드 (Order TextChoices → DB)'

    def handle(self, *args, **options):
        from apps.sales.models import SalesChannel, PaymentMethod

        ch_created = 0
        for code, name, is_mp, order in SALES_CHANNELS:
            _, was_created = SalesChannel.all_objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'is_marketplace': is_mp,
                    'sort_order': order,
                    'is_enabled': True,
                    'is_active': True,
                },
            )
            if was_created:
                ch_created += 1

        pm_created = 0
        for code, name, is_card, is_cash, order in PAYMENT_METHODS:
            _, was_created = PaymentMethod.all_objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'is_card': is_card,
                    'is_cash_equivalent': is_cash,
                    'sort_order': order,
                    'is_enabled': True,
                    'is_active': True,
                },
            )
            if was_created:
                pm_created += 1

        self.stdout.write(self.style.SUCCESS(
            f'SalesChannel 신규 {ch_created}건 / PaymentMethod 신규 {pm_created}건'
        ))
