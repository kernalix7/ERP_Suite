import json

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model

from .models import Report, Dashboard, DashboardPanel, SavedFilter, ReportSchedule
from .views import _sanitize_filters, ALLOWED_FILTER_KEYS, DATA_SOURCE_SCHEMA

User = get_user_model()


class ReportModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='biuser', password='testpass123', role='admin',
        )

    def test_create_report(self):
        report = Report.objects.create(
            name='월별 매출',
            report_type='CHART',
            data_source='ORDER',
            owner=self.user,
            created_by=self.user,
        )
        self.assertEqual(str(report), '월별 매출')
        self.assertTrue(report.is_active)

    def test_report_soft_delete(self):
        report = Report.objects.create(
            name='테스트 리포트',
            report_type='TABLE',
            data_source='PRODUCT',
            owner=self.user,
            created_by=self.user,
        )
        report.soft_delete()
        self.assertFalse(Report.objects.filter(pk=report.pk).exists())
        self.assertTrue(Report.all_objects.filter(pk=report.pk).exists())

    def test_report_query_config_default(self):
        report = Report.objects.create(
            name='기본 설정 리포트',
            report_type='KPI',
            data_source='INVENTORY',
            owner=self.user,
            created_by=self.user,
        )
        self.assertEqual(report.query_config, {})
        self.assertEqual(report.chart_config, {})


class DashboardModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='dashuser', password='testpass123', role='admin',
        )

    def test_create_dashboard(self):
        dashboard = Dashboard.objects.create(
            name='메인 대시보드',
            owner=self.user,
            created_by=self.user,
        )
        self.assertEqual(str(dashboard), '메인 대시보드')

    def test_dashboard_panel(self):
        dashboard = Dashboard.objects.create(
            name='테스트 대시보드',
            owner=self.user,
            created_by=self.user,
        )
        report = Report.objects.create(
            name='패널 리포트',
            report_type='CHART',
            data_source='ORDER',
            owner=self.user,
            created_by=self.user,
        )
        panel = DashboardPanel.objects.create(
            dashboard=dashboard,
            report=report,
            position_x=0,
            position_y=0,
            width=6,
            height=4,
            created_by=self.user,
        )
        self.assertEqual(panel.dashboard, dashboard)
        self.assertEqual(panel.report, report)
        self.assertEqual(dashboard.panels.count(), 1)


class SavedFilterModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='filteruser', password='testpass123', role='admin',
        )

    def test_create_saved_filter(self):
        sf = SavedFilter.objects.create(
            name='최근 3개월 주문',
            data_source='ORDER',
            filter_config={'order_date__gte': '2026-01-01'},
            owner=self.user,
            created_by=self.user,
        )
        self.assertEqual(str(sf), '최근 3개월 주문')


class ReportScheduleModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='scheduser', password='testpass123', role='admin',
        )

    def test_create_schedule(self):
        report = Report.objects.create(
            name='스케줄 리포트',
            report_type='TABLE',
            data_source='ORDER',
            owner=self.user,
            created_by=self.user,
        )
        schedule = ReportSchedule.objects.create(
            report=report,
            frequency='WEEKLY',
            format='PDF',
            created_by=self.user,
        )
        self.assertEqual(str(schedule), '스케줄 리포트 - 매주')


class ReportViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='viewuser', password='testpass123', role='admin',
        )
        self.client.force_login(self.user)

    def test_report_list_view(self):
        response = self.client.get('/bi/reports/')
        self.assertEqual(response.status_code, 200)

    def test_report_create_view(self):
        response = self.client.get('/bi/reports/create/')
        self.assertEqual(response.status_code, 200)

    def test_dashboard_list_view(self):
        response = self.client.get('/bi/dashboards/')
        self.assertEqual(response.status_code, 200)

    def test_data_source_schema_view(self):
        response = self.client.get('/bi/schema/ORDER/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('fields', data)

    def test_data_source_schema_invalid(self):
        response = self.client.get('/bi/schema/INVALID/')
        self.assertEqual(response.status_code, 400)

    def test_schedule_list_view(self):
        response = self.client.get('/bi/schedules/')
        self.assertEqual(response.status_code, 200)


class BiFilterSanitizationTest(TestCase):
    """ORM 인젝션 방지 화이트리스트 테스트"""

    def test_allowed_filter_passes(self):
        filters = {'order_date__gte': '2026-01-01', 'status': 'CONFIRMED'}
        result = _sanitize_filters(filters, 'ORDER')
        self.assertEqual(len(result), 2)

    def test_disallowed_filter_stripped(self):
        filters = {
            'status': 'CONFIRMED',
            'owner__password': 'hack',
            'partner__owner__is_superuser': True,
        }
        result = _sanitize_filters(filters, 'ORDER')
        self.assertEqual(list(result.keys()), ['status'])

    def test_empty_filters(self):
        result = _sanitize_filters({}, 'ORDER')
        self.assertEqual(result, {})

    def test_unknown_data_source(self):
        result = _sanitize_filters({'anything': 'val'}, 'NONEXISTENT')
        self.assertEqual(result, {})

    def test_all_sources_have_whitelist(self):
        for source in DATA_SOURCE_SCHEMA:
            self.assertIn(source, ALLOWED_FILTER_KEYS)
            self.assertTrue(len(ALLOWED_FILTER_KEYS[source]) > 0)


class BiPermissionTest(TestCase):
    """CUD 뷰 권한 테스트 — staff 사용자는 403"""

    def setUp(self):
        self.staff = User.objects.create_user(
            username='staffuser', password='testpass123', role='staff',
        )
        self.manager = User.objects.create_user(
            username='mgruser', password='testpass123', role='manager',
        )

    def test_staff_cannot_create_report(self):
        self.client.force_login(self.staff)
        response = self.client.get('/bi/reports/create/')
        self.assertEqual(response.status_code, 403)

    def test_manager_can_create_report(self):
        self.client.force_login(self.manager)
        response = self.client.get('/bi/reports/create/')
        self.assertEqual(response.status_code, 200)

    def test_staff_cannot_create_dashboard(self):
        self.client.force_login(self.staff)
        response = self.client.get('/bi/dashboards/create/')
        self.assertEqual(response.status_code, 403)

    def test_staff_cannot_create_schedule(self):
        self.client.force_login(self.staff)
        response = self.client.get('/bi/schedules/create/')
        self.assertEqual(response.status_code, 403)

    def test_staff_cannot_delete_report(self):
        self.client.force_login(self.staff)
        report = Report.objects.create(
            name='테스트', report_type='CHART', data_source='ORDER',
            owner=self.staff, created_by=self.staff,
        )
        response = self.client.post(f'/bi/reports/{report.pk}/delete/')
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_redirect(self):
        response = self.client.get('/bi/reports/')
        self.assertEqual(response.status_code, 302)

    def test_staff_can_read_report_list(self):
        self.client.force_login(self.staff)
        response = self.client.get('/bi/reports/')
        self.assertEqual(response.status_code, 200)

    def test_staff_can_read_dashboard_list(self):
        self.client.force_login(self.staff)
        response = self.client.get('/bi/dashboards/')
        self.assertEqual(response.status_code, 200)


class BiDrillDownSecurityTest(TestCase):
    """DrillDown 뷰 필터 검증 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='drilluser', password='testpass123', role='admin',
        )
        self.client.force_login(self.user)
        self.report = Report.objects.create(
            name='드릴다운', report_type='CHART', data_source='ORDER',
            owner=self.user, created_by=self.user,
        )

    def test_drill_down_strips_malicious_filters(self):
        response = self.client.post(
            f'/bi/reports/{self.report.pk}/drill-down/',
            data=json.dumps({
                'filters': {
                    'status': 'CONFIRMED',
                    'owner__password__startswith': 'a',
                },
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
