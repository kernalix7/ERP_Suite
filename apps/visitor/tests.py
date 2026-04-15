from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from .models import VisitorPurpose, Visitor, VisitRequest, VisitLog

User = get_user_model()


class VisitorModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='reception', password='pass')
        self.purpose = VisitorPurpose.objects.create(
            name='업무미팅', code='MTG', created_by=self.user,
        )
        self.visitor = Visitor.objects.create(
            name='홍길동', company='테스트(주)', created_by=self.user,
        )

    def test_visit_request_auto_number(self):
        req = VisitRequest.objects.create(
            visitor=self.visitor,
            host=self.user,
            purpose=self.purpose,
            scheduled_at=timezone.now(),
            created_by=self.user,
        )
        self.assertTrue(req.visit_number.startswith('VIS'))

    def test_visit_log_duration(self):
        req = VisitRequest.objects.create(
            visitor=self.visitor,
            host=self.user,
            purpose=self.purpose,
            scheduled_at=timezone.now(),
            created_by=self.user,
        )
        check_in = timezone.now()
        check_out = check_in + timezone.timedelta(minutes=45)
        log = VisitLog.objects.create(
            visit_request=req,
            visitor=self.visitor,
            check_in_at=check_in,
            check_out_at=check_out,
            created_by=self.user,
        )
        self.assertEqual(log.duration_minutes, 45)

    def test_visitor_str(self):
        self.assertEqual(str(self.visitor), '홍길동 (테스트(주))')


class VisitorViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username='vis_staff', password='pass', role='staff',
        )
        self.manager_user = User.objects.create_user(
            username='vis_manager', password='pass', role='manager',
        )

    def test_visit_request_list_requires_login(self):
        response = self.client.get(reverse('visitor:visit_request_list'))
        self.assertIn(response.status_code, [302, 403])

    def test_visit_log_list_requires_manager(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('visitor:visit_log_list'))
        self.assertEqual(response.status_code, 403)

    def test_visit_log_list_unauthenticated_redirects(self):
        response = self.client.get(reverse('visitor:visit_log_list'))
        self.assertEqual(response.status_code, 302)

    def test_visitor_list_requires_manager(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('visitor:visitor_list'))
        self.assertEqual(response.status_code, 403)

    def test_purpose_create_requires_manager(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('visitor:purpose_create'))
        self.assertEqual(response.status_code, 403)
