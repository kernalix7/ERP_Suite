import unittest.mock

from django.test import TestCase, RequestFactory
from django.utils import timezone

from apps.accounts.models import User
from .models import (
    ADDomain, ADOrganizationalUnit, ADGroup,
    ADUserMapping, ADSyncLog, ADGroupPolicy,
)
from .services import ADService


class ADDomainModelTest(TestCase):
    def setUp(self):
        self.domain = ADDomain.objects.create(
            name='테스트 도메인',
            domain='test.example.com',
            ldap_server='ldap://dc01.test.example.com:389',
            ldap_bind_dn='CN=svc,DC=test,DC=example,DC=com',
            ldap_bind_password='test_password',
            base_dn='DC=test,DC=example,DC=com',
        )

    def test_domain_creation(self):
        self.assertEqual(str(self.domain), '테스트 도메인 (test.example.com)')
        self.assertTrue(self.domain.sync_enabled)
        self.assertEqual(self.domain.sync_interval_minutes, 60)

    def test_domain_unique_constraint(self):
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            ADDomain.objects.create(
                name='중복 도메인',
                domain='test.example.com',
                ldap_server='ldap://dc02.test.example.com',
                ldap_bind_dn='CN=svc2,DC=test',
                ldap_bind_password='pw',
                base_dn='DC=test',
            )


class ADOrganizationalUnitTest(TestCase):
    def setUp(self):
        self.domain = ADDomain.objects.create(
            name='테스트', domain='test.local',
            ldap_server='ldap://test:389',
            ldap_bind_dn='CN=test', ldap_bind_password='pw',
            base_dn='DC=test',
        )
        self.ou = ADOrganizationalUnit.objects.create(
            domain=self.domain,
            distinguished_name='OU=Users,DC=test',
            name='Users',
        )

    def test_ou_creation(self):
        self.assertEqual(str(self.ou), 'Users')

    def test_nested_ou(self):
        child = ADOrganizationalUnit.objects.create(
            domain=self.domain,
            distinguished_name='OU=IT,OU=Users,DC=test',
            name='IT',
            parent=self.ou,
        )
        self.assertEqual(child.parent, self.ou)
        self.assertEqual(self.ou.children.count(), 1)


class ADGroupTest(TestCase):
    def setUp(self):
        self.domain = ADDomain.objects.create(
            name='테스트', domain='test.local',
            ldap_server='ldap://test:389',
            ldap_bind_dn='CN=test', ldap_bind_password='pw',
            base_dn='DC=test',
        )
        self.group = ADGroup.objects.create(
            domain=self.domain,
            distinguished_name='CN=Managers,OU=Groups,DC=test',
            sam_account_name='Managers',
            display_name='매니저 그룹',
            group_type='SECURITY',
            mapped_role='manager',
        )

    def test_group_creation(self):
        self.assertEqual(self.group.mapped_role, 'manager')
        self.assertIn('보안 그룹', str(self.group))

    def test_group_unique_dn(self):
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            ADGroup.objects.create(
                domain=self.domain,
                distinguished_name='CN=Managers,OU=Groups,DC=test',
                sam_account_name='Managers2',
            )


class ADUserMappingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123!',
            name='테스트 사용자',
        )
        self.domain = ADDomain.objects.create(
            name='테스트', domain='test.local',
            ldap_server='ldap://test:389',
            ldap_bind_dn='CN=test', ldap_bind_password='pw',
            base_dn='DC=test',
        )
        self.mapping = ADUserMapping.objects.create(
            user=self.user,
            domain=self.domain,
            distinguished_name='CN=testuser,OU=Users,DC=test',
            sam_account_name='testuser',
            object_guid='12345678-1234-1234-1234-123456789012',
        )

    def test_mapping_creation(self):
        self.assertEqual(self.mapping.sync_status, 'PENDING')
        self.assertIn('testuser', str(self.mapping))

    def test_one_to_one_constraint(self):
        User.objects.create_user(username='user2', password='pass123!')
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            ADUserMapping.objects.create(
                user=self.user,  # 이미 매핑된 사용자
                domain=self.domain,
                distinguished_name='CN=user2,OU=Users,DC=test',
                sam_account_name='user2',
                object_guid='22222222-2222-2222-2222-222222222222',
            )

    def test_group_membership(self):
        group = ADGroup.objects.create(
            domain=self.domain,
            distinguished_name='CN=Admins,DC=test',
            sam_account_name='Admins',
        )
        self.mapping.ad_groups.add(group)
        self.assertEqual(self.mapping.ad_groups.count(), 1)


class ADSyncLogTest(TestCase):
    def setUp(self):
        self.domain = ADDomain.objects.create(
            name='테스트', domain='test.local',
            ldap_server='ldap://test:389',
            ldap_bind_dn='CN=test', ldap_bind_password='pw',
            base_dn='DC=test',
        )

    def test_sync_log_creation(self):
        log = ADSyncLog.objects.create(
            domain=self.domain,
            sync_type='FULL',
            users_created=5,
            users_updated=10,
            users_disabled=2,
        )
        self.assertEqual(log.total_processed, 17)
        self.assertEqual(log.status, 'RUNNING')

    def test_sync_log_ordering(self):
        ADSyncLog.objects.create(domain=self.domain, sync_type='FULL')
        log2 = ADSyncLog.objects.create(domain=self.domain, sync_type='INCREMENTAL')
        logs = list(ADSyncLog.objects.all())
        self.assertEqual(logs[0], log2)  # 최신순


class ADGroupPolicyTest(TestCase):
    def setUp(self):
        self.domain = ADDomain.objects.create(
            name='테스트', domain='test.local',
            ldap_server='ldap://test:389',
            ldap_bind_dn='CN=test', ldap_bind_password='pw',
            base_dn='DC=test',
        )
        self.group = ADGroup.objects.create(
            domain=self.domain,
            distinguished_name='CN=ERP_Managers,DC=test',
            sam_account_name='ERP_Managers',
        )

    def test_policy_role_assignment(self):
        policy = ADGroupPolicy.objects.create(
            name='매니저 역할 부여',
            domain=self.domain,
            ad_group=self.group,
            action='ASSIGN_ROLE',
            action_value='manager',
            priority=10,
        )
        self.assertEqual(policy.action, 'ASSIGN_ROLE')
        self.assertEqual(policy.action_value, 'manager')


class ADServiceTest(TestCase):
    def setUp(self):
        self.domain = ADDomain.objects.create(
            name='테스트', domain='test.local',
            ldap_server='ldap://test:389',
            ldap_bind_dn='CN=test', ldap_bind_password='pw',
            base_dn='DC=test',
        )

    def test_connection_test_simulation(self):
        """LDAP 서버 미연결 시 시뮬레이션 모드 테스트"""
        service = ADService(self.domain)
        with unittest.mock.patch.object(service, '_get_connection', return_value=None):
            success, message = service.test_connection()
        self.assertTrue(success)
        self.assertIn('시뮬레이션', message)

    def test_sync_simulation(self):
        """LDAP 서버 미연결 시 동기화 시뮬레이션 테스트"""
        user = User.objects.create_user(username='admin', password='pass123!')
        service = ADService(self.domain)
        with unittest.mock.patch.object(service, '_get_connection', return_value=None):
            sync_log = service.sync(sync_type='FULL', triggered_by=user)
        self.assertEqual(sync_log.status, 'SUCCESS')
        self.assertIsNotNone(sync_log.finished_at)
        # 도메인의 last_sync_at도 갱신 확인
        self.domain.refresh_from_db()
        self.assertIsNotNone(self.domain.last_sync_at)


class ADSignalTest(TestCase):
    def test_user_deactivation_updates_mapping(self):
        """ERP 사용자 비활성화 시 AD 매핑 상태 변경"""
        user = User.objects.create_user(username='aduser', password='pass123!')
        domain = ADDomain.objects.create(
            name='테스트', domain='test.local',
            ldap_server='ldap://test:389',
            ldap_bind_dn='CN=test', ldap_bind_password='pw',
            base_dn='DC=test',
        )
        mapping = ADUserMapping.objects.create(
            user=user, domain=domain,
            distinguished_name='CN=aduser,DC=test',
            sam_account_name='aduser',
            object_guid='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
            sync_status='SYNCED',
        )

        # 사용자 비활성화
        user.is_active = False
        user.save()

        mapping.refresh_from_db()
        self.assertEqual(mapping.sync_status, 'DISABLED')
