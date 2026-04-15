from django.test import TestCase
from django.contrib.auth import get_user_model

from .models import AutomationRule, RuleAction, RuleCondition, AutomationLog, AutomationSchedule
from .engine import (
    check_conditions, execute_rule, execute_action,
    _get_allowed_model, _get_allowed_function, _validate_webhook_url,
    register_rpa_function,
)

User = get_user_model()


class AutomationRuleModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='rpauser', password='testpass123', role='admin',
        )

    def test_create_rule(self):
        rule = AutomationRule.objects.create(
            name='재고부족 알림',
            trigger_type='EVENT',
            trigger_config={'event_model': 'inventory.Product', 'event_action': 'update'},
            owner=self.user,
            created_by=self.user,
        )
        self.assertEqual(str(rule), '재고부족 알림')
        self.assertTrue(rule.is_active)
        self.assertEqual(rule.run_count, 0)

    def test_rule_soft_delete(self):
        rule = AutomationRule.objects.create(
            name='삭제 테스트',
            trigger_type='SCHEDULE',
            owner=self.user,
            created_by=self.user,
        )
        rule.soft_delete()
        self.assertFalse(AutomationRule.objects.filter(pk=rule.pk).exists())
        self.assertTrue(AutomationRule.all_objects.filter(pk=rule.pk).exists())


class RuleActionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='actuser', password='testpass123', role='admin',
        )
        self.rule = AutomationRule.objects.create(
            name='테스트 규칙',
            trigger_type='EVENT',
            owner=self.user,
            created_by=self.user,
        )

    def test_create_action(self):
        action = RuleAction.objects.create(
            rule=self.rule,
            sequence=1,
            action_type='SEND_NOTIFICATION',
            action_config={'title': '테스트', 'message': '알림'},
            created_by=self.user,
        )
        self.assertEqual(action.rule, self.rule)
        self.assertEqual(action.on_error, 'SKIP')


class RuleConditionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='conduser', password='testpass123', role='admin',
        )
        self.rule = AutomationRule.objects.create(
            name='조건 테스트',
            trigger_type='CONDITION',
            owner=self.user,
            created_by=self.user,
        )

    def test_create_condition(self):
        cond = RuleCondition.objects.create(
            rule=self.rule,
            field='current_stock',
            operator='LT',
            value='10',
            created_by=self.user,
        )
        self.assertEqual(str(cond), 'current_stock LT 10')


class EngineTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='enguser', password='testpass123', role='admin',
        )

    def test_check_conditions_no_conditions(self):
        rule = AutomationRule.objects.create(
            name='무조건 실행', trigger_type='EVENT',
            owner=self.user, created_by=self.user,
        )
        self.assertTrue(check_conditions(rule))

    def test_check_conditions_eq(self):
        rule = AutomationRule.objects.create(
            name='조건 테스트', trigger_type='CONDITION',
            owner=self.user, created_by=self.user,
        )
        RuleCondition.objects.create(
            rule=rule, field='status', operator='EQ', value='LOW',
            created_by=self.user,
        )
        self.assertTrue(check_conditions(rule, {'status': 'LOW'}))
        self.assertFalse(check_conditions(rule, {'status': 'OK'}))

    def test_execute_rule_no_actions(self):
        rule = AutomationRule.objects.create(
            name='빈 규칙', trigger_type='EVENT',
            owner=self.user, created_by=self.user,
        )
        log = execute_rule(rule)
        self.assertEqual(log.status, 'SUCCESS')
        self.assertEqual(log.actions_executed, 0)

    def test_execute_rule_with_notification(self):
        rule = AutomationRule.objects.create(
            name='알림 규칙', trigger_type='EVENT',
            owner=self.user, created_by=self.user,
        )
        RuleAction.objects.create(
            rule=rule, sequence=1,
            action_type='SEND_NOTIFICATION',
            action_config={'title': '테스트', 'message': '자동알림', 'users': 'admin'},
            created_by=self.user,
        )
        log = execute_rule(rule)
        self.assertEqual(log.status, 'SUCCESS')
        self.assertEqual(log.actions_executed, 1)


class RuleViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='viewuser', password='testpass123', role='admin',
        )
        self.client.force_login(self.user)

    def test_rule_list_view(self):
        response = self.client.get('/rpa/rules/')
        self.assertEqual(response.status_code, 200)

    def test_rule_create_view(self):
        response = self.client.get('/rpa/rules/create/')
        self.assertEqual(response.status_code, 200)

    def test_dashboard_view(self):
        response = self.client.get('/rpa/')
        self.assertEqual(response.status_code, 200)

    def test_log_list_view(self):
        response = self.client.get('/rpa/logs/')
        self.assertEqual(response.status_code, 200)

    def test_schedule_list_view(self):
        response = self.client.get('/rpa/schedules/')
        self.assertEqual(response.status_code, 200)


class RpaSecurityTest(TestCase):
    """RPA 엔진 보안 테스트 (RCE/SSRF 방지)"""

    def test_disallowed_model_raises(self):
        with self.assertRaises(ValueError) as ctx:
            _get_allowed_model('django.contrib.auth.models.User')
        self.assertIn('not allowed', str(ctx.exception))

    def test_allowed_model_returns_class(self):
        model_class = _get_allowed_model('inventory.Product')
        self.assertEqual(model_class.__name__, 'Product')

    def test_disallowed_function_raises(self):
        with self.assertRaises(ValueError) as ctx:
            _get_allowed_function('os.system')
        self.assertIn('not registered', str(ctx.exception))

    def test_registered_function_works(self):
        called = []
        register_rpa_function('test_func', lambda data: called.append(data))
        func = _get_allowed_function('test_func')
        func({'key': 'val'})
        self.assertEqual(len(called), 1)

    def test_webhook_localhost_blocked(self):
        with self.assertRaises(ValueError):
            _validate_webhook_url('http://localhost:8000/admin/')

    def test_webhook_127_blocked(self):
        with self.assertRaises(ValueError):
            _validate_webhook_url('http://127.0.0.1:9090/metrics')

    def test_webhook_private_ip_blocked(self):
        with self.assertRaises(ValueError):
            _validate_webhook_url('http://192.168.1.1/internal')

    def test_webhook_internal_domain_blocked(self):
        with self.assertRaises(ValueError):
            _validate_webhook_url('http://redis.internal:6379/')

    def test_webhook_valid_url_passes(self):
        _validate_webhook_url('https://hooks.example.com/webhook')

    def test_webhook_invalid_scheme_blocked(self):
        with self.assertRaises(ValueError):
            _validate_webhook_url('ftp://evil.com/file')

    def test_run_function_rce_blocked(self):
        """importlib 기반 임의 함수 실행이 차단되는지 확인"""
        user = User.objects.create_user(
            username='rcetest', password='testpass123', role='admin',
        )
        rule = AutomationRule.objects.create(
            name='RCE 테스트', trigger_type='EVENT',
            owner=user, created_by=user,
        )
        action = RuleAction.objects.create(
            rule=rule, sequence=1,
            action_type='RUN_FUNCTION',
            action_config={'function_path': 'os.system'},
            created_by=user,
        )
        with self.assertRaises(ValueError) as ctx:
            execute_action(action, {})
        self.assertIn('not registered', str(ctx.exception))

    def test_create_record_arbitrary_model_blocked(self):
        """임의 모델 레코드 생성이 차단되는지 확인"""
        user = User.objects.create_user(
            username='createtest', password='testpass123', role='admin',
        )
        rule = AutomationRule.objects.create(
            name='CREATE 테스트', trigger_type='EVENT',
            owner=user, created_by=user,
        )
        action = RuleAction.objects.create(
            rule=rule, sequence=1,
            action_type='CREATE_RECORD',
            action_config={
                'target_model': 'django.contrib.auth.models.User',
                'field_values': {'username': 'hacker', 'is_superuser': True},
            },
            created_by=user,
        )
        with self.assertRaises(ValueError) as ctx:
            execute_action(action, {})
        self.assertIn('not allowed', str(ctx.exception))


class RpaPermissionTest(TestCase):
    """RPA 뷰 권한 테스트"""

    def setUp(self):
        self.staff = User.objects.create_user(
            username='rpastaff', password='testpass123', role='staff',
        )
        self.manager = User.objects.create_user(
            username='rpamgr', password='testpass123', role='manager',
        )

    def test_staff_cannot_create_rule(self):
        self.client.force_login(self.staff)
        response = self.client.get('/rpa/rules/create/')
        self.assertEqual(response.status_code, 403)

    def test_manager_can_create_rule(self):
        self.client.force_login(self.manager)
        response = self.client.get('/rpa/rules/create/')
        self.assertEqual(response.status_code, 200)

    def test_staff_can_read_rule_list(self):
        self.client.force_login(self.staff)
        response = self.client.get('/rpa/rules/')
        self.assertEqual(response.status_code, 200)

    def test_staff_can_read_logs(self):
        self.client.force_login(self.staff)
        response = self.client.get('/rpa/logs/')
        self.assertEqual(response.status_code, 200)

    def test_staff_cannot_create_schedule(self):
        self.client.force_login(self.staff)
        response = self.client.get('/rpa/schedules/create/')
        self.assertEqual(response.status_code, 403)

    def test_staff_cannot_delete_rule(self):
        self.client.force_login(self.staff)
        rule = AutomationRule.objects.create(
            name='삭제 테스트', trigger_type='EVENT',
            owner=self.manager, created_by=self.manager,
        )
        response = self.client.post(f'/rpa/rules/{rule.pk}/delete/')
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_redirect(self):
        response = self.client.get('/rpa/rules/')
        self.assertEqual(response.status_code, 302)

    def test_staff_can_read_dashboard(self):
        self.client.force_login(self.staff)
        response = self.client.get('/rpa/')
        self.assertEqual(response.status_code, 200)
