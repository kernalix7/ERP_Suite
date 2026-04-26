from django.core.management.base import BaseCommand

from apps.accounting.models import PlatformFinancialConfig


# 주의: 수수료율·정산주기는 시장 표준 어림값입니다.
# 실제 값은 사용자 사업자 등급·카테고리·정산방식·VIP 협상에 따라 달라집니다.
# 각 거래처는 PlatformFinancialConfig 채널값과 별개로 Partner.CommissionRate에서
# 협상가를 별도 관리할 수 있습니다 (단방향: 채널값 변경 → 신규 거래처 자동 복사).
# 운영 전 반드시 `/accounting/platform-config/<id>/edit/` 에서 본인 계약값으로 갱신하세요.
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
        # 정산: 구매확정+1영업일, 자동확정 보통 7~14일 → 평균 8일
        'settlement_cycle_days': 8,
        # 네이버페이 결제수수료 + 매출수수료 합산 평균 (2024 기준)
        'commission_rate': 3.74,
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
        # 정산: 주정산 D+15 평균 (월정산은 다음달 15일)
        'settlement_cycle_days': 15,
        # 카테고리별 5~13% 평균 (의류 10~12% / 식품 5~7% / 디지털 5~10%)
        'commission_rate': 10.8,
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
