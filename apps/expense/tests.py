from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.expense.models import (
    CardTransaction, CorporateCard, ExpenseCategory, ExpenseClaim,
    ExpenseItem, ExpensePolicy,
)

User = get_user_model()


class ExpensePolicyModelTest(TestCase):
    def test_create_policy(self):
        policy = ExpensePolicy.objects.create(
            name='일반 경비', max_amount=Decimal('500000'),
            daily_limit=Decimal('200000'), monthly_limit=Decimal('3000000'),
        )
        self.assertEqual(str(policy), '일반 경비')
        self.assertTrue(policy.requires_receipt)


class ExpenseCategoryModelTest(TestCase):
    def test_create_category(self):
        cat = ExpenseCategory.objects.create(name='교통비', code='TRANS')
        self.assertEqual(str(cat), '[TRANS] 교통비')

    def test_parent_category(self):
        parent = ExpenseCategory.objects.create(name='업무비', code='BIZ')
        child = ExpenseCategory.objects.create(name='출장비', code='BIZ-T', parent=parent)
        self.assertEqual(child.parent, parent)


class ExpenseClaimModelTest(TestCase):
    def test_auto_number(self):
        claim = ExpenseClaim.objects.create(title='3월 경비')
        self.assertTrue(claim.claim_number.startswith('EXP-'))

    def test_default_status(self):
        claim = ExpenseClaim.objects.create(title='신규 경비')
        self.assertEqual(claim.status, ExpenseClaim.Status.DRAFT)

    def test_recalculate_total(self):
        cat = ExpenseCategory.objects.create(name='식비', code='MEAL')
        claim = ExpenseClaim.objects.create(title='식대 청구')
        ExpenseItem.objects.create(
            claim=claim, category=cat, date=date.today(),
            description='점심', amount=Decimal('12000'),
        )
        ExpenseItem.objects.create(
            claim=claim, category=cat, date=date.today(),
            description='저녁', amount=Decimal('18000'),
        )
        claim.recalculate_total()
        self.assertEqual(claim.total_amount, Decimal('30000'))


class ExpenseItemModelTest(TestCase):
    def test_create_item(self):
        cat = ExpenseCategory.objects.create(name='교통비', code='TR')
        claim = ExpenseClaim.objects.create(title='이동경비')
        item = ExpenseItem.objects.create(
            claim=claim, category=cat, date=date.today(),
            description='택시', amount=Decimal('25000'),
        )
        self.assertIn('택시', str(item))


class CorporateCardModelTest(TestCase):
    def test_create_card(self):
        card = CorporateCard.objects.create(
            card_number_last4='1234', card_type='법인',
            monthly_limit=Decimal('5000000'),
        )
        self.assertIn('1234', str(card))


class CardTransactionModelTest(TestCase):
    def test_create_transaction(self):
        card = CorporateCard.objects.create(
            card_number_last4='5678', card_type='법인',
        )
        txn = CardTransaction.objects.create(
            card=card, transaction_date=date.today(),
            merchant='스타벅스', amount=Decimal('5500'),
        )
        self.assertIn('스타벅스', str(txn))
        self.assertFalse(txn.is_personal)


class ExpenseViewAccessTest(TestCase):
    """경비 뷰 접근 권한 테스트 (비인증/비권한 거부 확인)"""

    def setUp(self):
        self.manager = User.objects.create_user(
            username='mgr_expense', password='testpass123', role='manager',
        )
        self.staff = User.objects.create_user(
            username='staff_expense', password='testpass123', role='staff',
        )

    def test_claim_list_requires_login(self):
        resp = self.client.get('/expense/claims/')
        self.assertEqual(resp.status_code, 302)

    def test_policy_list_requires_manager(self):
        self.client.force_login(self.staff)
        resp = self.client.get('/expense/policies/')
        self.assertIn(resp.status_code, [302, 403])

    def test_dashboard_requires_login(self):
        resp = self.client.get('/expense/')
        self.assertEqual(resp.status_code, 302)
