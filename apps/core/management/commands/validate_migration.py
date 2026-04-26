"""마이그레이션 정합성 검증 명령.

다른 솔루션에서 ERP Suite로 데이터 import 후 실행하여
시산표·재고·AR/AP·잔액 등 핵심 정합성을 자동 검증한다.

사용:
    python manage.py validate_migration
    python manage.py validate_migration --as-of 2026-04-30
    python manage.py validate_migration --strict   # 경고도 실패로 처리
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Sum, F, Q


class Command(BaseCommand):
    help = '마이그레이션 정합성 검증 — 시산표 · 재고 · AR/AP · 잔액 · 부수효과'

    def add_arguments(self, parser):
        parser.add_argument('--as-of', type=str, help='검증 기준일 YYYY-MM-DD')
        parser.add_argument('--strict', action='store_true',
                            help='경고도 실패로 처리')

    def handle(self, **options):
        as_of_str = options.get('as_of')
        as_of = date.fromisoformat(as_of_str) if as_of_str else date.today()
        self.strict = options['strict']
        self.errors = []
        self.warnings = []

        self.stdout.write(self.style.NOTICE(
            f'\n=== 마이그레이션 정합성 검증 (기준일: {as_of}) ===\n'
        ))

        self._check_trial_balance(as_of)
        self._check_stock_consistency()
        self._check_ar_ap_balances()
        self._check_bank_balances()
        self._check_signal_orphans()
        self._check_closing_periods()
        self._check_history_coverage()

        # 요약
        self.stdout.write('')
        if not self.errors and not self.warnings:
            self.stdout.write(self.style.SUCCESS(
                '✅ 모든 검증 통과 — 마이그레이션 무결성 OK'
            ))
            return
        if self.warnings:
            self.stdout.write(self.style.WARNING(
                f'⚠ 경고 {len(self.warnings)}건:'
            ))
            for w in self.warnings:
                self.stdout.write(f'  - {w}')
        if self.errors:
            self.stdout.write(self.style.ERROR(
                f'❌ 오류 {len(self.errors)}건:'
            ))
            for e in self.errors:
                self.stdout.write(f'  - {e}')
            raise SystemExit(1)
        if self.strict and self.warnings:
            raise SystemExit(2)

    def _ok(self, msg):
        self.stdout.write(self.style.SUCCESS(f'  ✓ {msg}'))

    def _warn(self, msg):
        self.warnings.append(msg)
        self.stdout.write(self.style.WARNING(f'  ⚠ {msg}'))

    def _err(self, msg):
        self.errors.append(msg)
        self.stdout.write(self.style.ERROR(f'  ✗ {msg}'))

    # ── 검증 항목 ─────────────────────────────────────

    def _check_trial_balance(self, as_of):
        self.stdout.write('1. 시산표 (Trial Balance) — APPROVED 전표 차변=대변')
        from apps.accounting.models import VoucherLine
        agg = VoucherLine.objects.filter(
            is_active=True, voucher__is_active=True,
            voucher__approval_status='APPROVED',
            voucher__voucher_date__lte=as_of,
        ).aggregate(d=Sum('debit'), c=Sum('credit'))
        debit = int(agg['d'] or 0)
        credit = int(agg['c'] or 0)
        if debit == credit:
            self._ok(f'차변 {debit:,} = 대변 {credit:,}')
        else:
            self._err(
                f'차대변 불일치: 차변 {debit:,} vs 대변 {credit:,} '
                f'(차이 {abs(debit - credit):,})'
            )

    def _check_stock_consistency(self):
        self.stdout.write('2. 재고 정합성 — Product.current_stock vs StockMovement 합계')
        from apps.inventory.models import Product, StockMovement
        mismatches = []
        for p in Product.objects.filter(is_active=True):
            if not p.is_stockable:
                continue
            net = StockMovement.objects.filter(
                product=p, is_active=True,
            ).aggregate(
                in_total=Sum('quantity', filter=Q(movement_type='IN')),
                out_total=Sum('quantity', filter=Q(movement_type='OUT')),
            )
            in_q = net['in_total'] or Decimal('0')
            out_q = net['out_total'] or Decimal('0')
            calc = in_q - out_q
            if calc != p.current_stock:
                mismatches.append(
                    f'{p.code}({p.name}): DB {p.current_stock} vs '
                    f'movements {calc} (차이 {p.current_stock - calc})'
                )
        if not mismatches:
            self._ok(f'재고 정합 — Product 전체 일치')
        else:
            head = '\n    '.join(mismatches[:5])
            self._warn(
                f'재고 불일치 {len(mismatches)}건 (상위 5건):\n    {head}'
            )

    def _check_ar_ap_balances(self):
        self.stdout.write('3. AR / AP 잔액 — amount >= paid_amount')
        from apps.accounting.models import AccountReceivable, AccountPayable
        ar_invalid = AccountReceivable.objects.filter(
            is_active=True, paid_amount__gt=F('amount'),
        ).count()
        ap_invalid = AccountPayable.objects.filter(
            is_active=True, paid_amount__gt=F('amount'),
        ).count()
        if ar_invalid == 0 and ap_invalid == 0:
            ar_total = AccountReceivable.objects.filter(
                is_active=True,
            ).aggregate(t=Sum(F('amount') - F('paid_amount')))['t'] or 0
            ap_total = AccountPayable.objects.filter(
                is_active=True,
            ).aggregate(t=Sum(F('amount') - F('paid_amount')))['t'] or 0
            self._ok(f'AR 미수 {int(ar_total):,}원 / AP 미지급 {int(ap_total):,}원')
        else:
            if ar_invalid:
                self._err(f'AR 과다입금 {ar_invalid}건 (paid > amount)')
            if ap_invalid:
                self._err(f'AP 과다지급 {ap_invalid}건 (paid > amount)')

    def _check_bank_balances(self):
        self.stdout.write('4. 결제계좌 잔액 — opening + Payment 합계 = balance')
        from apps.accounting.models import BankAccount, Payment
        from decimal import Decimal as D
        mismatches = []
        for ba in BankAccount.objects.filter(is_active=True):
            in_total = Payment.objects.filter(
                bank_account=ba, payment_type='RECEIPT', is_active=True,
            ).aggregate(t=Sum('amount'))['t'] or D(0)
            out_total = Payment.objects.filter(
                bank_account=ba, payment_type='DISBURSEMENT', is_active=True,
            ).aggregate(t=Sum('amount'))['t'] or D(0)
            calc = (ba.opening_balance or D(0)) + in_total - out_total
            if abs(calc - ba.balance) > D('0.01'):
                mismatches.append(
                    f'{ba.name}: DB {int(ba.balance):,} vs 계산 {int(calc):,} '
                    f'(차이 {int(ba.balance - calc):,})'
                )
        if not mismatches:
            self._ok('전 계좌 잔액 정합')
        else:
            head = '\n    '.join(mismatches[:5])
            self._warn(f'잔액 불일치 {len(mismatches)}건:\n    {head}')

    def _check_signal_orphans(self):
        self.stdout.write('5. 시그널 부수효과 — CONFIRMED 주문 = AR 존재')
        from apps.sales.models import Order
        from apps.accounting.models import AccountReceivable
        # 비스킵 (CONFIRMED 이상, 0원 아니고, 마감 외, NORMAL 유형) 주문 중
        # 활성 AR 0건인 케이스
        active_states = ['CONFIRMED', 'PARTIAL_SHIPPED', 'SHIPPED', 'DELIVERED', 'CLOSED']
        orphans = []
        for o in Order.objects.filter(
            is_active=True, order_type='NORMAL',
            status__in=active_states,
        ).exclude(grand_total=0)[:5000]:
            if not AccountReceivable.objects.filter(
                order=o, is_active=True,
            ).exists():
                orphans.append(f'{o.order_number}({o.status})')
        if not orphans:
            self._ok('CONFIRMED 이상 주문은 모두 AR 존재')
        else:
            head = ', '.join(orphans[:10])
            self._warn(
                f'AR 누락 주문 {len(orphans)}건 (상위 10): {head}'
            )

    def _check_closing_periods(self):
        self.stdout.write('6. ClosingPeriod — 마감월 이후 신규 전표 없음')
        from apps.accounting.models import ClosingPeriod, Voucher
        latest = ClosingPeriod.objects.filter(
            is_closed=True, is_active=True,
        ).order_by('-year', '-month').first()
        if not latest:
            self._ok('마감 미설정 — skip')
            return
        from datetime import date as _d
        boundary = _d(latest.year, latest.month, 28)
        leaks = Voucher.objects.filter(
            is_active=True,
            voucher_date__lte=boundary,
            created_at__gt=latest.closed_at or boundary,
        ).count() if latest.closed_at else 0
        if leaks == 0:
            self._ok(f'최신 마감 {latest.year}-{latest.month:02d} 이후 누설 0건')
        else:
            self._warn(
                f'마감 후 등록된 전표 {leaks}건 (마감기간 위반 가능)'
            )

    def _check_history_coverage(self):
        self.stdout.write('7. simple_history 커버리지 — Order 샘플 1건당 history 1건+')
        from apps.sales.models import Order
        if not Order.objects.filter(is_active=True).exists():
            self._ok('Order 데이터 없음 — skip')
            return
        sample = Order.objects.filter(is_active=True).order_by('-pk')[:50]
        no_history = [o.order_number for o in sample if o.history.count() == 0]
        if not no_history:
            self._ok(f'최근 50건 Order 모두 history 존재')
        else:
            head = ', '.join(no_history[:5])
            self._warn(
                f'history 누락 Order {len(no_history)}/50건 — '
                f'bulk_create 사용 시 발생: {head}'
            )
