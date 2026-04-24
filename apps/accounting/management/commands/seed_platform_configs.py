from django.core.management.base import BaseCommand

from apps.accounting.models import PlatformFinancialConfig


SEED = [
    {
        'code': 'DIRECT',
        'name': '직판',
        'payment_method_default': PlatformFinancialConfig.PaymentMethod.BANK_TRANSFER,
        'settlement_cycle_days': 0,
        'commission_rate': 0,
        'tax_invoice_issuer': PlatformFinancialConfig.IssuerType.SELF,
        'cash_receipt_issuer': PlatformFinancialConfig.IssuerType.SELF,
        'card_receipt_issuer': PlatformFinancialConfig.IssuerType.SELF,
        'vat_classification_default': PlatformFinancialConfig.TaxType.TAXABLE,
        'allow_zero_rate': True,
        'is_enabled': True,
    },
    {
        'code': 'NAVER',
        'name': '네이버 스마트스토어',
        'payment_method_default': PlatformFinancialConfig.PaymentMethod.PLATFORM_SETTLEMENT,
        'settlement_cycle_days': 3,
        'commission_rate': 2,
        'tax_invoice_issuer': PlatformFinancialConfig.IssuerType.SELF,
        'cash_receipt_issuer': PlatformFinancialConfig.IssuerType.PLATFORM,
        'card_receipt_issuer': PlatformFinancialConfig.IssuerType.PLATFORM,
        'vat_classification_default': PlatformFinancialConfig.TaxType.TAXABLE,
        'allow_zero_rate': False,
        'is_enabled': True,
    },
    {
        'code': 'COUPANG',
        'name': '쿠팡',
        'payment_method_default': PlatformFinancialConfig.PaymentMethod.PLATFORM_SETTLEMENT,
        'settlement_cycle_days': 30,
        'commission_rate': 10,
        'tax_invoice_issuer': PlatformFinancialConfig.IssuerType.SELF,
        'cash_receipt_issuer': PlatformFinancialConfig.IssuerType.PLATFORM,
        'card_receipt_issuer': PlatformFinancialConfig.IssuerType.PLATFORM,
        'vat_classification_default': PlatformFinancialConfig.TaxType.TAXABLE,
        'allow_zero_rate': False,
        'is_enabled': True,
    },
]


class Command(BaseCommand):
    help = '기본 플랫폼 재무설정 시드 데이터 (DIRECT / NAVER / COUPANG)'

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for row in SEED:
            code = row['code']
            obj, was_created = PlatformFinancialConfig.all_objects.update_or_create(
                code=code,
                defaults={**row, 'is_active': True},
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(
            f'PlatformFinancialConfig 시드 완료 — 생성 {created}건, 갱신 {updated}건'
        ))
