from datetime import date
from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.inventory.models import Product
from apps.sales.models import Partner

from .models import (
    AccountCode,
    ClosingPeriod,
    Currency,
    ExchangeRate,
    FixedCost,
    TaxInvoice,
    TaxRate,
    Voucher,
    VoucherLine,
    WithholdingTax,
)
from apps.approval.models import ApprovalRequest


class TaxInvoiceTests(TestCase):
    """세금계산서 모델 테스트"""

    def setUp(self):
        self.partner = Partner.objects.create(
            code='P-001',
            name='테스트 거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
        )

    def test_tax_invoice_creation_with_partner(self):
        """거래처 연결된 세금계산서 생성"""
        invoice = TaxInvoice.objects.create(
            invoice_number='INV-2026-0001',
            invoice_type=TaxInvoice.InvoiceType.SALES,
            partner=self.partner,
            issue_date=date(2026, 3, 1),
            supply_amount=Decimal('1000000'),
            tax_amount=Decimal('100000'),
            total_amount=Decimal('1100000'),
        )
        self.assertEqual(invoice.partner, self.partner)
        self.assertEqual(invoice.invoice_type, 'SALES')
        self.assertEqual(str(invoice), 'INV-2026-0001 (매출)')

    def test_tax_invoice_unique_number(self):
        """세금계산서 번호 중복 불가"""
        TaxInvoice.objects.create(
            invoice_number='INV-DUP',
            invoice_type=TaxInvoice.InvoiceType.PURCHASE,
            partner=self.partner,
            issue_date=date(2026, 1, 1),
            supply_amount=100000,
            tax_amount=10000,
            total_amount=110000,
        )
        with self.assertRaises(IntegrityError):
            TaxInvoice.objects.create(
                invoice_number='INV-DUP',
                invoice_type=TaxInvoice.InvoiceType.SALES,
                partner=self.partner,
                issue_date=date(2026, 2, 1),
                supply_amount=200000,
                tax_amount=20000,
                total_amount=220000,
            )


class VoucherBalanceTests(TestCase):
    """전표 대차균형(복식부기) 테스트"""

    def setUp(self):
        self.account_debit = AccountCode.objects.create(
            code='101',
            name='현금',
            account_type=AccountCode.AccountType.ASSET,
        )
        self.account_credit = AccountCode.objects.create(
            code='401',
            name='매출',
            account_type=AccountCode.AccountType.REVENUE,
        )

    def test_balanced_voucher(self):
        """차변 합 == 대변 합이면 is_balanced True"""
        voucher = Voucher.objects.create(
            voucher_number='V-2026-0001',
            voucher_type=Voucher.VoucherType.RECEIPT,
            voucher_date=date(2026, 3, 1),
            description='매출 입금',
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=self.account_debit,
            debit=Decimal('500000'),
            credit=Decimal('0'),
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=self.account_credit,
            debit=Decimal('0'),
            credit=Decimal('500000'),
        )
        self.assertEqual(voucher.total_debit, Decimal('500000'))
        self.assertEqual(voucher.total_credit, Decimal('500000'))
        self.assertTrue(voucher.is_balanced)

    def test_unbalanced_voucher(self):
        """차변 합 != 대변 합이면 is_balanced False"""
        voucher = Voucher.objects.create(
            voucher_number='V-2026-0002',
            voucher_type=Voucher.VoucherType.PAYMENT,
            voucher_date=date(2026, 3, 2),
            description='불균형 전표',
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=self.account_debit,
            debit=Decimal('300000'),
            credit=Decimal('0'),
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=self.account_credit,
            debit=Decimal('0'),
            credit=Decimal('200000'),
        )
        self.assertNotEqual(voucher.total_debit, voucher.total_credit)
        self.assertFalse(voucher.is_balanced)

    def test_voucher_no_lines(self):
        """전표 항목 없으면 0 == 0 → 균형"""
        voucher = Voucher.objects.create(
            voucher_number='V-2026-0003',
            voucher_type=Voucher.VoucherType.TRANSFER,
            voucher_date=date(2026, 3, 3),
            description='빈 전표',
        )
        self.assertEqual(voucher.total_debit, 0)
        self.assertEqual(voucher.total_credit, 0)
        self.assertTrue(voucher.is_balanced)


class ApprovalRequestTests(TestCase):
    """결재/품의 상태 워크플로우 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='requester',
            password='testpass123',
            name='요청자',
            role=User.Role.STAFF,
        )
        self.approver = User.objects.create_user(
            username='approver',
            password='testpass123',
            name='결재자',
            role=User.Role.MANAGER,
        )

    def test_approval_workflow_draft_to_approved(self):
        """DRAFT → SUBMITTED → APPROVED 워크플로우"""
        req = ApprovalRequest.objects.create(
            request_number='AP-2026-0001',
            category=ApprovalRequest.DocCategory.PURCHASE,
            title='사무용품 구매',
            content='A4 용지 100박스',
            amount=Decimal('500000'),
            requester=self.user,
        )
        self.assertEqual(req.status, ApprovalRequest.Status.DRAFT)

        # DRAFT → SUBMITTED
        req.status = ApprovalRequest.Status.SUBMITTED
        req.submitted_at = timezone.now()
        req.save()
        req.refresh_from_db()
        self.assertEqual(req.status, ApprovalRequest.Status.SUBMITTED)
        self.assertIsNotNone(req.submitted_at)

        # SUBMITTED → APPROVED
        req.status = ApprovalRequest.Status.APPROVED
        req.approver = self.approver
        req.approved_at = timezone.now()
        req.save()
        req.refresh_from_db()
        self.assertEqual(req.status, ApprovalRequest.Status.APPROVED)
        self.assertEqual(req.approver, self.approver)
        self.assertIsNotNone(req.approved_at)

    def test_approval_rejection_with_reason(self):
        """결재 반려 시 사유 기록"""
        req = ApprovalRequest.objects.create(
            request_number='AP-2026-0002',
            category=ApprovalRequest.DocCategory.EXPENSE,
            title='출장비 정산',
            content='서울 출장 교통비',
            amount=Decimal('150000'),
            requester=self.user,
            status=ApprovalRequest.Status.SUBMITTED,
            submitted_at=timezone.now(),
        )
        reject_reason = '예산 초과로 반려합니다.'
        req.status = ApprovalRequest.Status.REJECTED
        req.reject_reason = reject_reason
        req.approver = self.approver
        req.save()
        req.refresh_from_db()
        self.assertEqual(req.status, ApprovalRequest.Status.REJECTED)
        self.assertEqual(req.reject_reason, reject_reason)


class FixedCostTests(TestCase):
    """고정비 월별 집계 테스트"""

    def test_monthly_aggregation(self):
        """같은 달 고정비 합산"""
        target_month = date(2026, 3, 1)
        FixedCost.objects.create(
            category=FixedCost.CostCategory.RENT,
            name='사무실 임대료',
            amount=Decimal('2000000'),
            month=target_month,
        )
        FixedCost.objects.create(
            category=FixedCost.CostCategory.TELECOM,
            name='인터넷 요금',
            amount=Decimal('50000'),
            month=target_month,
        )
        FixedCost.objects.create(
            category=FixedCost.CostCategory.LABOR,
            name='인건비',
            amount=Decimal('3000000'),
            month=target_month,
        )
        # 다른 달 비용 (집계에서 제외)
        FixedCost.objects.create(
            category=FixedCost.CostCategory.RENT,
            name='사무실 임대료',
            amount=Decimal('2000000'),
            month=date(2026, 2, 1),
        )

        from django.db.models import Sum

        total = FixedCost.objects.filter(month=target_month).aggregate(
            total=Sum('amount')
        )['total']
        self.assertEqual(total, Decimal('5050000'))

    def test_str_representation(self):
        """고정비 문자열 표현"""
        cost = FixedCost.objects.create(
            category=FixedCost.CostCategory.SUBSCRIPTION,
            name='클라우드 구독',
            amount=Decimal('100000'),
            month=date(2026, 3, 1),
        )
        self.assertEqual(str(cost), '클라우드 구독 (2026-03)')


class WithholdingTaxTests(TestCase):
    """원천징수 실지급액 계산 테스트"""

    def test_net_amount_calculation(self):
        """실지급액 = 지급액 - 원천징수액"""
        wht = WithholdingTax.objects.create(
            tax_type=WithholdingTax.TaxType.INCOME,
            payee_name='홍길동',
            payment_date=date(2026, 3, 15),
            gross_amount=Decimal('5000000'),
            tax_rate=Decimal('3.30'),
            tax_amount=Decimal('165000'),
            net_amount=Decimal('4835000'),
        )
        self.assertEqual(
            wht.net_amount,
            wht.gross_amount - wht.tax_amount,
        )

    def test_str_representation(self):
        """원천징수 문자열 표현"""
        wht = WithholdingTax.objects.create(
            tax_type=WithholdingTax.TaxType.CORPORATE,
            payee_name='(주)테스트',
            payment_date=date(2026, 6, 1),
            gross_amount=Decimal('10000000'),
            tax_rate=Decimal('2.20'),
            tax_amount=Decimal('220000'),
            net_amount=Decimal('9780000'),
        )
        self.assertEqual(str(wht), '(주)테스트 - 2026-06-01')


class VoucherLineTests(TestCase):
    """전표 항목 상세 테스트"""

    def setUp(self):
        self.account_cash = AccountCode.objects.create(
            code='110', name='보통예금',
            account_type=AccountCode.AccountType.ASSET,
        )
        self.account_expense = AccountCode.objects.create(
            code='501', name='복리후생비',
            account_type=AccountCode.AccountType.EXPENSE,
        )
        self.voucher = Voucher.objects.create(
            voucher_number='V-LINE-001',
            voucher_type=Voucher.VoucherType.PAYMENT,
            voucher_date=date(2026, 3, 10),
            description='복리후생비 지출',
        )

    def test_voucher_line_str(self):
        """전표항목 문자열 표현"""
        line = VoucherLine.objects.create(
            voucher=self.voucher,
            account=self.account_expense,
            debit=Decimal('100000'),
            credit=Decimal('0'),
        )
        self.assertIn('복리후생비', str(line))
        self.assertIn('100000', str(line))

    def test_multiple_lines_balance(self):
        """복수 전표항목 균형 확인"""
        VoucherLine.objects.create(
            voucher=self.voucher, account=self.account_expense,
            debit=Decimal('100000'), credit=Decimal('0'),
        )
        VoucherLine.objects.create(
            voucher=self.voucher, account=self.account_expense,
            debit=Decimal('50000'), credit=Decimal('0'),
        )
        VoucherLine.objects.create(
            voucher=self.voucher, account=self.account_cash,
            debit=Decimal('0'), credit=Decimal('150000'),
        )
        self.assertEqual(self.voucher.total_debit, Decimal('150000'))
        self.assertEqual(self.voucher.total_credit, Decimal('150000'))
        self.assertTrue(self.voucher.is_balanced)

    def test_voucher_approval_status_choices(self):
        """전표 승인 상태 선택지"""
        choices = dict(Voucher.ApprovalStatus.choices)
        self.assertIn('DRAFT', choices)
        self.assertIn('SUBMITTED', choices)
        self.assertIn('APPROVED', choices)
        self.assertIn('REJECTED', choices)

    def test_voucher_approval_flow(self):
        """전표 승인 워크플로우"""
        self.assertEqual(self.voucher.approval_status, 'DRAFT')
        self.voucher.approval_status = Voucher.ApprovalStatus.SUBMITTED
        self.voucher.save()
        self.voucher.refresh_from_db()
        self.assertEqual(self.voucher.approval_status, 'SUBMITTED')

        self.voucher.approval_status = Voucher.ApprovalStatus.APPROVED
        self.voucher.save()
        self.voucher.refresh_from_db()
        self.assertEqual(self.voucher.approval_status, 'APPROVED')


class ApprovalStepTests(TestCase):
    """다단계 결재 테스트"""

    def setUp(self):
        self.requester = User.objects.create_user(
            username='step_req', password='testpass123',
            name='기안자', role=User.Role.STAFF,
        )
        self.approver1 = User.objects.create_user(
            username='step_appr1', password='testpass123',
            name='1차결재자', role=User.Role.MANAGER,
        )
        self.approver2 = User.objects.create_user(
            username='step_appr2', password='testpass123',
            name='2차결재자', role=User.Role.ADMIN,
        )

    def test_multi_step_approval(self):
        """다단계 결재선 생성 및 순차 승인"""
        from apps.approval.models import ApprovalStep

        req = ApprovalRequest.objects.create(
            request_number='AP-STEP-001',
            category=ApprovalRequest.DocCategory.PURCHASE,
            title='다단계 결재 테스트',
            content='내용',
            amount=Decimal('1000000'),
            requester=self.requester,
            status=ApprovalRequest.Status.SUBMITTED,
            submitted_at=timezone.now(),
        )
        step1 = ApprovalStep.objects.create(
            request=req, step_order=1,
            approver=self.approver1,
        )
        step2 = ApprovalStep.objects.create(
            request=req, step_order=2,
            approver=self.approver2,
        )
        # 1단계 승인
        step1.status = ApprovalStep.Status.APPROVED
        step1.acted_at = timezone.now()
        step1.comment = '승인합니다'
        step1.save()
        step1.refresh_from_db()
        self.assertEqual(step1.status, 'APPROVED')

        # 2단계 승인
        step2.status = ApprovalStep.Status.APPROVED
        step2.acted_at = timezone.now()
        step2.save()
        step2.refresh_from_db()
        self.assertEqual(step2.status, 'APPROVED')

        # 모든 단계 승인 확인
        all_approved = all(
            s.status == 'APPROVED'
            for s in req.steps.all()
        )
        self.assertTrue(all_approved)

    def test_approval_step_rejection(self):
        """결재 단계 반려"""
        from apps.approval.models import ApprovalStep

        req = ApprovalRequest.objects.create(
            request_number='AP-STEP-REJ',
            category=ApprovalRequest.DocCategory.EXPENSE,
            title='반려 테스트',
            content='내용',
            amount=Decimal('500000'),
            requester=self.requester,
            status=ApprovalRequest.Status.SUBMITTED,
            submitted_at=timezone.now(),
        )
        step = ApprovalStep.objects.create(
            request=req, step_order=1,
            approver=self.approver1,
        )
        step.status = ApprovalStep.Status.REJECTED
        step.comment = '예산 부족'
        step.acted_at = timezone.now()
        step.save()
        step.refresh_from_db()
        self.assertEqual(step.status, 'REJECTED')
        self.assertEqual(step.comment, '예산 부족')

    def test_approval_step_str(self):
        """결재 단계 문자열 표현"""
        from apps.approval.models import ApprovalStep

        req = ApprovalRequest.objects.create(
            request_number='AP-STEP-STR',
            category=ApprovalRequest.DocCategory.GENERAL,
            title='문자열 테스트',
            content='내용',
            requester=self.requester,
        )
        step = ApprovalStep.objects.create(
            request=req, step_order=1,
            approver=self.approver1,
        )
        result = str(step)
        self.assertIn('AP-STEP-STR', result)
        self.assertIn('1', result)

    def test_unique_together_request_step_order(self):
        """같은 결재요청에 같은 단계순서 중복 불가"""
        from apps.approval.models import ApprovalStep

        req = ApprovalRequest.objects.create(
            request_number='AP-STEP-UNIQ',
            category=ApprovalRequest.DocCategory.GENERAL,
            title='중복 테스트',
            content='내용',
            requester=self.requester,
        )
        ApprovalStep.objects.create(
            request=req, step_order=1,
            approver=self.approver1,
        )
        with self.assertRaises(IntegrityError):
            ApprovalStep.objects.create(
                request=req, step_order=1,
                approver=self.approver2,
            )


class AccountReceivablePayableTests(TestCase):
    """미수금/미지급금 잔액 추적 테스트"""

    def setUp(self):
        self.partner = Partner.objects.create(
            code='ARAP-001', name='미수미지급 거래처',
            partner_type=Partner.PartnerType.BOTH,
        )

    def test_ar_remaining_amount(self):
        """미수금 잔액 계산"""
        from apps.accounting.models import AccountReceivable
        ar = AccountReceivable.objects.create(
            partner=self.partner,
            amount=Decimal('1000000'),
            paid_amount=Decimal('300000'),
            due_date=date(2026, 4, 1),
        )
        self.assertEqual(ar.remaining_amount, Decimal('700000'))

    def test_ar_fully_paid(self):
        """미수금 완납 시 잔액 0"""
        from apps.accounting.models import AccountReceivable
        ar = AccountReceivable.objects.create(
            partner=self.partner,
            amount=Decimal('500000'),
            paid_amount=Decimal('500000'),
            due_date=date(2026, 4, 1),
            status=AccountReceivable.Status.PAID,
        )
        self.assertEqual(ar.remaining_amount, Decimal('0'))

    def test_ar_is_overdue(self):
        """미수금 연체 판정"""
        from apps.accounting.models import AccountReceivable
        ar = AccountReceivable.objects.create(
            partner=self.partner,
            amount=Decimal('500000'),
            due_date=date(2020, 1, 1),  # 과거 날짜
        )
        self.assertTrue(ar.is_overdue)

    def test_ar_not_overdue_when_paid(self):
        """완납 시 연체 아님"""
        from apps.accounting.models import AccountReceivable
        ar = AccountReceivable.objects.create(
            partner=self.partner,
            amount=Decimal('500000'),
            paid_amount=Decimal('500000'),
            due_date=date(2020, 1, 1),
            status=AccountReceivable.Status.PAID,
        )
        self.assertFalse(ar.is_overdue)

    def test_ar_str(self):
        """미수금 문자열 표현"""
        from apps.accounting.models import AccountReceivable
        ar = AccountReceivable.objects.create(
            partner=self.partner,
            amount=Decimal('1000000'),
            due_date=date(2026, 4, 1),
        )
        result = str(ar)
        self.assertIn('미수미지급 거래처', result)
        self.assertIn('1000000', result)

    def test_ap_remaining_amount(self):
        """미지급금 잔액 계산"""
        from apps.accounting.models import AccountPayable
        ap = AccountPayable.objects.create(
            partner=self.partner,
            amount=Decimal('2000000'),
            paid_amount=Decimal('500000'),
            due_date=date(2026, 4, 1),
        )
        self.assertEqual(ap.remaining_amount, Decimal('1500000'))

    def test_ap_is_overdue(self):
        """미지급금 연체 판정"""
        from apps.accounting.models import AccountPayable
        ap = AccountPayable.objects.create(
            partner=self.partner,
            amount=Decimal('1000000'),
            due_date=date(2020, 1, 1),
        )
        self.assertTrue(ap.is_overdue)

    def test_ap_str(self):
        """미지급금 문자열 표현"""
        from apps.accounting.models import AccountPayable
        ap = AccountPayable.objects.create(
            partner=self.partner,
            amount=Decimal('3000000'),
            due_date=date(2026, 5, 1),
        )
        result = str(ap)
        self.assertIn('미수미지급 거래처', result)
        self.assertIn('3000000', result)


class AccountCodeTests(TestCase):
    """계정과목 테스트"""

    def test_account_code_creation(self):
        """계정과목 생성"""
        ac = AccountCode.objects.create(
            code='100', name='현금및현금성자산',
            account_type=AccountCode.AccountType.ASSET,
        )
        self.assertEqual(ac.code, '100')
        self.assertEqual(ac.account_type, 'ASSET')

    def test_account_code_str(self):
        """계정과목 문자열 표현"""
        ac = AccountCode.objects.create(
            code='200', name='매입채무',
            account_type=AccountCode.AccountType.LIABILITY,
        )
        self.assertEqual(str(ac), '[200] 매입채무')

    def test_account_code_unique(self):
        """계정코드 중복 불가"""
        AccountCode.objects.create(
            code='DUP', name='중복1',
            account_type=AccountCode.AccountType.ASSET,
        )
        with self.assertRaises(IntegrityError):
            AccountCode.objects.create(
                code='DUP', name='중복2',
                account_type=AccountCode.AccountType.LIABILITY,
            )

    def test_account_type_choices(self):
        """계정유형 선택지"""
        choices = dict(AccountCode.AccountType.choices)
        self.assertIn('ASSET', choices)
        self.assertIn('LIABILITY', choices)
        self.assertIn('EQUITY', choices)
        self.assertIn('REVENUE', choices)
        self.assertIn('EXPENSE', choices)

    def test_account_code_hierarchy(self):
        """계정과목 상하위 관계"""
        parent = AccountCode.objects.create(
            code='100', name='유동자산',
            account_type=AccountCode.AccountType.ASSET,
        )
        child = AccountCode.objects.create(
            code='101', name='현금',
            account_type=AccountCode.AccountType.ASSET,
            parent=parent,
        )
        self.assertEqual(child.parent, parent)

    def test_account_code_ordering(self):
        """계정과목은 코드순 정렬"""
        AccountCode.objects.create(
            code='300', name='자본금',
            account_type=AccountCode.AccountType.EQUITY,
        )
        AccountCode.objects.create(
            code='100', name='현금',
            account_type=AccountCode.AccountType.ASSET,
        )
        codes = list(AccountCode.objects.all())
        self.assertEqual(codes[0].code, '100')
        self.assertEqual(codes[1].code, '300')


class TaxRateTests(TestCase):
    """세율 테스트"""

    def test_tax_rate_creation(self):
        """세율 생성"""
        rate = TaxRate.objects.create(
            name='부가가치세',
            code='VAT10',
            rate=Decimal('10.00'),
            is_default=True,
            effective_from=date(2026, 1, 1),
        )
        self.assertEqual(rate.rate, Decimal('10.00'))
        self.assertTrue(rate.is_default)

    def test_tax_rate_str(self):
        """세율 문자열 표현"""
        rate = TaxRate.objects.create(
            name='영세율',
            code='ZERO',
            rate=Decimal('0.00'),
            effective_from=date(2026, 1, 1),
        )
        self.assertEqual(str(rate), '영세율 (0.00%)')

    def test_tax_rate_unique_code(self):
        """세율코드 중복 불가"""
        TaxRate.objects.create(
            name='세율1', code='DUP-RATE',
            rate=Decimal('10.00'),
            effective_from=date(2026, 1, 1),
        )
        with self.assertRaises(IntegrityError):
            TaxRate.objects.create(
                name='세율2', code='DUP-RATE',
                rate=Decimal('5.00'),
                effective_from=date(2026, 1, 1),
            )


class PaymentTests(TestCase):
    """입출금 기록 테스트"""

    def setUp(self):
        self.partner = Partner.objects.create(
            code='PAY-001', name='입출금 거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
        )

    def test_payment_creation(self):
        """입출금 기록 생성"""
        from apps.accounting.models import Payment
        payment = Payment.objects.create(
            payment_number='PAY-2026-001',
            payment_type=Payment.PaymentType.RECEIPT,
            partner=self.partner,
            amount=Decimal('500000'),
            payment_date=date(2026, 3, 17),
        )
        self.assertEqual(payment.payment_type, 'RECEIPT')
        self.assertEqual(payment.amount, Decimal('500000'))

    def test_payment_str(self):
        """입출금 문자열 표현"""
        from apps.accounting.models import Payment
        payment = Payment.objects.create(
            payment_number='PAY-STR-001',
            payment_type=Payment.PaymentType.DISBURSEMENT,
            partner=self.partner,
            amount=Decimal('300000'),
            payment_date=date(2026, 3, 17),
        )
        result = str(payment)
        self.assertIn('PAY-STR-001', result)
        self.assertIn('출금', result)

    def test_payment_method_choices(self):
        """결제수단 선택지"""
        from apps.accounting.models import Payment
        choices = dict(Payment.PaymentMethod.choices)
        self.assertIn('BANK_TRANSFER', choices)
        self.assertIn('CASH', choices)
        self.assertIn('CHECK', choices)
        self.assertIn('CARD', choices)


class ClosingPeriodTest(TestCase):
    """결산마감 모델 테스트"""

    def test_closing_period_creation(self):
        """ClosingPeriod 생성 가능"""
        period = ClosingPeriod.objects.create(
            year=2026,
            month=3,
            is_closed=False,
        )
        self.assertEqual(period.year, 2026)
        self.assertEqual(period.month, 3)
        self.assertFalse(period.is_closed)
        self.assertEqual(str(period), '2026년 03월 미마감')

    def test_unique_year_month(self):
        """동일 년/월 중복 생성 불가"""
        ClosingPeriod.objects.create(year=2026, month=6)
        with self.assertRaises(IntegrityError):
            ClosingPeriod.objects.create(year=2026, month=6)


class CurrencyTest(TestCase):
    """통화 모델 테스트"""

    def test_currency_creation(self):
        """Currency 생성 가능"""
        currency = Currency.objects.create(
            code='USD',
            name='미국 달러',
            symbol='$',
            decimal_places=2,
            is_base=False,
        )
        self.assertEqual(currency.code, 'USD')
        self.assertEqual(currency.name, '미국 달러')
        self.assertEqual(currency.symbol, '$')
        self.assertEqual(str(currency), 'USD (미국 달러)')

    def test_base_currency_unique(self):
        """is_base=True인 통화가 하나만 존재하도록"""
        krw = Currency.objects.create(
            code='KRW', name='원화', symbol='₩',
            decimal_places=0, is_base=True,
        )
        # 두 번째 기준통화 생성 시 기존 기준통화가 해제됨
        usd = Currency.objects.create(
            code='USD', name='미국 달러', symbol='$',
            decimal_places=2, is_base=True,
        )
        krw.refresh_from_db()
        self.assertFalse(krw.is_base)
        self.assertTrue(usd.is_base)
        # 기준통화는 하나만 존재
        self.assertEqual(
            Currency.objects.filter(is_base=True).count(), 1,
        )


class ExchangeRateTest(TestCase):
    """환율 모델 테스트"""

    def setUp(self):
        self.currency = Currency.objects.create(
            code='USD', name='미국 달러', symbol='$',
        )

    def test_exchange_rate_creation(self):
        """ExchangeRate 생성 가능"""
        rate = ExchangeRate.objects.create(
            currency=self.currency,
            rate_date=date(2026, 3, 20),
            rate=Decimal('1350.5000'),
        )
        self.assertEqual(rate.currency, self.currency)
        self.assertEqual(rate.rate, Decimal('1350.5000'))
        self.assertIn('USD', str(rate))
        self.assertIn('2026-03-20', str(rate))

    def test_unique_currency_date(self):
        """동일 통화/날짜 중복 불가"""
        ExchangeRate.objects.create(
            currency=self.currency,
            rate_date=date(2026, 3, 20),
            rate=Decimal('1350.0000'),
        )
        with self.assertRaises(IntegrityError):
            ExchangeRate.objects.create(
                currency=self.currency,
                rate_date=date(2026, 3, 20),
                rate=Decimal('1355.0000'),
            )
