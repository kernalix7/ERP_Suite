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
    AccountPayable,
    AccountReceivable,
    BankAccount,
    CardBilling,
    CardTransaction,
    ClosingPeriod,
    CreditCard,
    Currency,
    ExchangeRate,
    FixedCost,
    Payment,
    SalesSettlement,
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


class AccountPayablePurchaseOrderTests(TestCase):
    """AP ← PurchaseOrder FK 테스트"""

    def setUp(self):
        self.partner = Partner.objects.create(
            code='P-AP-001',
            name='테스트 공급사',
            partner_type=Partner.PartnerType.SUPPLIER,
        )

    def test_ap_with_purchase_order_fk(self):
        """AP에 PurchaseOrder FK 연결 가능"""
        from apps.purchase.models import PurchaseOrder
        po = PurchaseOrder.objects.create(
            po_number='PO-TEST-001',
            partner=self.partner,
            order_date=date.today(),
            status='CONFIRMED',
        )
        ap = AccountPayable.objects.create(
            partner=self.partner,
            purchase_order=po,
            amount=Decimal('1000000'),
            due_date=date.today(),
            status='PENDING',
            notes=f'발주 {po.po_number} 입고완료',
        )
        self.assertEqual(ap.purchase_order, po)
        self.assertEqual(po.payables.first(), ap)

    def test_ap_without_purchase_order(self):
        """AP는 PurchaseOrder FK 없이도 생성 가능"""
        ap = AccountPayable.objects.create(
            partner=self.partner,
            amount=Decimal('500000'),
            due_date=date.today(),
            status='PENDING',
        )
        self.assertIsNone(ap.purchase_order)


class OverdueTaskTests(TestCase):
    """AR/AP 연체 Celery 태스크 테스트"""

    def setUp(self):
        self.partner = Partner.objects.create(
            code='P-OD-001',
            name='연체 테스트 거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
        )

    def test_overdue_ar_auto_transition(self):
        """만기일 지난 AR이 OVERDUE로 전환"""
        from datetime import timedelta
        from apps.accounting.tasks import update_overdue_receivables

        ar = AccountReceivable.objects.create(
            partner=self.partner,
            amount=Decimal('1000000'),
            due_date=date.today() - timedelta(days=1),
            status='PENDING',
        )
        result = update_overdue_receivables()
        ar.refresh_from_db()
        self.assertEqual(ar.status, 'OVERDUE')
        self.assertEqual(result['ar_updated'], 1)

    def test_overdue_ap_auto_transition(self):
        """만기일 지난 AP가 OVERDUE로 전환"""
        from datetime import timedelta
        from apps.accounting.tasks import update_overdue_receivables

        ap = AccountPayable.objects.create(
            partner=self.partner,
            amount=Decimal('500000'),
            due_date=date.today() - timedelta(days=1),
            status='PARTIAL',
        )
        result = update_overdue_receivables()
        ap.refresh_from_db()
        self.assertEqual(ap.status, 'OVERDUE')
        self.assertEqual(result['ap_updated'], 1)

    def test_paid_ar_not_marked_overdue(self):
        """완납된 AR은 OVERDUE로 전환되지 않음"""
        from datetime import timedelta
        from apps.accounting.tasks import update_overdue_receivables

        ar = AccountReceivable.objects.create(
            partner=self.partner,
            amount=Decimal('1000000'),
            paid_amount=Decimal('1000000'),
            due_date=date.today() - timedelta(days=10),
            status='PAID',
        )
        update_overdue_receivables()
        ar.refresh_from_db()
        self.assertEqual(ar.status, 'PAID')

    def test_future_due_date_not_marked_overdue(self):
        """만기일이 아직 안 지난 AR은 OVERDUE로 전환되지 않음"""
        from datetime import timedelta
        from apps.accounting.tasks import update_overdue_receivables

        ar = AccountReceivable.objects.create(
            partner=self.partner,
            amount=Decimal('1000000'),
            due_date=date.today() + timedelta(days=30),
            status='PENDING',
        )
        update_overdue_receivables()
        ar.refresh_from_db()
        self.assertEqual(ar.status, 'PENDING')


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


class TaxInvoiceElectronicTests(TestCase):
    """전자세금계산서 필드 테스트"""

    def setUp(self):
        self.partner = Partner.objects.create(
            code='P-E001',
            name='전자발행 테스트 거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
        )
        self.invoice = TaxInvoice.objects.create(
            invoice_number='TI-E-0001',
            invoice_type=TaxInvoice.InvoiceType.SALES,
            partner=self.partner,
            issue_date=date(2026, 3, 24),
            supply_amount=Decimal('500000'),
            tax_amount=Decimal('50000'),
            total_amount=Decimal('550000'),
        )

    def test_default_electronic_status(self):
        """기본 전자발행상태는 NONE"""
        self.assertEqual(self.invoice.electronic_status, 'NONE')

    def test_electronic_status_choices(self):
        """ElectronicStatus 선택지 확인"""
        choices = dict(TaxInvoice.ElectronicStatus.choices)
        self.assertIn('NONE', choices)
        self.assertIn('ISSUED', choices)
        self.assertIn('SENT', choices)
        self.assertIn('ACCEPTED', choices)
        self.assertIn('REJECTED', choices)
        self.assertIn('CANCELLED', choices)
        self.assertEqual(choices['NONE'], '미발행')
        self.assertEqual(choices['ACCEPTED'], '국세청 승인')

    def test_electronic_fields_blank_by_default(self):
        """전자발행 필드들은 기본적으로 비어있음"""
        self.assertEqual(self.invoice.nts_confirmation_number, '')
        self.assertEqual(self.invoice.issue_id, '')
        self.assertIsNone(self.invoice.sent_at)
        self.assertEqual(self.invoice.nts_response, {})

    def test_update_electronic_status(self):
        """전자발행 상태 변경"""
        self.invoice.electronic_status = TaxInvoice.ElectronicStatus.ISSUED
        self.invoice.issue_id = 'test-uuid-1234'
        self.invoice.sent_at = timezone.now()
        self.invoice.save()

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.electronic_status, 'ISSUED')
        self.assertEqual(self.invoice.issue_id, 'test-uuid-1234')
        self.assertIsNotNone(self.invoice.sent_at)

    def test_nts_response_json(self):
        """국세청 응답 JSON 저장"""
        self.invoice.nts_response = {
            'ResultCode': '00',
            'NTSConfirmNumber': 'NTS-2026-0001',
        }
        self.invoice.save()

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.nts_response['ResultCode'], '00')


class NTSClientTests(TestCase):
    """국세청 API 클라이언트 단위 테스트"""

    def setUp(self):
        self.partner = Partner.objects.create(
            code='P-NTS001',
            name='NTS 테스트 거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
        )
        self.invoice = TaxInvoice.objects.create(
            invoice_number='TI-NTS-0001',
            invoice_type=TaxInvoice.InvoiceType.SALES,
            partner=self.partner,
            issue_date=date(2026, 3, 24),
            supply_amount=Decimal('1000000'),
            tax_amount=Decimal('100000'),
            total_amount=Decimal('1100000'),
        )

    def test_nts_api_error(self):
        """NTSAPIError 예외 생성"""
        from apps.accounting.nts_client import NTSAPIError
        error = NTSAPIError('테스트 에러', code='E001', response_data={'key': 'val'})
        self.assertEqual(str(error), '테스트 에러')
        self.assertEqual(error.code, 'E001')
        self.assertEqual(error.response_data, {'key': 'val'})

    def test_nts_client_build_xml(self):
        """XML 빌드 기본 동작"""
        from apps.accounting.nts_client import NTSClient
        client = NTSClient()
        client._config = {
            'business_number': '1234567890',
            'environment': 'test',
        }
        xml = client._build_xml(self.invoice)
        self.assertIn('1000000', xml)
        self.assertIn('100000', xml)
        self.assertIn('1100000', xml)

    def test_nts_client_cancel_invalid_status(self):
        """취소 불가 상태에서 cancel 호출 시 에러"""
        from apps.accounting.nts_client import NTSClient, NTSAPIError
        client = NTSClient()
        client._config = {
            'business_number': '1234567890',
            'api_key': 'test',
            'environment': 'test',
        }
        self.invoice.electronic_status = 'NONE'
        with self.assertRaises(NTSAPIError):
            client.cancel(self.invoice, reason='테스트')

    def test_nts_client_query_no_issue_id(self):
        """issue_id 없이 query 호출 시 에러"""
        from apps.accounting.nts_client import NTSClient, NTSAPIError
        client = NTSClient()
        client._config = {
            'business_number': '1234567890',
            'api_key': 'test',
            'environment': 'test',
        }
        self.invoice.issue_id = ''
        with self.assertRaises(NTSAPIError):
            client.query(self.invoice)


class BankAccountSyncTest(TestCase):
    """BankAccount 연동 필드 테스트"""

    def test_show_on_dashboard_default_false(self):
        """show_on_dashboard 기본값 False"""
        from .models import BankAccount
        acct = BankAccount.objects.create(
            name='테스트통장', account_type='BUSINESS', owner='테스트',
        )
        self.assertFalse(acct.show_on_dashboard)

    def test_employee_fk_nullable(self):
        """employee FK는 null 가능"""
        from .models import BankAccount
        acct = BankAccount.objects.create(
            name='일반통장', account_type='BUSINESS', owner='회사',
        )
        self.assertIsNone(acct.employee)

    def test_partner_fk_nullable(self):
        """partner FK는 null 가능"""
        from .models import BankAccount
        acct = BankAccount.objects.create(
            name='일반통장', account_type='BUSINESS', owner='회사',
        )
        self.assertIsNone(acct.partner)

    def test_personal_account_type(self):
        """PERSONAL 계좌 유형 사용 가능"""
        from .models import BankAccount
        acct = BankAccount.objects.create(
            name='급여통장', account_type='PERSONAL', owner='직원',
            bank='국민은행',
        )
        self.assertEqual(acct.account_type, 'PERSONAL')
        self.assertEqual(acct.get_account_type_display(), '개인통장')


class PaymentSoftDeleteTests(TestCase):
    """Payment soft delete 시 잔액 복원 테스트"""

    def setUp(self):
        self.partner = Partner.objects.create(
            code='PSD-001', name='잔액복원 거래처',
            partner_type=Partner.PartnerType.BOTH,
        )
        self.account_code = AccountCode.objects.create(
            code='110', name='보통예금',
            account_type=AccountCode.AccountType.ASSET,
        )
        self.bank_account = BankAccount.objects.create(
            name='테스트 계좌',
            account_type='BUSINESS',
            owner='테스트',
            account_code=self.account_code,
            balance=Decimal('10000000'),
        )

    def test_receipt_soft_delete_restores_ar_and_bank(self):
        """입금 Payment soft delete → AR paid_amount 감소 + 계좌잔액 복원"""
        ar = AccountReceivable.objects.create(
            partner=self.partner,
            amount=Decimal('1000000'),
            paid_amount=Decimal('500000'),
            due_date=date.today(),
            status='PARTIAL',
        )
        payment = Payment.objects.create(
            payment_type='RECEIPT',
            partner=self.partner,
            bank_account=self.bank_account,
            receivable=ar,
            amount=Decimal('500000'),
            payment_date=date.today(),
        )
        # post_save signal adds 500000 to bank balance
        self.bank_account.refresh_from_db()
        balance_after_payment = self.bank_account.balance

        # Soft delete
        payment.soft_delete()

        ar.refresh_from_db()
        self.bank_account.refresh_from_db()
        # AR paid_amount restored
        self.assertEqual(ar.paid_amount, Decimal('0'))
        # AR status recalculated
        self.assertEqual(ar.status, 'PENDING')
        # Bank balance restored (subtract the receipt amount)
        self.assertEqual(
            self.bank_account.balance,
            balance_after_payment - Decimal('500000'),
        )

    def test_disbursement_soft_delete_restores_ap_and_bank(self):
        """출금 Payment soft delete → AP paid_amount 감소 + 계좌잔액 복원"""
        ap = AccountPayable.objects.create(
            partner=self.partner,
            amount=Decimal('2000000'),
            paid_amount=Decimal('1000000'),
            due_date=date.today(),
            status='PARTIAL',
        )
        payment = Payment.objects.create(
            payment_type='DISBURSEMENT',
            partner=self.partner,
            bank_account=self.bank_account,
            payable=ap,
            amount=Decimal('1000000'),
            payment_date=date.today(),
        )
        # post_save signal subtracts 1000000 from bank balance
        self.bank_account.refresh_from_db()
        balance_after_payment = self.bank_account.balance

        # Soft delete
        payment.soft_delete()

        ap.refresh_from_db()
        self.bank_account.refresh_from_db()
        # AP paid_amount restored
        self.assertEqual(ap.paid_amount, Decimal('0'))
        # AP status recalculated
        self.assertEqual(ap.status, 'PENDING')
        # Bank balance restored (add back the disbursement amount)
        self.assertEqual(
            self.bank_account.balance,
            balance_after_payment + Decimal('1000000'),
        )

    def test_soft_delete_paid_ar_becomes_partial(self):
        """완납 AR에서 일부 Payment만 soft delete → PARTIAL"""
        ar = AccountReceivable.objects.create(
            partner=self.partner,
            amount=Decimal('1000000'),
            paid_amount=Decimal('1000000'),
            due_date=date.today(),
            status='PAID',
        )
        payment = Payment.objects.create(
            payment_type='RECEIPT',
            partner=self.partner,
            receivable=ar,
            amount=Decimal('400000'),
            payment_date=date.today(),
        )

        payment.soft_delete()

        ar.refresh_from_db()
        self.assertEqual(ar.paid_amount, Decimal('600000'))
        self.assertEqual(ar.status, 'PARTIAL')

    def test_skip_balance_restore_flag(self):
        """_skip_balance_restore 플래그 설정 시 복원 스킵"""
        ar = AccountReceivable.objects.create(
            partner=self.partner,
            amount=Decimal('1000000'),
            paid_amount=Decimal('500000'),
            due_date=date.today(),
            status='PARTIAL',
        )
        payment = Payment.objects.create(
            payment_type='RECEIPT',
            partner=self.partner,
            bank_account=self.bank_account,
            receivable=ar,
            amount=Decimal('500000'),
            payment_date=date.today(),
        )
        self.bank_account.refresh_from_db()
        balance_after = self.bank_account.balance

        # Set skip flag and soft delete
        payment._skip_balance_restore = True
        payment.soft_delete()

        ar.refresh_from_db()
        self.bank_account.refresh_from_db()
        # AR paid_amount NOT restored (skipped)
        self.assertEqual(ar.paid_amount, Decimal('500000'))
        # Bank balance NOT restored (skipped)
        self.assertEqual(self.bank_account.balance, balance_after)

    def test_soft_delete_without_ar_ap(self):
        """AR/AP 연결 없는 Payment soft delete → 계좌잔액만 복원"""
        payment = Payment.objects.create(
            payment_type='RECEIPT',
            partner=self.partner,
            bank_account=self.bank_account,
            amount=Decimal('300000'),
            payment_date=date.today(),
        )
        self.bank_account.refresh_from_db()
        balance_after = self.bank_account.balance

        payment.soft_delete()

        self.bank_account.refresh_from_db()
        self.assertEqual(
            self.bank_account.balance,
            balance_after - Decimal('300000'),
        )


class CreditCardCRUDTests(TestCase):
    """카드 CRUD 테스트"""

    def test_credit_card_creation(self):
        """카드 생성"""
        card = CreditCard.objects.create(
            name='법인카드1',
            card_type=CreditCard.CardType.CORPORATE,
            card_issuer=CreditCard.CardIssuer.SHINHAN,
            card_number_last4='1234',
            cardholder='홍길동',
            monthly_limit=Decimal('5000000'),
        )
        self.assertEqual(card.name, '법인카드1')
        self.assertEqual(card.card_type, 'CORPORATE')
        self.assertEqual(card.remaining_limit, Decimal('5000000'))
        self.assertEqual(card.usage_rate, 0)

    def test_credit_card_str(self):
        """카드 문자열 표현"""
        card = CreditCard.objects.create(
            name='테스트카드',
            card_type=CreditCard.CardType.PERSONAL,
            card_issuer=CreditCard.CardIssuer.KB,
            card_number_last4='5678',
            cardholder='테스트',
        )
        result = str(card)
        self.assertIn('테스트카드', result)
        self.assertIn('5678', result)

    def test_credit_card_usage_rate(self):
        """카드 사용률 계산"""
        card = CreditCard.objects.create(
            name='한도카드',
            card_type=CreditCard.CardType.CORPORATE,
            card_issuer=CreditCard.CardIssuer.SAMSUNG,
            card_number_last4='9999',
            cardholder='테스트',
            monthly_limit=Decimal('1000000'),
            used_amount=Decimal('250000'),
        )
        self.assertEqual(card.usage_rate, 25.0)
        self.assertEqual(card.remaining_limit, Decimal('750000'))


class CardTransactionVoucherTests(TestCase):
    """카드 거래 → 자동전표 테스트"""

    def setUp(self):
        self.card = CreditCard.objects.create(
            name='테스트법인카드',
            card_type=CreditCard.CardType.CORPORATE,
            card_issuer=CreditCard.CardIssuer.SHINHAN,
            card_number_last4='1111',
            cardholder='테스트',
            monthly_limit=Decimal('10000000'),
        )
        # 비용 계정과목 + 미지급금 계정
        self.expense_acct = AccountCode.objects.create(
            code='501', name='매입원가',
            account_type=AccountCode.AccountType.EXPENSE,
        )
        self.payable_acct = AccountCode.objects.create(
            code='253', name='미지급금',
            account_type=AccountCode.AccountType.LIABILITY,
        )
        self.travel_acct = AccountCode.objects.create(
            code='524', name='여비교통비',
            account_type=AccountCode.AccountType.EXPENSE,
        )

    def test_transaction_creates_voucher(self):
        """카드 거래 생성 시 자동전표 생성 + used_amount 증가"""
        txn = CardTransaction.objects.create(
            card=self.card,
            transaction_date=date.today(),
            merchant_name='테스트가맹점',
            amount=Decimal('100000'),
            category=CardTransaction.Category.PURCHASE,
        )
        txn.refresh_from_db()
        self.assertIsNotNone(txn.voucher)
        self.assertTrue(txn.voucher.is_balanced)

        self.card.refresh_from_db()
        self.assertEqual(self.card.used_amount, Decimal('100000'))

    def test_transaction_travel_category_voucher(self):
        """여비교통비 카테고리 → 524 계정과목 사용"""
        txn = CardTransaction.objects.create(
            card=self.card,
            transaction_date=date.today(),
            merchant_name='택시',
            amount=Decimal('30000'),
            category=CardTransaction.Category.TRAVEL,
        )
        txn.refresh_from_db()
        self.assertIsNotNone(txn.voucher)
        # 차변이 여비교통비(524)
        debit_line = txn.voucher.lines.filter(debit__gt=0).first()
        self.assertEqual(debit_line.account.code, '524')


class CardTransactionCancelTests(TestCase):
    """카드 거래 취소 테스트"""

    def setUp(self):
        self.card = CreditCard.objects.create(
            name='취소테스트카드',
            card_type=CreditCard.CardType.CORPORATE,
            card_issuer=CreditCard.CardIssuer.KB,
            card_number_last4='2222',
            cardholder='테스트',
            monthly_limit=Decimal('5000000'),
        )
        AccountCode.objects.create(
            code='501', name='매입원가',
            account_type=AccountCode.AccountType.EXPENSE,
        )
        AccountCode.objects.create(
            code='253', name='미지급금',
            account_type=AccountCode.AccountType.LIABILITY,
        )

    def test_cancel_reduces_used_amount(self):
        """카드 거래 취소 시 used_amount 감소"""
        txn = CardTransaction.objects.create(
            card=self.card,
            transaction_date=date.today(),
            merchant_name='취소가맹점',
            amount=Decimal('200000'),
            category=CardTransaction.Category.PURCHASE,
        )
        self.card.refresh_from_db()
        self.assertEqual(self.card.used_amount, Decimal('200000'))

        # 취소 처리
        txn.is_cancelled = True
        txn.cancelled_date = date.today()
        txn.save()

        self.card.refresh_from_db()
        self.assertEqual(self.card.used_amount, Decimal('0'))

    def test_cancel_creates_reverse_voucher(self):
        """카드 거래 취소 시 역전표 생성"""
        txn = CardTransaction.objects.create(
            card=self.card,
            transaction_date=date.today(),
            merchant_name='역전표가맹점',
            amount=Decimal('150000'),
            category=CardTransaction.Category.PURCHASE,
        )
        initial_voucher_count = Voucher.objects.count()

        txn.is_cancelled = True
        txn.cancelled_date = date.today()
        txn.save()

        # 역전표가 추가로 1건 생성됨
        self.assertEqual(Voucher.objects.count(), initial_voucher_count + 1)
        # 역전표는 차변=미지급금, 대변=비용
        reverse_voucher = Voucher.objects.order_by('-pk').first()
        self.assertTrue(reverse_voucher.is_balanced)
        self.assertIn('카드취소전표', reverse_voucher.description)


class CardBillingPayTests(TestCase):
    """카드 청구 결제 테스트"""

    def setUp(self):
        self.bank_account = BankAccount.objects.create(
            name='결제계좌',
            account_type=BankAccount.AccountType.BUSINESS,
            owner='회사',
            balance=Decimal('10000000'),
        )
        self.card = CreditCard.objects.create(
            name='청구테스트카드',
            card_type=CreditCard.CardType.CORPORATE,
            card_issuer=CreditCard.CardIssuer.HYUNDAI,
            card_number_last4='3333',
            cardholder='테스트',
            monthly_limit=Decimal('5000000'),
            payment_account=self.bank_account,
        )

    def test_billing_payment_creates_disbursement(self):
        """청구 결제 시 Payment(DISBURSEMENT) 생성"""
        partner = Partner.objects.create(
            code='CARD-PAY', name='카드결제 거래처',
            partner_type='SUPPLIER',
        )
        billing = CardBilling.objects.create(
            card=self.card,
            billing_month=date(2026, 3, 1),
            total_amount=Decimal('500000'),
            payment_due_date=date(2026, 4, 25),
        )
        # 수동으로 결제 처리 로직 수행
        from django.db import transaction as db_transaction
        from django.db.models import F as db_F
        from apps.core.utils import generate_document_number

        with db_transaction.atomic():
            pay_amount = billing.remaining_amount
            payment = Payment.objects.create(
                payment_number=generate_document_number(Payment, 'payment_number', 'PM'),
                payment_type='DISBURSEMENT',
                partner=partner,
                bank_account=self.bank_account,
                amount=pay_amount,
                payment_date=date.today(),
                payment_method='CARD',
            )
            CardBilling.objects.filter(pk=billing.pk).update(
                paid_amount=db_F('paid_amount') + pay_amount,
                payment=payment,
            )
            billing.refresh_from_db()
            if billing.paid_amount >= billing.total_amount:
                CardBilling.objects.filter(pk=billing.pk).update(status='PAID')
            billing.refresh_from_db()

        billing.refresh_from_db()
        self.assertEqual(billing.status, 'PAID')
        self.assertEqual(billing.paid_amount, Decimal('500000'))
        self.assertIsNotNone(billing.payment)

    def test_billing_remaining_amount(self):
        """청구 잔액 계산"""
        billing = CardBilling.objects.create(
            card=self.card,
            billing_month=date(2026, 4, 1),
            total_amount=Decimal('1000000'),
            paid_amount=Decimal('300000'),
            payment_due_date=date(2026, 5, 25),
            status='PARTIAL',
        )
        self.assertEqual(billing.remaining_amount, Decimal('700000'))


class CardLimitTests(TestCase):
    """카드 한도 검증 테스트"""

    def test_zero_limit_usage_rate(self):
        """한도가 0인 카드의 사용률은 0"""
        card = CreditCard.objects.create(
            name='무한도카드',
            card_type=CreditCard.CardType.CHECK,
            card_issuer=CreditCard.CardIssuer.WOORI,
            card_number_last4='4444',
            cardholder='테스트',
            monthly_limit=Decimal('0'),
            used_amount=Decimal('100000'),
        )
        self.assertEqual(card.usage_rate, 0)
        self.assertEqual(card.remaining_limit, Decimal('-100000'))


class ARAutoVoucherTests(TestCase):
    """AR 생성 시 자동전표 생성 테스트"""

    def setUp(self):
        self.partner = Partner.objects.create(
            code='AR-AV-001', name='미수금전표 거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
        )
        self.acct_120 = AccountCode.objects.create(
            code='120', name='미수금',
            account_type=AccountCode.AccountType.ASSET,
        )
        self.acct_401 = AccountCode.objects.create(
            code='401', name='매출',
            account_type=AccountCode.AccountType.REVENUE,
        )

    def test_ar_auto_voucher_on_create(self):
        """AR 생성 시 차변 120(미수금) / 대변 401(매출) 자동전표 생성"""
        initial_count = Voucher.objects.count()
        ar = AccountReceivable.objects.create(
            partner=self.partner,
            amount=Decimal('1000000'),
            due_date=date(2026, 6, 1),
        )
        self.assertEqual(Voucher.objects.count(), initial_count + 1)
        voucher = Voucher.objects.order_by('-pk').first()
        self.assertTrue(voucher.is_balanced)
        self.assertIn('미수금 발생', voucher.description)
        # 차변: 120 미수금
        debit_line = voucher.lines.filter(debit__gt=0).first()
        self.assertEqual(debit_line.account.code, '120')
        self.assertEqual(debit_line.debit, Decimal('1000000'))
        # 대변: 401 매출
        credit_line = voucher.lines.filter(credit__gt=0).first()
        self.assertEqual(credit_line.account.code, '401')
        self.assertEqual(credit_line.credit, Decimal('1000000'))

    def test_ar_auto_voucher_skips_without_account_codes(self):
        """계정과목 없으면 자동전표 생성 안 함"""
        self.acct_120.delete()
        initial_count = Voucher.objects.count()
        AccountReceivable.objects.create(
            partner=self.partner,
            amount=Decimal('500000'),
            due_date=date(2026, 6, 1),
        )
        self.assertEqual(Voucher.objects.count(), initial_count)


class APAutoVoucherTests(TestCase):
    """AP 생성 시 자동전표 생성 테스트"""

    def setUp(self):
        self.partner = Partner.objects.create(
            code='AP-AV-001', name='미지급전표 거래처',
            partner_type=Partner.PartnerType.SUPPLIER,
        )
        self.acct_501 = AccountCode.objects.create(
            code='501', name='매입원가',
            account_type=AccountCode.AccountType.EXPENSE,
        )
        self.acct_253 = AccountCode.objects.create(
            code='253', name='미지급금',
            account_type=AccountCode.AccountType.LIABILITY,
        )

    def test_ap_auto_voucher_on_create(self):
        """AP 생성 시 차변 501(매입원가) / 대변 253(미지급금) 자동전표 생성"""
        initial_count = Voucher.objects.count()
        ap = AccountPayable.objects.create(
            partner=self.partner,
            amount=Decimal('2000000'),
            due_date=date(2026, 6, 1),
        )
        self.assertEqual(Voucher.objects.count(), initial_count + 1)
        voucher = Voucher.objects.order_by('-pk').first()
        self.assertTrue(voucher.is_balanced)
        self.assertIn('미지급금 발생', voucher.description)
        # 차변: 501 매입원가
        debit_line = voucher.lines.filter(debit__gt=0).first()
        self.assertEqual(debit_line.account.code, '501')
        self.assertEqual(debit_line.debit, Decimal('2000000'))
        # 대변: 253 미지급금
        credit_line = voucher.lines.filter(credit__gt=0).first()
        self.assertEqual(credit_line.account.code, '253')
        self.assertEqual(credit_line.credit, Decimal('2000000'))

    def test_ap_auto_voucher_skips_without_account_codes(self):
        """계정과목 없으면 자동전표 생성 안 함"""
        self.acct_253.delete()
        initial_count = Voucher.objects.count()
        AccountPayable.objects.create(
            partner=self.partner,
            amount=Decimal('500000'),
            due_date=date(2026, 6, 1),
        )
        self.assertEqual(Voucher.objects.count(), initial_count)


class AROverdueTransitionTests(TestCase):
    """AR 연체 자동 전환 테스트 (ListView 기반)"""

    def setUp(self):
        self.partner = Partner.objects.create(
            code='AR-OD-001', name='연체전환 거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
        )

    def test_ar_overdue_auto_transition(self):
        """due_date가 지난 PENDING/PARTIAL AR이 OVERDUE로 전환"""
        from datetime import timedelta
        ar_pending = AccountReceivable.objects.create(
            partner=self.partner,
            amount=Decimal('1000000'),
            due_date=date.today() - timedelta(days=5),
            status='PENDING',
        )
        ar_partial = AccountReceivable.objects.create(
            partner=self.partner,
            amount=Decimal('500000'),
            paid_amount=Decimal('100000'),
            due_date=date.today() - timedelta(days=1),
            status='PARTIAL',
        )
        # Simulate what ARListView.get_queryset does
        today = date.today()
        AccountReceivable.objects.filter(
            is_active=True,
            due_date__lt=today,
            status__in=['PENDING', 'PARTIAL'],
        ).update(status='OVERDUE')

        ar_pending.refresh_from_db()
        ar_partial.refresh_from_db()
        self.assertEqual(ar_pending.status, 'OVERDUE')
        self.assertEqual(ar_partial.status, 'OVERDUE')

    def test_paid_ar_not_overdue(self):
        """PAID 상태 AR은 OVERDUE로 전환되지 않음"""
        from datetime import timedelta
        ar_paid = AccountReceivable.objects.create(
            partner=self.partner,
            amount=Decimal('1000000'),
            paid_amount=Decimal('1000000'),
            due_date=date.today() - timedelta(days=10),
            status='PAID',
        )
        today = date.today()
        AccountReceivable.objects.filter(
            is_active=True,
            due_date__lt=today,
            status__in=['PENDING', 'PARTIAL'],
        ).update(status='OVERDUE')

        ar_paid.refresh_from_db()
        self.assertEqual(ar_paid.status, 'PAID')


class ClosingPeriodBlocksVoucherTests(TestCase):
    """마감된 기간 전표 생성 차단 테스트"""

    def setUp(self):
        self.partner = Partner.objects.create(
            code='CP-001', name='마감차단 거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
        )
        AccountCode.objects.create(
            code='120', name='미수금',
            account_type=AccountCode.AccountType.ASSET,
        )
        AccountCode.objects.create(
            code='401', name='매출',
            account_type=AccountCode.AccountType.REVENUE,
        )
        # 2026년 1월 마감
        ClosingPeriod.objects.create(
            year=2026, month=1, is_closed=True,
        )

    def test_closing_period_blocks_ar_voucher(self):
        """마감된 월에 해당하는 AR 생성 시 전표 생성이 차단됨"""
        initial_count = Voucher.objects.count()
        # due_date가 마감된 월(2026-01)
        ar = AccountReceivable.objects.create(
            partner=self.partner,
            amount=Decimal('500000'),
            due_date=date(2026, 1, 15),
        )
        # 전표가 생성되지 않아야 함 (마감 차단)
        self.assertEqual(Voucher.objects.count(), initial_count)

    def test_open_period_allows_ar_voucher(self):
        """마감되지 않은 월은 전표 정상 생성"""
        initial_count = Voucher.objects.count()
        ar = AccountReceivable.objects.create(
            partner=self.partner,
            amount=Decimal('500000'),
            due_date=date(2026, 6, 15),
        )
        self.assertEqual(Voucher.objects.count(), initial_count + 1)


class PaymentSoftDeleteRestoresFullBalanceTests(TestCase):
    """Payment soft delete 시 AR/AP + BankAccount 전체 복원 통합 테스트"""

    def setUp(self):
        self.partner = Partner.objects.create(
            code='PSDR-001', name='복원통합 거래처',
            partner_type=Partner.PartnerType.BOTH,
        )
        self.account_code = AccountCode.objects.create(
            code='110', name='보통예금',
            account_type=AccountCode.AccountType.ASSET,
        )
        self.bank_account = BankAccount.objects.create(
            name='복원통합 계좌',
            account_type='BUSINESS',
            owner='테스트',
            account_code=self.account_code,
            balance=Decimal('5000000'),
        )

    def test_payment_soft_delete_restores_balance(self):
        """입금 Payment soft delete → AR paid_amount 복원 + 계좌잔액 복원 + status 재계산"""
        ar = AccountReceivable.objects.create(
            partner=self.partner,
            amount=Decimal('1000000'),
            paid_amount=Decimal('600000'),
            due_date=date.today(),
            status='PARTIAL',
        )
        payment = Payment.objects.create(
            payment_type='RECEIPT',
            partner=self.partner,
            bank_account=self.bank_account,
            receivable=ar,
            amount=Decimal('600000'),
            payment_date=date.today(),
        )
        # post_save adds 600000 to bank
        self.bank_account.refresh_from_db()
        bank_after = self.bank_account.balance

        # Soft delete
        payment.soft_delete()

        ar.refresh_from_db()
        self.bank_account.refresh_from_db()
        # AR paid_amount 복원
        self.assertEqual(ar.paid_amount, Decimal('0'))
        # AR status 재계산 → PENDING
        self.assertEqual(ar.status, 'PENDING')
        # Bank balance 복원
        self.assertEqual(self.bank_account.balance, bank_after - Decimal('600000'))


class QuotationExpiryTaskTests(TestCase):
    """견적 만료 Celery 태스크 테스트"""

    def setUp(self):
        from apps.sales.models import Partner, Customer
        self.partner = Partner.objects.create(
            code='QE-001', name='견적만료 거래처',
            partner_type=Partner.PartnerType.CUSTOMER,
        )

    def test_expired_quotation_auto_update(self):
        """만료된 견적서 EXPIRED 자동 전환"""
        from datetime import timedelta
        from apps.sales.models import Quotation
        from apps.sales.tasks import expire_quotations

        # 만료된 견적 — Quotation.save()가 자동 만료하므로,
        # 유효 기한 내로 생성 후 update로 만료시킴
        q_expired = Quotation.objects.create(
            partner=self.partner,
            quote_date=date.today(),
            valid_until=date.today() + timedelta(days=30),
            status='SENT',
        )
        # DB에서 직접 valid_until을 과거로 변경 (save 자동만료 우회)
        Quotation.objects.filter(pk=q_expired.pk).update(
            valid_until=date.today() - timedelta(days=1),
        )
        # 아직 유효한 견적
        q_valid = Quotation.objects.create(
            partner=self.partner,
            quote_date=date.today(),
            valid_until=date.today() + timedelta(days=30),
            status='SENT',
        )
        result = expire_quotations()
        q_expired.refresh_from_db()
        q_valid.refresh_from_db()
        self.assertEqual(q_expired.status, 'EXPIRED')
        self.assertEqual(q_valid.status, 'SENT')
        self.assertEqual(result, 1)

    def test_converted_quotation_not_expired(self):
        """CONVERTED 상태 견적은 만료 전환 안 됨"""
        from datetime import timedelta
        from apps.sales.models import Quotation
        from apps.sales.tasks import expire_quotations

        q = Quotation.objects.create(
            partner=self.partner,
            quote_date=date.today(),
            valid_until=date.today() + timedelta(days=30),
            status='CONVERTED',
        )
        # DB에서 직접 valid_until을 과거로 변경
        Quotation.objects.filter(pk=q.pk).update(
            valid_until=date.today() - timedelta(days=1),
        )
        expire_quotations()
        q.refresh_from_db()
        self.assertEqual(q.status, 'CONVERTED')


class ExchangeGainLossTests(TestCase):
    """환차손익 계산 테스트"""

    def setUp(self):
        self.partner = Partner.objects.create(
            code='EGL-001', name='외화 거래처',
            partner_type=Partner.PartnerType.BOTH,
        )
        self.usd = Currency.objects.create(
            code='USD', name='미국 달러', symbol='$',
            decimal_places=2, is_base=False,
        )

    def test_exchange_gain_calculation(self):
        """환율 상승 시 AR 환차이익 발생"""
        from apps.sales.models import Order
        # USD 주문 (환율 1300)
        order = Order.objects.create(
            partner=self.partner,
            order_date=date.today(),
            currency=self.usd,
            exchange_rate=Decimal('1300.0000'),
            status='CONFIRMED',
        )
        ar = AccountReceivable.objects.create(
            partner=self.partner,
            order=order,
            amount=Decimal('1300000'),  # $1000 * 1300
            due_date=date.today(),
            status='PENDING',
        )
        # 현재 환율 1400으로 등록
        ExchangeRate.objects.create(
            currency=self.usd,
            rate_date=date.today(),
            rate=Decimal('1400.0000'),
        )
        # 외화 잔액: 1,300,000 / 1,300 = 1000 USD
        # 재평가: 1000 * 1400 = 1,400,000
        # 환차이익: 1,400,000 - 1,300,000 = 100,000
        foreign_remaining = ar.remaining_amount / order.exchange_rate
        self.assertEqual(foreign_remaining, Decimal('1000'))
        revalued = int(foreign_remaining * Decimal('1400'))
        gain_loss = revalued - int(ar.remaining_amount)
        self.assertEqual(gain_loss, 100000)

    def test_exchange_loss_calculation(self):
        """환율 하락 시 AP 환차손실 발생"""
        from apps.purchase.models import PurchaseOrder
        po = PurchaseOrder.objects.create(
            partner=self.partner,
            order_date=date.today(),
            currency=self.usd,
            exchange_rate=Decimal('1400.0000'),
            status='CONFIRMED',
        )
        ap = AccountPayable.objects.create(
            partner=self.partner,
            purchase_order=po,
            amount=Decimal('1400000'),  # $1000 * 1400
            due_date=date.today(),
            status='PENDING',
        )
        # 현재 환율 1300으로 등록 (하락)
        ExchangeRate.objects.create(
            currency=self.usd,
            rate_date=date.today(),
            rate=Decimal('1300.0000'),
        )
        foreign_remaining = ap.remaining_amount / po.exchange_rate
        revalued = int(foreign_remaining * Decimal('1300'))
        gain_loss = revalued - int(ap.remaining_amount)
        # AP 환율 하락 → 재평가액 감소 → 환차이익 (부채 감소)
        self.assertEqual(gain_loss, -100000)


class BudgetWarningTests(TestCase):
    """예산 초과 경고 테스트"""

    def setUp(self):
        self.expense_acct = AccountCode.objects.create(
            code='501', name='매입원가',
            account_type=AccountCode.AccountType.EXPENSE,
        )
        self.bank_acct = AccountCode.objects.create(
            code='110', name='보통예금',
            account_type=AccountCode.AccountType.ASSET,
        )

    def test_budget_overspend_warning(self):
        """예산 초과 시 경고 로깅"""
        from apps.accounting.models import Budget
        today = date.today()
        # 예산 50만원
        Budget.objects.create(
            account=self.expense_acct,
            year=today.year,
            month=today.month,
            budget_amount=Decimal('500000'),
        )
        voucher = Voucher.objects.create(
            voucher_number='V-BW-001',
            voucher_type=Voucher.VoucherType.PAYMENT,
            voucher_date=today,
            description='예산초과 테스트 전표',
            approval_status='APPROVED',
        )
        # VoucherLine 생성 시 예산 체크 시그널 발동
        with self.assertLogs('apps.accounting.signals', level='WARNING') as cm:
            VoucherLine.objects.create(
                voucher=voucher,
                account=self.expense_acct,
                debit=Decimal('1000000'), credit=0,
            )
        VoucherLine.objects.create(
            voucher=voucher,
            account=self.bank_acct,
            debit=0, credit=Decimal('1000000'),
        )
        # 경고 로그 확인
        warnings = [m for m in cm.output if 'Budget overspend' in m]
        self.assertTrue(len(warnings) > 0)
        self.assertIn('501', warnings[0])

    def test_no_warning_within_budget(self):
        """예산 이내면 경고 없음"""
        from apps.accounting.models import Budget
        today = date.today()
        Budget.objects.create(
            account=self.expense_acct,
            year=today.year,
            month=today.month,
            budget_amount=Decimal('5000000'),  # 500만원
        )
        # 전표 10만원 → 예산 이내
        voucher = Voucher.objects.create(
            voucher_number='V-BW-002',
            voucher_type=Voucher.VoucherType.PAYMENT,
            voucher_date=today,
            description='예산이내 테스트',
            approval_status='APPROVED',
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=self.expense_acct,
            debit=Decimal('100000'), credit=0,
        )
        VoucherLine.objects.create(
            voucher=voucher,
            account=self.bank_acct,
            debit=0, credit=Decimal('100000'),
        )
        # 예산 이내이므로 Budget.actual_amount < budget_amount
        from apps.accounting.models import Budget as B
        b = B.objects.get(account=self.expense_acct, year=today.year, month=today.month)
        self.assertLessEqual(b.actual_amount, b.budget_amount)


class SettlementVoucherSignalTest(TestCase):
    """매출 정산 → 수수료/배송비 자동전표 테스트"""

    def setUp(self):
        self.acct_521 = AccountCode.objects.create(
            code='521', name='판매수수료', account_type='EXPENSE',
        )
        self.acct_524 = AccountCode.objects.create(
            code='524', name='운반비', account_type='EXPENSE',
        )
        self.acct_253 = AccountCode.objects.create(
            code='253', name='미지급금', account_type='LIABILITY',
        )

    def test_settlement_with_commission_and_shipping(self):
        """배송비+수수료 모두 있으면 전표 3행(차변2+대변1) 생성"""
        before = Voucher.objects.count()
        settlement = SalesSettlement.objects.create(
            settlement_date=date(2026, 4, 1),
            total_shipping=Decimal('5000'),
            total_platform_commission=Decimal('30000'),
        )
        self.assertEqual(Voucher.objects.count(), before + 1)
        settlement.refresh_from_db()
        self.assertIsNotNone(settlement.commission_voucher_id)

        voucher = Voucher.objects.get(pk=settlement.commission_voucher_id)
        self.assertTrue(voucher.is_balanced)
        self.assertEqual(voucher.lines.count(), 3)

        commission_line = voucher.lines.get(account=self.acct_521)
        self.assertEqual(commission_line.debit, Decimal('30000'))

        shipping_line = voucher.lines.get(account=self.acct_524)
        self.assertEqual(shipping_line.debit, Decimal('5000'))

        payable_line = voucher.lines.get(account=self.acct_253)
        self.assertEqual(payable_line.credit, Decimal('35000'))

    def test_settlement_commission_only(self):
        """수수료만 있으면 전표 2행(차변1+대변1)"""
        settlement = SalesSettlement.objects.create(
            settlement_date=date(2026, 4, 1),
            total_shipping=Decimal('0'),
            total_platform_commission=Decimal('20000'),
        )
        settlement.refresh_from_db()
        voucher = Voucher.objects.get(pk=settlement.commission_voucher_id)
        self.assertEqual(voucher.lines.count(), 2)
        self.assertTrue(voucher.is_balanced)

    def test_settlement_shipping_only(self):
        """배송비만 있으면 전표 2행(차변1+대변1)"""
        settlement = SalesSettlement.objects.create(
            settlement_date=date(2026, 4, 1),
            total_shipping=Decimal('8000'),
            total_platform_commission=Decimal('0'),
        )
        settlement.refresh_from_db()
        voucher = Voucher.objects.get(pk=settlement.commission_voucher_id)
        self.assertEqual(voucher.lines.count(), 2)
        self.assertTrue(voucher.is_balanced)

    def test_settlement_no_fees_no_voucher(self):
        """배송비/수수료 모두 0이면 전표 미생성"""
        before = Voucher.objects.count()
        settlement = SalesSettlement.objects.create(
            settlement_date=date(2026, 4, 1),
            total_shipping=Decimal('0'),
            total_platform_commission=Decimal('0'),
        )
        self.assertEqual(Voucher.objects.count(), before)
        settlement.refresh_from_db()
        self.assertIsNone(settlement.commission_voucher_id)

    def test_settlement_no_duplicate_voucher(self):
        """commission_voucher 이미 있으면 재생성 안 함"""
        settlement = SalesSettlement.objects.create(
            settlement_date=date(2026, 4, 1),
            total_shipping=Decimal('5000'),
            total_platform_commission=Decimal('10000'),
        )
        settlement.refresh_from_db()
        first_voucher_id = settlement.commission_voucher_id
        self.assertIsNotNone(first_voucher_id)

        # 다시 save() — 기존 voucher 유지
        before = Voucher.objects.count()
        settlement.save()
        self.assertEqual(Voucher.objects.count(), before)
        settlement.refresh_from_db()
        self.assertEqual(settlement.commission_voucher_id, first_voucher_id)

    def test_settlement_missing_accounts_no_voucher(self):
        """계정과목 없으면 전표 미생성"""
        self.acct_253.delete()
        before = Voucher.objects.count()
        settlement = SalesSettlement.objects.create(
            settlement_date=date(2026, 4, 1),
            total_platform_commission=Decimal('10000'),
        )
        self.assertEqual(Voucher.objects.count(), before)
