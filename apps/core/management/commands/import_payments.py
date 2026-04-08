"""결제내역 Excel → 견적서 자동 생성 커맨드"""
import openpyxl
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = '결제내역 Excel 파일을 읽어 견적서를 자동 생성합니다.'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Excel 파일 경로')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='실제 DB에 저장하지 않고 미리보기만',
        )

    def handle(self, *args, **options):
        file_path = options['file_path']
        dry_run = options['dry_run']

        wb = openpyxl.load_workbook(file_path)
        ws = wb.active

        rows = list(ws.iter_rows(min_row=2, values_only=True))
        # 환불 건 제외, 완료 건만
        payments = []
        for row in rows:
            status = row[4]  # 결제상태
            if status != '완료':
                self.stdout.write(self.style.WARNING(
                    f'  제외 (상태={status}): {row[11]} / {row[6]}',
                ))
                continue
            amount_str = str(row[6]).replace(',', '').replace('+', '')
            amount = int(amount_str)
            if amount <= 0:
                continue

            dt_str = row[2]  # 결제일시 '2026.03.28 16:01:37'
            dt = datetime.strptime(dt_str, '%Y.%m.%d %H:%M:%S')

            payments.append({
                'store': row[1],           # 매장명
                'date': dt.date(),
                'amount': amount,          # VAT 포함 총액
                'method': row[8],          # 결제방식
                'institution': row[9],     # 결제기관
                'product_name': row[11],   # 구매상품
            })

        self.stdout.write(f'\n처리 대상: {len(payments)}건')
        for p in payments:
            self.stdout.write(
                f'  {p["date"]} | {p["product_name"]} | '
                f'{p["amount"]:,}원 | {p["method"]} {p["institution"] or ""}'
            )

        if dry_run:
            self.stdout.write(self.style.SUCCESS('\n[DRY RUN] 미리보기 완료.'))
            return

        from apps.inventory.models import Product
        from apps.sales.models import Partner, Quotation, QuotationItem

        with transaction.atomic():
            # 1. 거래처 find or create
            partner, created = Partner.all_objects.get_or_create(
                name=payments[0]['store'],
                defaults={'code': 'CRT-001', 'partner_type': 'CUSTOMER'},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(
                    f'\n거래처 생성: {partner.name} ({partner.code})',
                ))
            else:
                self.stdout.write(f'\n기존 거래처 사용: {partner.name}')

            for i, p in enumerate(payments, 1):
                # 2. SERVICE 제품 find or create
                product_name = p['product_name']
                product, p_created = Product.all_objects.get_or_create(
                    name=product_name,
                    defaults={
                        'product_type': 'SERVICE',
                        'unit_price': p['amount'],
                    },
                )
                if p_created:
                    self.stdout.write(self.style.SUCCESS(
                        f'  제품 생성: [{product.code}] {product.name}'
                        f' (SERVICE, {p["amount"]:,}원)',
                    ))

                # 3. 견적서 생성 (vat_included=True)
                quote = Quotation.all_objects.create(
                    partner=partner,
                    quote_date=p['date'],
                    valid_until=p['date'] + timedelta(days=30),
                    status='DRAFT',
                    vat_included=True,
                    notes=(
                        f'결제방식: {p["method"]}'
                        f'{" / " + p["institution"] if p["institution"] else ""}'
                    ),
                )

                # 4. 견적 항목 생성
                QuotationItem.all_objects.create(
                    quotation=quote,
                    product=product,
                    quantity=1,
                    unit_price=p['amount'],
                )
                quote.update_total()

                self.stdout.write(
                    f'  견적 생성: {quote.quote_number} | '
                    f'{p["date"]} | {product_name} | '
                    f'공급가 {quote.total_amount:,} + 부가세 {quote.tax_total:,}'
                    f' = 총 {quote.grand_total:,}원',
                )

        self.stdout.write(self.style.SUCCESS(
            f'\n완료: 견적 {len(payments)}건 생성.',
        ))
