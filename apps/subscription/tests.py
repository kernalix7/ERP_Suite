from datetime import date
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import User
from apps.inventory.models import Product
from apps.sales.models import Partner

from .models import (
    BillingRecord,
    Subscription,
    SubscriptionItem,
    SubscriptionPlan,
    UsageRecord,
)


class SubscriptionPlanTests(TestCase):
    def test_create_plan(self):
        plan = SubscriptionPlan.objects.create(
            name='기본 플랜',
            code='BASIC',
            billing_cycle=SubscriptionPlan.BillingCycle.MONTHLY,
            price=100000,
            features=['기본 기능', '이메일 지원'],
        )
        self.assertIn('월간', str(plan))
        self.assertEqual(plan.price, 100000)

    def test_yearly_plan(self):
        plan = SubscriptionPlan.objects.create(
            name='연간 플랜',
            code='YEARLY',
            billing_cycle=SubscriptionPlan.BillingCycle.YEARLY,
            price=1000000,
        )
        self.assertEqual(plan.billing_cycle, 'YEARLY')


class SubscriptionTests(TestCase):
    def setUp(self):
        self.partner = Partner.objects.create(
            code='PTN-SUB01', name='구독 고객', partner_type='CUSTOMER',
        )
        self.plan = SubscriptionPlan.objects.create(
            name='스탠다드', code='STD',
            billing_cycle=SubscriptionPlan.BillingCycle.MONTHLY,
            price=200000,
        )

    def test_create_subscription_auto_number(self):
        sub = Subscription.objects.create(
            partner=self.partner,
            plan=self.plan,
            start_date=date(2026, 4, 1),
            next_billing_date=date(2026, 5, 1),
        )
        self.assertTrue(sub.subscription_number.startswith('SUB-'))
        self.assertEqual(sub.status, Subscription.Status.TRIAL)

    def test_status_flow(self):
        sub = Subscription.objects.create(
            partner=self.partner,
            plan=self.plan,
            start_date=date(2026, 4, 1),
        )
        sub.status = Subscription.Status.ACTIVE
        sub.save()
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)

        sub.status = Subscription.Status.PAUSED
        sub.save()
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.PAUSED)

        sub.status = Subscription.Status.CANCELLED
        sub.cancel_reason = '비용 절감'
        sub.save()
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.CANCELLED)

    def test_soft_delete(self):
        sub = Subscription.objects.create(
            partner=self.partner,
            plan=self.plan,
            start_date=date(2026, 4, 1),
        )
        sub.soft_delete()
        self.assertFalse(Subscription.objects.filter(pk=sub.pk).exists())
        self.assertTrue(Subscription.all_objects.filter(pk=sub.pk).exists())


class SubscriptionItemTests(TestCase):
    def setUp(self):
        self.partner = Partner.objects.create(
            code='PTN-SI01', name='항목 고객', partner_type='CUSTOMER',
        )
        self.plan = SubscriptionPlan.objects.create(
            name='프리미엄', code='PREM',
            billing_cycle=SubscriptionPlan.BillingCycle.MONTHLY,
            price=500000,
        )
        self.sub = Subscription.objects.create(
            partner=self.partner, plan=self.plan,
            start_date=date(2026, 4, 1),
        )
        self.product = Product.objects.create(
            code='PRD-SUB01', name='구독 제품',
            product_type=Product.ProductType.FINISHED,
        )

    def test_create_item(self):
        item = SubscriptionItem.objects.create(
            subscription=self.sub,
            product=self.product,
            quantity=5,
            unit_price=10000,
        )
        self.assertEqual(item.amount, 50000)


class BillingRecordTests(TestCase):
    def setUp(self):
        self.partner = Partner.objects.create(
            code='PTN-BR01', name='과금 고객', partner_type='CUSTOMER',
        )
        self.plan = SubscriptionPlan.objects.create(
            name='과금 플랜', code='BILL',
            billing_cycle=SubscriptionPlan.BillingCycle.MONTHLY,
            price=100000,
        )
        self.sub = Subscription.objects.create(
            partner=self.partner, plan=self.plan,
            start_date=date(2026, 4, 1),
        )

    def test_create_billing_auto_tax(self):
        record = BillingRecord.objects.create(
            subscription=self.sub,
            billing_date=date(2026, 5, 1),
            amount=100000,
        )
        self.assertEqual(record.tax_amount, 10000)
        self.assertEqual(record.total, 110000)
        self.assertEqual(record.status, BillingRecord.Status.PENDING)

    def test_billing_status_flow(self):
        record = BillingRecord.objects.create(
            subscription=self.sub,
            billing_date=date(2026, 5, 1),
            amount=200000,
        )
        record.status = BillingRecord.Status.INVOICED
        record.save()
        record.refresh_from_db()
        self.assertEqual(record.status, 'INVOICED')

        record.status = BillingRecord.Status.PAID
        record.save()
        record.refresh_from_db()
        self.assertEqual(record.status, 'PAID')


class UsageRecordTests(TestCase):
    def test_create_usage(self):
        partner = Partner.objects.create(
            code='PTN-UR01', name='사용량 고객', partner_type='CUSTOMER',
        )
        plan = SubscriptionPlan.objects.create(
            name='사용량 플랜', code='USAGE',
            billing_cycle=SubscriptionPlan.BillingCycle.MONTHLY,
            price=50000,
        )
        sub = Subscription.objects.create(
            partner=partner, plan=plan, start_date=date(2026, 4, 1),
        )
        usage = UsageRecord.objects.create(
            subscription=sub,
            metric_name='API 호출수',
            quantity=Decimal('1500.00'),
            recorded_date=date(2026, 4, 15),
        )
        self.assertFalse(usage.billed)
        self.assertIn('API 호출수', str(usage))


class SubscriptionViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='sub_staff', password='testpass123', role='staff',
        )
        self.manager = User.objects.create_user(
            username='sub_manager', password='testpass123', role='manager',
        )

    def test_dashboard_requires_login(self):
        resp = self.client.get(reverse('subscription:dashboard'))
        self.assertEqual(resp.status_code, 302)

    def test_dashboard_authenticated(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('subscription:dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_plan_list_requires_login(self):
        resp = self.client.get(reverse('subscription:plan_list'))
        self.assertEqual(resp.status_code, 302)

    def test_plan_list_authenticated(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('subscription:plan_list'))
        self.assertEqual(resp.status_code, 200)

    def test_subscription_list_requires_login(self):
        resp = self.client.get(reverse('subscription:subscription_list'))
        self.assertEqual(resp.status_code, 302)

    def test_subscription_list_authenticated(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('subscription:subscription_list'))
        self.assertEqual(resp.status_code, 200)
