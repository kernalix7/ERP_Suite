from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.esg.models import (
    CarbonEmission, ComplianceRequirement, ESGCategory, ESGMetric,
    ESGRecord, ESGReport, SafetyIncident,
)

User = get_user_model()


class ESGCategoryModelTest(TestCase):
    def test_create_category(self):
        cat = ESGCategory.objects.create(
            name='에너지', code='ENV-E',
            category_type=ESGCategory.CategoryType.ENVIRONMENTAL,
        )
        self.assertEqual(str(cat), '[ENV-E] 에너지')
        self.assertTrue(cat.is_active)

    def test_parent_category(self):
        parent = ESGCategory.objects.create(
            name='환경', code='ENV',
            category_type=ESGCategory.CategoryType.ENVIRONMENTAL,
        )
        child = ESGCategory.objects.create(
            name='폐기물', code='ENV-W',
            category_type=ESGCategory.CategoryType.ENVIRONMENTAL,
            parent=parent,
        )
        self.assertEqual(child.parent, parent)


class ESGMetricModelTest(TestCase):
    def test_create_metric(self):
        cat = ESGCategory.objects.create(
            name='탄소', code='ENV-C',
            category_type=ESGCategory.CategoryType.ENVIRONMENTAL,
        )
        metric = ESGMetric.objects.create(
            category=cat, name='CO2 배출량', code='CO2',
            unit='tCO2eq', target_value=Decimal('100.00'),
        )
        self.assertIn('CO2', str(metric))
        self.assertEqual(metric.measurement_frequency, ESGMetric.Frequency.MONTHLY)


class ESGRecordModelTest(TestCase):
    def test_create_record(self):
        cat = ESGCategory.objects.create(
            name='환경', code='E01',
            category_type=ESGCategory.CategoryType.ENVIRONMENTAL,
        )
        metric = ESGMetric.objects.create(
            category=cat, name='전력사용량', code='ELEC', unit='kWh',
        )
        record = ESGRecord.objects.create(
            metric=metric,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            value=Decimal('15000.50'),
        )
        self.assertFalse(record.verified)
        self.assertIn('전력사용량', str(record))


class CarbonEmissionModelTest(TestCase):
    def test_create_emission(self):
        emission = CarbonEmission.objects.create(
            source='보일러', scope=CarbonEmission.Scope.SCOPE1,
            amount_kg=Decimal('500.00'), period=date(2026, 3, 1),
            facility='본사',
        )
        self.assertIn('보일러', str(emission))
        self.assertIn('Scope 1', str(emission))

    def test_scope_choices(self):
        self.assertEqual(len(CarbonEmission.Scope.choices), 3)


class SafetyIncidentModelTest(TestCase):
    def test_auto_number(self):
        incident = SafetyIncident.objects.create(
            date=date.today(), location='공장 A동',
            severity=SafetyIncident.Severity.MINOR,
            description='작업 중 경미한 부상',
        )
        self.assertTrue(incident.incident_number.startswith('SI-'))

    def test_default_status(self):
        incident = SafetyIncident.objects.create(
            date=date.today(), location='사무실',
            severity=SafetyIncident.Severity.NEAR_MISS,
            description='아차사고 발생',
        )
        self.assertEqual(incident.status, SafetyIncident.Status.REPORTED)
        self.assertEqual(incident.injured_count, 0)


class ComplianceRequirementModelTest(TestCase):
    def test_create_requirement(self):
        req = ComplianceRequirement.objects.create(
            name='개인정보보호법 준수',
            regulation='개인정보보호법',
            description='연간 정보보호 교육 실시',
        )
        self.assertEqual(req.status, ComplianceRequirement.Status.PENDING)
        self.assertIn('개인정보보호법', str(req))


class ESGReportModelTest(TestCase):
    def test_create_report(self):
        report = ESGReport.objects.create(
            title='2026 ESG 연간보고서',
            report_type=ESGReport.ReportType.ANNUAL,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 12, 31),
        )
        self.assertEqual(report.status, ESGReport.Status.DRAFT)
        self.assertIn('2026', str(report))


class ESGViewAccessTest(TestCase):
    """ESG 뷰 접근 권한 테스트 (비인증/비권한 거부 확인)"""

    def setUp(self):
        self.manager = User.objects.create_user(
            username='mgr_esg', password='testpass123', role='manager',
        )
        self.staff = User.objects.create_user(
            username='staff_esg', password='testpass123', role='staff',
        )

    def test_metric_list_requires_login(self):
        resp = self.client.get('/esg/metrics/')
        self.assertEqual(resp.status_code, 302)

    def test_metric_create_requires_manager(self):
        self.client.force_login(self.staff)
        resp = self.client.get('/esg/metrics/create/')
        self.assertIn(resp.status_code, [302, 403])

    def test_record_create_requires_manager(self):
        self.client.force_login(self.staff)
        resp = self.client.get('/esg/records/create/')
        self.assertIn(resp.status_code, [302, 403])

    def test_carbon_create_requires_manager(self):
        self.client.force_login(self.staff)
        resp = self.client.get('/esg/carbon/create/')
        self.assertIn(resp.status_code, [302, 403])

    def test_dashboard_requires_login(self):
        resp = self.client.get('/esg/')
        self.assertEqual(resp.status_code, 302)
