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
    ApprovalRequest,
    FixedCost,
    TaxInvoice,
    TaxRate,
    Voucher,
    VoucherLine,
    WithholdingTax,
)


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
