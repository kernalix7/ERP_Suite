from datetime import date
from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase

from apps.accounting.models import AccountCode, Voucher, VoucherLine

from .models import (
    Distribution,
    EquityChange,
    Investment,
    InvestmentRound,
    Investor,
)


class InvestorTests(TestCase):
    """투자자 모델 테스트"""

    def test_creation(self):
        """투자자 생성"""
        investor = Investor.objects.create(
            code='INV-001', name='테스트 투자자',
            company='테스트 벤처캐피탈',
            phone='02-1234-5678',
            email='investor@test.com',
            registration_date=date(2026, 1, 1),
        )
        self.assertIn('INV-001', str(investor))
        self.assertEqual(investor.company, '테스트 벤처캐피탈')

    def test_total_invested_no_investments(self):
        """투자 내역 없을 때 total_invested = 0"""
        investor = Investor.objects.create(
            code='INV-NEW', name='신규 투자자',
            registration_date=date(2026, 1, 1),
        )
        self.assertEqual(investor.total_invested, 0)

    def test_total_invested_with_investments(self):
        """투자 내역 합산"""
        investor = Investor.objects.create(
            code='INV-MULTI', name='다중투자자',
            registration_date=date(2025, 1, 1),
        )
        round1 = InvestmentRound.objects.create(
            code='RND-SEED1', name='시드 라운드',
            round_type=InvestmentRound.RoundType.SEED,
            round_date=date(2025, 6, 1),
        )
        round2 = InvestmentRound.objects.create(
            code='RND-SA1', name='시리즈A',
            round_type=InvestmentRound.RoundType.SERIES_A,
            round_date=date(2026, 1, 1),
        )
        Investment.objects.create(
            investor=investor,
            round=round1,
            amount=Decimal('100000000'),
            share_percentage=Decimal('10.000'),
            investment_date=date(2025, 6, 1),
        )
        Investment.objects.create(
            investor=investor,
            round=round2,
            amount=Decimal('300000000'),
            share_percentage=Decimal('15.000'),
            investment_date=date(2026, 1, 1),
        )
        self.assertEqual(investor.total_invested, Decimal('400000000'))

    def test_current_share_from_equity_change(self):
        """최신 지분변동으로 현재 지분율 조회"""
        investor = Investor.objects.create(
            code='INV-EQT', name='지분 투자자',
            registration_date=date(2025, 1, 1),
        )
        round1 = InvestmentRound.objects.create(
            code='RND-SEED2', name='시드',
            round_type=InvestmentRound.RoundType.SEED,
            round_date=date(2025, 6, 1),
        )
        Investment.objects.create(
            investor=investor,
            round=round1,
            amount=Decimal('100000000'),
            share_percentage=Decimal('10.000'),
            investment_date=date(2025, 6, 1),
        )
        EquityChange.objects.create(
            investor=investor,
            change_type=EquityChange.ChangeType.DILUTION,
            change_date=date(2026, 1, 1),
            before_percentage=Decimal('10.000'),
            after_percentage=Decimal('7.500'),
        )
        self.assertEqual(investor.current_share, Decimal('7.500'))

    def test_current_share_no_equity_change(self):
        """지분변동 없으면 최근 투자의 share_percentage 반환"""
        investor = Investor.objects.create(
            code='INV-NOCHG', name='무변동 투자자',
            registration_date=date(2025, 1, 1),
        )
        round1 = InvestmentRound.objects.create(
            code='RND-SEED3', name='시드',
            round_type=InvestmentRound.RoundType.SEED,
            round_date=date(2025, 6, 1),
        )
        Investment.objects.create(
            investor=investor,
            round=round1,
            amount=Decimal('50000000'),
            share_percentage=Decimal('5.000'),
            investment_date=date(2025, 6, 1),
        )
        self.assertEqual(investor.current_share, Decimal('5.000'))

    def test_total_distributed(self):
        """지급완료(PAID) 배당만 합산"""
        investor = Investor.objects.create(
            code='INV-DIST', name='배당 투자자',
            registration_date=date(2025, 1, 1),
        )
        Distribution.objects.create(
            investor=investor,
            distribution_type=Distribution.DistributionType.DIVIDEND,
            amount=Decimal('10000000'),
            scheduled_date=date(2026, 3, 1),
            status=Distribution.PaymentStatus.PAID,
            fiscal_year=2025,
        )
        Distribution.objects.create(
            investor=investor,
            distribution_type=Distribution.DistributionType.DIVIDEND,
            amount=Decimal('5000000'),
            scheduled_date=date(2026, 6, 1),
            status=Distribution.PaymentStatus.SCHEDULED,
            fiscal_year=2025,
        )
        # PAID 건만 합산
        self.assertEqual(investor.total_distributed, Decimal('10000000'))


class InvestmentRoundTests(TestCase):
    """투자라운드 모델 테스트"""

    def test_creation(self):
        """투자라운드 생성"""
        inv_round = InvestmentRound.objects.create(
            code='RND-SA-CRT', name='시리즈A 라운드',
            round_type=InvestmentRound.RoundType.SERIES_A,
            target_amount=Decimal('1000000000'),
            round_date=date(2026, 1, 15),
            pre_valuation=Decimal('5000000000'),
            post_valuation=Decimal('6000000000'),
        )
        self.assertIn('RND-SA-CRT', str(inv_round))

    def test_total_invested_and_investor_count(self):
        """라운드 총 투자금액 및 투자자 수"""
        inv_round = InvestmentRound.objects.create(
            code='RND-SEED-CNT', name='시드 라운드',
            round_type=InvestmentRound.RoundType.SEED,
            round_date=date(2025, 6, 1),
        )
        investor_a = Investor.objects.create(
            code='INV-A', name='투자자A',
            registration_date=date(2025, 1, 1),
        )
        investor_b = Investor.objects.create(
            code='INV-B', name='투자자B',
            registration_date=date(2025, 2, 1),
        )
        Investment.objects.create(
            investor=investor_a,
            round=inv_round,
            amount=Decimal('200000000'),
            share_percentage=Decimal('10.000'),
            investment_date=date(2025, 6, 1),
        )
        Investment.objects.create(
            investor=investor_b,
            round=inv_round,
            amount=Decimal('100000000'),
            share_percentage=Decimal('5.000'),
            investment_date=date(2025, 6, 1),
        )
        self.assertEqual(inv_round.total_invested, Decimal('300000000'))
        self.assertEqual(inv_round.investor_count, 2)


class InvestmentTests(TestCase):
    """투자내역 모델 테스트"""

    def setUp(self):
        self.investor = Investor.objects.create(
            code='INV-INV', name='투자자',
            registration_date=date(2025, 1, 1),
        )
        self.inv_round = InvestmentRound.objects.create(
            code='RND-SEED-INV', name='시드',
            round_type=InvestmentRound.RoundType.SEED,
            round_date=date(2025, 6, 1),
        )

    def test_creation(self):
        """투자내역 생성"""
        inv = Investment.objects.create(
            investor=self.investor,
            round=self.inv_round,
            amount=Decimal('100000000'),
            share_percentage=Decimal('10.000'),
            investment_date=date(2025, 6, 1),
        )
        self.assertIn('투자자', str(inv))
        self.assertIn('시드', str(inv))

    def test_unique_together_investor_round(self):
        """같은 투자자-라운드 조합은 중복 불가"""
        Investment.objects.create(
            investor=self.investor,
            round=self.inv_round,
            amount=Decimal('100000000'),
            share_percentage=Decimal('10.000'),
            investment_date=date(2025, 6, 1),
        )
        with self.assertRaises(IntegrityError):
            Investment.objects.create(
                investor=self.investor,
                round=self.inv_round,
                amount=Decimal('50000000'),
                share_percentage=Decimal('5.000'),
                investment_date=date(2025, 7, 1),
            )


class EquityChangeTests(TestCase):
    """지분변동 모델 테스트"""

    def test_creation(self):
        """지분변동 생성"""
        investor = Investor.objects.create(
            code='INV-EQCHG', name='지분변동 투자자',
            registration_date=date(2025, 1, 1),
        )
        ec = EquityChange.objects.create(
            investor=investor,
            change_type=EquityChange.ChangeType.INVESTMENT,
            change_date=date(2025, 6, 1),
            before_percentage=Decimal('0.000'),
            after_percentage=Decimal('10.000'),
        )
        self.assertEqual(
            str(ec), '지분변동 투자자 0.000% → 10.000%'
        )

    def test_dilution(self):
        """희석에 의한 지분 감소"""
        investor = Investor.objects.create(
            code='INV-DIL', name='희석 투자자',
            registration_date=date(2025, 1, 1),
        )
        ec = EquityChange.objects.create(
            investor=investor,
            change_type=EquityChange.ChangeType.DILUTION,
            change_date=date(2026, 1, 1),
            before_percentage=Decimal('10.000'),
            after_percentage=Decimal('7.500'),
        )
        self.assertLess(ec.after_percentage, ec.before_percentage)


class DistributionTests(TestCase):
    """배당/분배 모델 테스트"""

    def setUp(self):
        self.investor = Investor.objects.create(
            code='INV-DIST2', name='배당 투자자',
            registration_date=date(2025, 1, 1),
        )

    def test_creation(self):
        """배당 생성"""
        dist = Distribution.objects.create(
            investor=self.investor,
            distribution_type=Distribution.DistributionType.DIVIDEND,
            amount=Decimal('10000000'),
            scheduled_date=date(2026, 3, 31),
            status=Distribution.PaymentStatus.SCHEDULED,
            fiscal_year=2025,
        )
        self.assertEqual(str(dist), '배당 투자자 - 배당 (2025)')
        self.assertEqual(dist.status, 'SCHEDULED')

    def test_payment_status_workflow(self):
        """SCHEDULED → PENDING → PAID 상태 전환"""
        dist = Distribution.objects.create(
            investor=self.investor,
            distribution_type=Distribution.DistributionType.PROFIT_SHARE,
            amount=Decimal('5000000'),
            scheduled_date=date(2026, 6, 30),
            fiscal_year=2025,
        )
        self.assertEqual(dist.status, Distribution.PaymentStatus.SCHEDULED)

        dist.status = Distribution.PaymentStatus.PENDING
        dist.save()
        dist.refresh_from_db()
        self.assertEqual(dist.status, Distribution.PaymentStatus.PENDING)

        dist.status = Distribution.PaymentStatus.PAID
        dist.paid_date = date(2026, 6, 30)
        dist.save()
        dist.refresh_from_db()
        self.assertEqual(dist.status, Distribution.PaymentStatus.PAID)
        self.assertEqual(dist.paid_date, date(2026, 6, 30))


class DistributionSignalTest(TestCase):
    """배당/분배 시그널 테스트"""

    def setUp(self):
        self.investor = Investor.objects.create(
            code='INV-SIG', name='시그널 투자자',
            registration_date=date(2025, 1, 1),
        )
        # 시그널 테스트용 계정과목
        self.acct_330 = AccountCode.objects.create(
            code='330', name='이익잉여금',
            account_type='EQUITY',
        )
        self.acct_270 = AccountCode.objects.create(
            code='270', name='미지급배당금',
            account_type='LIABILITY',
        )
        self.acct_101 = AccountCode.objects.create(
            code='101', name='보통예금',
            account_type='ASSET',
        )

    def test_pending_distribution_creates_voucher(self):
        """SCHEDULED → PENDING 전환 시 배당 의무 전표 생성"""
        dist = Distribution.objects.create(
            investor=self.investor,
            distribution_type=Distribution.DistributionType.DIVIDEND,
            amount=Decimal('10000000'),
            scheduled_date=date(2026, 3, 31),
            status=Distribution.PaymentStatus.SCHEDULED,
            fiscal_year=2025,
        )
        before_count = Voucher.objects.count()
        dist.status = Distribution.PaymentStatus.PENDING
        dist.save()

        self.assertEqual(Voucher.objects.count(), before_count + 1)
        voucher = Voucher.objects.latest('pk')
        self.assertIn('시그널 투자자', voucher.description)
        self.assertTrue(voucher.is_balanced)
        lines = voucher.lines.all()
        self.assertEqual(lines.count(), 2)
        debit_line = lines.get(debit__gt=0)
        credit_line = lines.get(credit__gt=0)
        self.assertEqual(debit_line.account, self.acct_330)
        self.assertEqual(debit_line.debit, Decimal('10000000'))
        self.assertEqual(credit_line.account, self.acct_270)
        self.assertEqual(credit_line.credit, Decimal('10000000'))

    def test_paid_distribution_creates_payment_voucher(self):
        """PENDING → PAID 전환 시 지급 전표 생성"""
        dist = Distribution.objects.create(
            investor=self.investor,
            distribution_type=Distribution.DistributionType.DIVIDEND,
            amount=Decimal('5000000'),
            scheduled_date=date(2026, 6, 30),
            status=Distribution.PaymentStatus.SCHEDULED,
            fiscal_year=2025,
        )
        # PENDING 전환
        dist.status = Distribution.PaymentStatus.PENDING
        dist.save()
        pending_count = Voucher.objects.count()

        # PAID 전환
        dist.status = Distribution.PaymentStatus.PAID
        dist.paid_date = date(2026, 6, 30)
        dist.save()

        self.assertEqual(Voucher.objects.count(), pending_count + 1)
        voucher = Voucher.objects.latest('pk')
        self.assertIn('지급완료', voucher.description)
        self.assertTrue(voucher.is_balanced)
        lines = voucher.lines.all()
        debit_line = lines.get(debit__gt=0)
        credit_line = lines.get(credit__gt=0)
        self.assertEqual(debit_line.account, self.acct_270)
        self.assertEqual(credit_line.account, self.acct_101)

    def test_created_as_pending_creates_voucher(self):
        """PENDING 상태로 직접 생성 시 전표 생성"""
        before_count = Voucher.objects.count()
        Distribution.objects.create(
            investor=self.investor,
            distribution_type=Distribution.DistributionType.PROFIT_SHARE,
            amount=Decimal('3000000'),
            scheduled_date=date(2026, 9, 30),
            status=Distribution.PaymentStatus.PENDING,
            fiscal_year=2025,
        )
        self.assertEqual(Voucher.objects.count(), before_count + 1)

    def test_scheduled_creation_no_voucher(self):
        """SCHEDULED 상태 생성 시 전표 미생성"""
        before_count = Voucher.objects.count()
        Distribution.objects.create(
            investor=self.investor,
            distribution_type=Distribution.DistributionType.DIVIDEND,
            amount=Decimal('8000000'),
            scheduled_date=date(2026, 12, 31),
            status=Distribution.PaymentStatus.SCHEDULED,
            fiscal_year=2025,
        )
        self.assertEqual(Voucher.objects.count(), before_count)

    def test_no_voucher_without_accounts(self):
        """계정과목 없으면 전표 미생성 (에러 없이 진행)"""
        self.acct_330.delete()
        before_count = Voucher.objects.count()
        dist = Distribution.objects.create(
            investor=self.investor,
            distribution_type=Distribution.DistributionType.DIVIDEND,
            amount=Decimal('2000000'),
            scheduled_date=date(2026, 3, 31),
            status=Distribution.PaymentStatus.SCHEDULED,
            fiscal_year=2025,
        )
        dist.status = Distribution.PaymentStatus.PENDING
        dist.save()
        self.assertEqual(Voucher.objects.count(), before_count)
