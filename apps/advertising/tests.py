from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import User
from .models import (
    AdPlatform, AdCampaign, AdCreative,
    AdPerformance, AdBudget,
)


class AdPlatformModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='adtest', password='test1234',
            role='manager', name='Ad Tester',
        )

    def test_create_platform(self):
        platform = AdPlatform.objects.create(
            name='Google Ads',
            platform_type='SEARCH',
            created_by=self.user,
        )
        self.assertEqual(str(platform), 'Google Ads')
        self.assertFalse(platform.is_connected)

    def test_platform_types(self):
        for ptype, _ in AdPlatform.PLATFORM_TYPE_CHOICES:
            p = AdPlatform.objects.create(
                name=f'Platform {ptype}',
                platform_type=ptype,
                created_by=self.user,
            )
            self.assertEqual(p.platform_type, ptype)


class AdCampaignModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='camptest', password='test1234',
            role='manager', name='Campaign Tester',
        )
        self.platform = AdPlatform.objects.create(
            name='Naver Ads',
            platform_type='SEARCH',
            created_by=self.user,
        )

    def test_create_campaign(self):
        campaign = AdCampaign.objects.create(
            platform=self.platform,
            name='Spring Campaign',
            campaign_type='SEASONAL',
            budget=1000000,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            created_by=self.user,
        )
        self.assertEqual(str(campaign), 'Spring Campaign')
        self.assertEqual(campaign.status, 'DRAFT')

    def test_budget_utilization(self):
        campaign = AdCampaign.objects.create(
            platform=self.platform,
            name='Test Campaign',
            budget=1000000,
            spent=500000,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            created_by=self.user,
        )
        self.assertEqual(campaign.budget_utilization, 50.0)

    def test_budget_utilization_zero(self):
        campaign = AdCampaign.objects.create(
            platform=self.platform,
            name='Zero Budget',
            budget=0,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            created_by=self.user,
        )
        self.assertEqual(campaign.budget_utilization, 0)


class AdCreativeModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='cretest', password='test1234',
            role='manager', name='Creative Tester',
        )
        self.platform = AdPlatform.objects.create(
            name='Meta Ads', platform_type='SOCIAL',
            created_by=self.user,
        )
        self.campaign = AdCampaign.objects.create(
            platform=self.platform,
            name='Creative Test Campaign',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            created_by=self.user,
        )

    def test_create_creative(self):
        creative = AdCreative.objects.create(
            campaign=self.campaign,
            name='Banner A',
            creative_type='IMAGE',
            headline='Buy Now!',
            created_by=self.user,
        )
        self.assertEqual(str(creative), 'Banner A')
        self.assertEqual(creative.status, 'DRAFT')


class AdPerformanceModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='perftest', password='test1234',
            role='manager', name='Perf Tester',
        )
        self.platform = AdPlatform.objects.create(
            name='Kakao Ads', platform_type='DISPLAY',
            created_by=self.user,
        )
        self.campaign = AdCampaign.objects.create(
            platform=self.platform,
            name='Perf Test Campaign',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            created_by=self.user,
        )

    def test_ctr(self):
        perf = AdPerformance.objects.create(
            campaign=self.campaign,
            date=date.today(),
            impressions=10000,
            clicks=250,
            created_by=self.user,
        )
        self.assertEqual(perf.ctr, 2.5)

    def test_cpc(self):
        perf = AdPerformance.objects.create(
            campaign=self.campaign,
            date=date.today(),
            clicks=100,
            cost=50000,
            created_by=self.user,
        )
        self.assertEqual(perf.cpc, 500)

    def test_roas(self):
        perf = AdPerformance.objects.create(
            campaign=self.campaign,
            date=date.today(),
            cost=100000,
            revenue=350000,
            created_by=self.user,
        )
        self.assertEqual(perf.roas, 350.0)

    def test_conversion_rate(self):
        perf = AdPerformance.objects.create(
            campaign=self.campaign,
            date=date.today(),
            clicks=200,
            conversions=10,
            created_by=self.user,
        )
        self.assertEqual(perf.conversion_rate, 5.0)

    def test_zero_division_safety(self):
        perf = AdPerformance.objects.create(
            campaign=self.campaign,
            date=date.today(),
            created_by=self.user,
        )
        self.assertEqual(perf.ctr, 0)
        self.assertEqual(perf.cpc, 0)
        self.assertEqual(perf.roas, 0)
        self.assertEqual(perf.conversion_rate, 0)


class AdBudgetModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='budtest', password='test1234',
            role='manager', name='Budget Tester',
        )
        self.platform = AdPlatform.objects.create(
            name='YouTube Ads', platform_type='VIDEO',
            created_by=self.user,
        )

    def test_create_budget(self):
        budget = AdBudget.objects.create(
            year=2026, month=3,
            platform=self.platform,
            planned_budget=5000000,
            actual_spent=2500000,
            created_by=self.user,
        )
        self.assertIn('YouTube Ads', str(budget))
        self.assertEqual(budget.utilization_rate, 50.0)

    def test_budget_without_platform(self):
        budget = AdBudget.objects.create(
            year=2026, month=3,
            planned_budget=10000000,
            created_by=self.user,
        )
        self.assertIn('전체', str(budget))

    def test_utilization_zero_budget(self):
        budget = AdBudget.objects.create(
            year=2026, month=4,
            planned_budget=0,
            created_by=self.user,
        )
        self.assertEqual(budget.utilization_rate, 0)

    def test_unique_together(self):
        AdBudget.objects.create(
            year=2026, month=5,
            platform=self.platform,
            planned_budget=1000000,
            created_by=self.user,
        )
        with self.assertRaises(Exception):
            AdBudget.objects.create(
                year=2026, month=5,
                platform=self.platform,
                planned_budget=2000000,
                created_by=self.user,
            )
