from unittest.mock import patch, MagicMock

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User

from .models import (
    EscalationRule,
    SLA,
    SLABreach,
    Ticket,
    TicketCategory,
    TicketComment,
)


class SLATests(TestCase):
    def test_create_sla(self):
        sla = SLA.objects.create(
            name='표준 SLA',
            response_time_hours=4,
            resolution_time_hours=24,
            escalation_time_hours=8,
        )
        self.assertEqual(str(sla), '표준 SLA')
        self.assertEqual(sla.response_time_hours, 4)


class TicketCategoryTests(TestCase):
    def test_create_category(self):
        sla = SLA.objects.create(name='기본 SLA', response_time_hours=4,
                                 resolution_time_hours=24, escalation_time_hours=8)
        cat = TicketCategory.objects.create(
            name='하드웨어',
            default_priority='HIGH',
            default_sla=sla,
        )
        self.assertEqual(str(cat), '하드웨어')
        self.assertEqual(cat.default_priority, 'HIGH')

    def test_parent_child(self):
        parent = TicketCategory.objects.create(name='IT 지원')
        child = TicketCategory.objects.create(name='네트워크', parent=parent)
        self.assertEqual(child.parent, parent)
        self.assertIn(child, parent.children.all())


class TicketTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='reporter01', password='testpass123',
        )
        self.manager = User.objects.create_user(
            username='manager01', password='testpass123',
        )
        self.sla = SLA.objects.create(
            name='표준', response_time_hours=4,
            resolution_time_hours=24, escalation_time_hours=8,
        )
        self.category = TicketCategory.objects.create(
            name='소프트웨어', default_sla=self.sla,
        )

    def test_create_ticket_auto_number(self):
        ticket = Ticket.objects.create(
            title='로그인 오류',
            description='로그인이 되지 않습니다',
            reporter=self.user,
            category=self.category,
        )
        self.assertTrue(ticket.ticket_number.startswith('TK-'))
        self.assertEqual(ticket.status, Ticket.Status.OPEN)
        self.assertEqual(ticket.sla, self.sla)

    def test_status_flow(self):
        ticket = Ticket.objects.create(
            title='프린터 오류',
            description='프린터가 작동하지 않습니다',
            reporter=self.user,
        )
        flow = [
            Ticket.Status.OPEN,
            Ticket.Status.ASSIGNED,
            Ticket.Status.IN_PROGRESS,
            Ticket.Status.WAITING,
            Ticket.Status.RESOLVED,
            Ticket.Status.CLOSED,
        ]
        self.assertEqual(ticket.status, flow[0])
        for next_status in flow[1:]:
            ticket.status = next_status
            ticket.save()
            ticket.refresh_from_db()
            self.assertEqual(ticket.status, next_status)

    def test_soft_delete(self):
        ticket = Ticket.objects.create(
            title='삭제 테스트',
            description='soft delete 테스트',
            reporter=self.user,
        )
        ticket_number = ticket.ticket_number
        ticket.soft_delete()
        self.assertFalse(Ticket.objects.filter(ticket_number=ticket_number).exists())
        self.assertTrue(Ticket.all_objects.filter(pk=ticket.pk).exists())

    def test_sla_from_category(self):
        ticket = Ticket.objects.create(
            title='SLA 자동 할당',
            description='카테고리의 기본 SLA가 할당되어야 합니다',
            reporter=self.user,
            category=self.category,
        )
        self.assertEqual(ticket.sla, self.sla)

    def test_priority_from_category(self):
        cat = TicketCategory.objects.create(name='긴급분류', default_priority='URGENT')
        ticket = Ticket.objects.create(
            title='긴급 이슈',
            description='긴급 카테고리 우선순위 상속',
            reporter=self.user,
            category=cat,
        )
        self.assertEqual(ticket.priority, 'URGENT')


class TicketCommentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='commenter01', password='testpass123',
        )
        self.ticket = Ticket.objects.create(
            title='코멘트 테스트',
            description='코멘트 테스트용 티켓',
            reporter=self.user,
        )

    def test_create_comment(self):
        comment = TicketComment.objects.create(
            ticket=self.ticket,
            author=self.user,
            content='테스트 코멘트입니다.',
        )
        self.assertFalse(comment.is_internal)
        self.assertEqual(comment.ticket, self.ticket)

    def test_internal_comment(self):
        comment = TicketComment.objects.create(
            ticket=self.ticket,
            author=self.user,
            content='내부 메모입니다.',
            is_internal=True,
        )
        self.assertTrue(comment.is_internal)


class EscalationRuleTests(TestCase):
    def test_create_rule(self):
        user = User.objects.create_user(username='escalator01', password='testpass123')
        cat = TicketCategory.objects.create(name='테스트 분류')
        rule = EscalationRule.objects.create(
            category=cat,
            condition_type=EscalationRule.ConditionType.RESPONSE_OVERDUE,
            escalate_to=user,
            notify_method='EMAIL',
        )
        self.assertEqual(rule.condition_type, 'RESPONSE_OVERDUE')
        self.assertIn('응답 지연', str(rule))


class SLABreachModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='breach_user', password='testpass123')
        self.sla = SLA.objects.create(
            name='SLA 위반테스트',
            response_time_hours=4,
            resolution_time_hours=24,
            escalation_time_hours=8,
        )
        self.ticket = Ticket.objects.create(
            title='위반 티켓',
            description='SLA 위반 테스트용',
            reporter=self.user,
            sla=self.sla,
        )

    def test_create_sla_breach(self):
        breach = SLABreach.objects.create(
            ticket=self.ticket,
            sla=self.sla,
            breach_type=SLABreach.BreachType.RESPONSE,
        )
        self.assertEqual(breach.breach_type, 'RESPONSE')
        self.assertFalse(breach.notified)
        self.assertIn(self.ticket.ticket_number, str(breach))

    def test_unique_together_prevents_duplicate(self):
        SLABreach.objects.create(
            ticket=self.ticket,
            sla=self.sla,
            breach_type=SLABreach.BreachType.RESPONSE,
        )
        _, created = SLABreach.objects.get_or_create(
            ticket=self.ticket,
            breach_type=SLABreach.BreachType.RESPONSE,
            defaults={'sla': self.sla},
        )
        self.assertFalse(created)
        self.assertEqual(SLABreach.objects.filter(ticket=self.ticket).count(), 1)


class CheckSLABreachesTaskTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_sla', password='testpass123', role='admin',
        )
        self.reporter = User.objects.create_user(
            username='reporter_sla', password='testpass123',
        )
        self.sla = SLA.objects.create(
            name='표준',
            response_time_hours=4,
            resolution_time_hours=24,
            escalation_time_hours=8,
        )

    def _make_ticket(self, response_due_offset=None, resolution_due_offset=None,
                     status=Ticket.Status.OPEN, priority=Ticket.Priority.MEDIUM):
        now = timezone.now()
        ticket = Ticket.objects.create(
            title='SLA 테스트 티켓',
            description='테스트',
            reporter=self.reporter,
            sla=self.sla,
            status=status,
            priority=priority,
        )
        update_fields = []
        if response_due_offset is not None:
            ticket.sla_response_due = now + timezone.timedelta(hours=response_due_offset)
            update_fields.append('sla_response_due')
        if resolution_due_offset is not None:
            ticket.sla_resolution_due = now + timezone.timedelta(hours=resolution_due_offset)
            update_fields.append('sla_resolution_due')
        if update_fields:
            ticket.save(update_fields=update_fields)
        return ticket

    @patch('apps.core.notification.send_realtime_notification')
    @patch('apps.core.email.send_mail')
    def test_response_breach_creates_slabreach(self, mock_mail, mock_ws):
        """응답시간 초과 → SLABreach(RESPONSE) 생성"""
        ticket = self._make_ticket(response_due_offset=-1)  # 1시간 전 초과
        from apps.helpdesk.tasks import check_sla_breaches
        check_sla_breaches()
        self.assertTrue(SLABreach.objects.filter(ticket=ticket, breach_type='RESPONSE').exists())

    @patch('apps.core.notification.send_realtime_notification')
    @patch('apps.core.email.send_mail')
    def test_resolution_breach_creates_slabreach(self, mock_mail, mock_ws):
        """해결시간 초과 → SLABreach(RESOLUTION) 생성"""
        ticket = self._make_ticket(resolution_due_offset=-1)
        from apps.helpdesk.tasks import check_sla_breaches
        check_sla_breaches()
        self.assertTrue(SLABreach.objects.filter(ticket=ticket, breach_type='RESOLUTION').exists())

    @patch('apps.core.notification.send_realtime_notification')
    @patch('apps.core.email.send_mail')
    def test_breach_escalates_priority(self, mock_mail, mock_ws):
        """SLA 위반 시 priority 상향"""
        ticket = self._make_ticket(response_due_offset=-1, priority=Ticket.Priority.LOW)
        from apps.helpdesk.tasks import check_sla_breaches
        check_sla_breaches()
        ticket.refresh_from_db()
        self.assertEqual(ticket.priority, Ticket.Priority.MEDIUM)

    @patch('apps.core.notification.send_realtime_notification')
    @patch('apps.core.email.send_mail')
    def test_no_duplicate_slabreach(self, mock_mail, mock_ws):
        """SLA 위반 중복 생성 방지"""
        ticket = self._make_ticket(response_due_offset=-1)
        from apps.helpdesk.tasks import check_sla_breaches
        check_sla_breaches()
        check_sla_breaches()  # 두 번 실행
        self.assertEqual(
            SLABreach.objects.filter(ticket=ticket, breach_type='RESPONSE').count(), 1,
        )

    @patch('apps.core.notification.send_realtime_notification')
    def test_no_breach_when_within_sla(self, mock_ws):
        """SLA 미초과 → SLABreach 미생성"""
        ticket = self._make_ticket(response_due_offset=+2)  # 2시간 후 만료
        from apps.helpdesk.tasks import check_sla_breaches
        check_sla_breaches()
        self.assertFalse(SLABreach.objects.filter(ticket=ticket).exists())

    @patch('apps.core.notification.send_realtime_notification')
    def test_closed_ticket_skipped(self, mock_ws):
        """종료된 티켓은 SLA 점검 대상 제외"""
        ticket = self._make_ticket(
            response_due_offset=-1, status=Ticket.Status.CLOSED,
        )
        from apps.helpdesk.tasks import check_sla_breaches
        check_sla_breaches()
        self.assertFalse(SLABreach.objects.filter(ticket=ticket).exists())


class EmailNotificationIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='email_user', password='testpass123',
            email='test@example.com',
        )
        self.user_no_email = User.objects.create_user(
            username='noemail_user', password='testpass123',
            email='',
        )

    @patch('apps.core.email.send_mail')
    @patch('apps.core.notification.send_realtime_notification')
    def test_email_sent_for_matching_noti_type(self, mock_ws, mock_mail):
        """EMAIL_NOTIFY_TYPES에 포함된 유형 → 이메일 발송"""
        from apps.core.notification import create_notification
        create_notification(
            users=[self.user],
            title='재고 부족',
            message='재고가 부족합니다.',
            noti_type='STOCK_LOW',
        )
        mock_mail.assert_called_once()

    @patch('apps.core.email.send_mail')
    @patch('apps.core.notification.send_realtime_notification')
    def test_email_not_sent_for_unmatched_noti_type(self, mock_ws, mock_mail):
        """EMAIL_NOTIFY_TYPES에 없는 유형 → 이메일 미발송"""
        from apps.core.notification import create_notification
        create_notification(
            users=[self.user],
            title='신규 주문',
            message='주문이 접수되었습니다.',
            noti_type='ORDER_NEW',
        )
        mock_mail.assert_not_called()

    @patch('apps.core.email.send_mail')
    @patch('apps.core.notification.send_realtime_notification')
    def test_email_not_sent_when_no_email_address(self, mock_ws, mock_mail):
        """이메일 주소 없는 사용자 → send_mail 미호출"""
        from apps.core.notification import create_notification
        create_notification(
            users=[self.user_no_email],
            title='SLA 위반',
            message='SLA가 위반되었습니다.',
            noti_type='SLA_BREACH',
        )
        mock_mail.assert_not_called()

    @patch('apps.core.notification.send_realtime_notification')
    def test_email_failure_does_not_propagate(self, mock_ws):
        """이메일 발송 실패 시 예외 전파 없이 경고만 기록"""
        import smtplib
        from apps.core.notification import create_notification
        with patch('apps.core.email.send_mail', side_effect=smtplib.SMTPException('fail')):
            # 예외 전파 없이 정상 완료되어야 함
            create_notification(
                users=[self.user],
                title='테스트',
                message='메시지',
                noti_type='APPROVAL',
            )
        # 알림 DB 레코드는 생성되어야 함
        from apps.core.notification import Notification
        self.assertTrue(Notification.objects.filter(user=self.user).exists())


class HelpdeskViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='hd_staff', password='testpass123', role='staff',
        )
        self.manager = User.objects.create_user(
            username='hd_manager', password='testpass123', role='manager',
        )

    def test_ticket_list_requires_login(self):
        resp = self.client.get(reverse('helpdesk:ticket_list'))
        self.assertEqual(resp.status_code, 302)

    def test_ticket_list_authenticated(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('helpdesk:ticket_list'))
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_requires_login(self):
        resp = self.client.get(reverse('helpdesk:dashboard'))
        self.assertEqual(resp.status_code, 302)

    def test_dashboard_authenticated(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('helpdesk:dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_category_list_requires_manager(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('helpdesk:category_list'))
        self.assertEqual(resp.status_code, 403)

    def test_category_list_manager_ok(self):
        self.client.force_login(self.manager)
        resp = self.client.get(reverse('helpdesk:category_list'))
        self.assertEqual(resp.status_code, 200)

    def test_resolve_requires_manager(self):
        self.client.force_login(self.staff)
        ticket = Ticket.objects.create(
            title='테스트', description='테스트', reporter=self.staff,
        )
        resp = self.client.post(reverse('helpdesk:ticket_resolve', kwargs={'ticket_number': ticket.ticket_number}))
        self.assertEqual(resp.status_code, 403)
