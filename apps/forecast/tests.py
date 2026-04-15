from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.inventory.models import Product
from apps.forecast.models import DemandForecast, ForecastParameter, SOPMeeting, SOPScenario, SOPLineItem


class ForecastParameterTest(TestCase):
    def setUp(self):
        self.product = Product.objects.create(name='테스트제품', code='FC-001')

    def test_parameter_creation(self):
        param = ForecastParameter.objects.create(
            product=self.product, method='MOVING_AVG',
            lookback_months=6, weight_recent=Decimal('0.50'),
        )
        self.assertEqual(str(param), '[FC-001] 테스트제품 - 이동평균')

    def test_unique_product_method(self):
        ForecastParameter.objects.create(
            product=self.product, method='MOVING_AVG',
        )
        with self.assertRaises(Exception):
            ForecastParameter.objects.create(
                product=self.product, method='MOVING_AVG',
            )


class DemandForecastTest(TestCase):
    def setUp(self):
        self.product = Product.objects.create(name='테스트제품', code='FC-002')

    def test_forecast_creation(self):
        fc = DemandForecast.objects.create(
            product=self.product,
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
            forecast_method='MOVING_AVG',
            forecast_qty=Decimal('100'),
        )
        self.assertEqual(fc.forecast_qty, Decimal('100'))

    def test_accuracy_calculation(self):
        fc = DemandForecast(
            product=self.product,
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
            forecast_qty=Decimal('100'),
            actual_qty=Decimal('90'),
        )
        fc.calculate_accuracy()
        self.assertAlmostEqual(float(fc.accuracy_pct), 88.89, places=1)

    def test_accuracy_perfect(self):
        fc = DemandForecast(
            product=self.product,
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
            forecast_qty=Decimal('100'),
            actual_qty=Decimal('100'),
        )
        fc.calculate_accuracy()
        self.assertEqual(fc.accuracy_pct, Decimal('100'))


class SOPMeetingTest(TestCase):
    def test_meeting_creation(self):
        meeting = SOPMeeting.objects.create(
            title='4월 S&OP 회의',
            meeting_date=date(2026, 4, 15),
            period='2026-Q2',
        )
        self.assertEqual(meeting.status, 'PLANNED')
        self.assertIn('4월', str(meeting))

    def test_scenario_and_line_items(self):
        meeting = SOPMeeting.objects.create(
            title='테스트', meeting_date=date(2026, 4, 15), period='Q2',
        )
        scenario = SOPScenario.objects.create(
            meeting=meeting, name='기본 시나리오',
        )
        product = Product.objects.create(name='제품A', code='SOP-001')
        item = SOPLineItem.objects.create(
            scenario=scenario, product=product,
            forecast_qty=Decimal('500'),
            planned_production=Decimal('450'),
            planned_purchase=Decimal('100'),
            planned_inventory=Decimal('50'),
        )
        self.assertEqual(item.forecast_qty, Decimal('500'))
        self.assertEqual(scenario.line_items.count(), 1)
