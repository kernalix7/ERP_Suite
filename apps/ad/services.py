import logging
from datetime import datetime

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class ADService:
    """Active Directory 연동 서비스

    LDAP 프로토콜을 통해 AD 서버와 통신하며,
    사용자/그룹/OU 정보를 ERP 시스템과 동기화한다.

    실제 LDAP 통신은 ldap3 라이브러리를 사용하며,
    라이브러리 미설치 시 시뮬레이션 모드로 동작한다.
    """

    def __init__(self, domain):
        self.domain = domain
        self._connection = None

    def _get_connection(self):
        """LDAP 서버 연결 생성"""
        try:
            import ldap3
            from ldap3.core.exceptions import LDAPException
            server = ldap3.Server(
                self.domain.ldap_server,
                use_ssl=self.domain.use_ssl,
                get_info=ldap3.ALL,
                connect_timeout=5,
            )
            conn = ldap3.Connection(
                server,
                user=self.domain.ldap_bind_dn,
                password=self.domain.ldap_bind_password,
                auto_bind=True,
            )
            if self.domain.use_start_tls and not self.domain.use_ssl:
                conn.start_tls()
            return conn
        except ImportError:
            logger.warning('ldap3 라이브러리 미설치 - 시뮬레이션 모드')
            return None
        except (OSError, ConnectionError, ValueError) as e:
            logger.error('LDAP 연결 실패: %s', str(e))
            raise
        except LDAPException as e:
            logger.error('LDAP 연결 실패: %s', str(e))
            raise

    def test_connection(self):
        """AD 연결 테스트"""
        try:
            conn = self._get_connection()
            if conn is None:
                return True, 'ldap3 미설치 - 시뮬레이션 모드 (연결 가능 상태)'
            # 기본 DN으로 검색 테스트
            conn.search(
                self.domain.base_dn,
                '(objectClass=domain)',
                search_scope='BASE',
            )
            conn.unbind()
            return True, f'{self.domain.domain} 연결 성공'
        except (OSError, ConnectionError, ValueError) as e:
            return False, str(e)

    def sync(self, sync_type='FULL', triggered_by=None):
        """AD 동기화 실행"""
        from .models import ADSyncLog

        sync_log = ADSyncLog.objects.create(
            domain=self.domain,
            sync_type=sync_type,
            status='RUNNING',
            triggered_by=triggered_by,
            created_by=triggered_by,
        )

        try:
            conn = self._get_connection()

            if conn is None:
                # 시뮬레이션 모드: 기본 데이터 동기화 표시
                sync_log.status = 'SUCCESS'
                sync_log.finished_at = timezone.now()
                sync_log.save()
                self.domain.last_sync_at = timezone.now()
                self.domain.save(update_fields=['last_sync_at', 'updated_at'])
                return sync_log

            with transaction.atomic():
                if sync_type == 'FULL':
                    self._sync_ous(conn, sync_log)
                    self._sync_groups(conn, sync_log)
                    self._sync_users(conn, sync_log)
                else:
                    self._sync_users(conn, sync_log)

            conn.unbind()

            if sync_log.errors_count > 0:
                sync_log.status = 'PARTIAL'
            else:
                sync_log.status = 'SUCCESS'

            sync_log.finished_at = timezone.now()
            sync_log.save()

            self.domain.last_sync_at = timezone.now()
            self.domain.save(update_fields=['last_sync_at', 'updated_at'])

        except (OSError, ConnectionError, ValueError) as e:
            sync_log.status = 'FAILED'
            sync_log.error_details = str(e)
            sync_log.errors_count += 1
            sync_log.finished_at = timezone.now()
            sync_log.save()
            logger.error('AD 동기화 실패 (domain=%s): %s',
                         self.domain.name, str(e), exc_info=True)

        return sync_log

    def _sync_ous(self, conn, sync_log):
        """OU 동기화"""
        import ldap3
        from .models import ADOrganizationalUnit

        search_base = self.domain.base_dn
        conn.search(
            search_base,
            '(objectClass=organizationalUnit)',
            search_scope=ldap3.SUBTREE,
            attributes=['distinguishedName', 'name', 'description'],
        )

        for entry in conn.entries:
            dn = str(entry.distinguishedName)
            name = str(entry.name) if hasattr(entry, 'name') else dn.split(',')[0].split('=')[1]
            desc = str(entry.description) if hasattr(entry, 'description') else ''

            ADOrganizationalUnit.objects.update_or_create(
                distinguished_name=dn,
                defaults={
                    'domain': self.domain,
                    'name': name,
                    'description': desc,
                },
            )
            sync_log.ous_synced += 1

    def _sync_groups(self, conn, sync_log):
        """그룹 동기화"""
        import ldap3
        from .models import ADGroup

        search_base = self.domain.group_search_base or self.domain.base_dn
        conn.search(
            search_base,
            '(objectClass=group)',
            search_scope=ldap3.SUBTREE,
            attributes=[
                'distinguishedName', 'sAMAccountName',
                'displayName', 'description', 'groupType',
            ],
        )

        for entry in conn.entries:
            dn = str(entry.distinguishedName)
            sam = str(entry.sAMAccountName)

            ADGroup.objects.update_or_create(
                distinguished_name=dn,
                defaults={
                    'domain': self.domain,
                    'sam_account_name': sam,
                    'display_name': str(getattr(entry, 'displayName', sam)),
                    'description': str(getattr(entry, 'description', '')),
                },
            )
            sync_log.groups_synced += 1

    def _sync_users(self, conn, sync_log):
        """사용자 동기화"""
        import ldap3
        from apps.accounts.models import User
        from .models import ADUserMapping, ADGroup

        search_base = self.domain.user_search_base or self.domain.base_dn
        conn.search(
            search_base,
            '(&(objectClass=user)(objectCategory=person))',
            search_scope=ldap3.SUBTREE,
            attributes=[
                'distinguishedName', 'sAMAccountName',
                'userPrincipalName', 'objectGUID',
                'displayName', 'mail', 'telephoneNumber',
                'userAccountControl', 'memberOf',
                'pwdLastSet', 'lastLogon',
            ],
        )

        for entry in conn.entries:
            try:
                dn = str(entry.distinguishedName)
                sam = str(entry.sAMAccountName)
                guid = str(entry.objectGUID)
                upn = str(getattr(entry, 'userPrincipalName', ''))
                display_name = str(getattr(entry, 'displayName', sam))
                mail = str(getattr(entry, 'mail', ''))
                phone = str(getattr(entry, 'telephoneNumber', ''))

                # userAccountControl 비트마스크로 활성 상태 확인
                uac = int(getattr(entry, 'userAccountControl', 512))
                ad_enabled = not bool(uac & 0x2)  # ACCOUNTDISABLE 비트
                ad_locked = bool(uac & 0x10)  # LOCKOUT 비트

                # ERP 사용자 찾기 또는 생성
                mapping = ADUserMapping.objects.filter(object_guid=guid).first()

                if mapping:
                    # 기존 매핑 업데이트
                    user = mapping.user
                    user.name = display_name
                    if mail:
                        user.email = mail
                    if phone:
                        user.phone = phone
                    user.is_active = ad_enabled
                    user.save()

                    mapping.distinguished_name = dn
                    mapping.sam_account_name = sam
                    mapping.user_principal_name = upn
                    mapping.ad_enabled = ad_enabled
                    mapping.ad_locked = ad_locked
                    mapping.sync_status = 'SYNCED'
                    mapping.last_sync_at = timezone.now()
                    mapping.sync_error_message = ''
                    mapping.save()

                    if not ad_enabled:
                        sync_log.users_disabled += 1
                    else:
                        sync_log.users_updated += 1
                else:
                    # 신규 사용자 생성
                    user, created = User.objects.get_or_create(
                        username=sam,
                        defaults={
                            'name': display_name,
                            'email': mail,
                            'phone': phone,
                            'is_active': ad_enabled,
                        },
                    )

                    ADUserMapping.objects.create(
                        user=user,
                        domain=self.domain,
                        distinguished_name=dn,
                        sam_account_name=sam,
                        user_principal_name=upn,
                        object_guid=guid,
                        ad_enabled=ad_enabled,
                        ad_locked=ad_locked,
                        sync_status='SYNCED',
                        last_sync_at=timezone.now(),
                    )
                    sync_log.users_created += 1

                # 그룹 멤버십 동기화
                member_of = getattr(entry, 'memberOf', [])
                if member_of:
                    mapping = ADUserMapping.objects.get(object_guid=guid)
                    ad_groups = ADGroup.objects.filter(
                        distinguished_name__in=[str(g) for g in member_of],
                    )
                    mapping.ad_groups.set(ad_groups)

                    # 그룹 정책 적용
                    self._apply_group_policies(mapping, ad_groups)

            except (OSError, ConnectionError, ValueError) as e:
                sync_log.errors_count += 1
                sync_log.error_details += f'\n{sam}: {str(e)}'
                logger.warning('사용자 동기화 오류 (%s): %s', sam, str(e))

    def _apply_group_policies(self, mapping, ad_groups):
        """그룹 정책 기반 ERP 권한 자동 적용"""
        from .models import ADGroupPolicy

        policies = ADGroupPolicy.objects.filter(
            domain=self.domain,
            ad_group__in=ad_groups,
            is_active=True,
        ).order_by('priority')

        user = mapping.user

        for policy in policies:
            if policy.action == 'ASSIGN_ROLE':
                if policy.action_value in ('admin', 'manager', 'staff'):
                    user.role = policy.action_value
                    user.save(update_fields=['role'])
            elif policy.action == 'ASSIGN_DEPARTMENT':
                try:
                    from apps.hr.models import EmployeeProfile
                    profile = EmployeeProfile.objects.filter(user=user).first()
                    if profile:
                        from apps.hr.models import Department
                        dept = Department.objects.filter(
                            pk=int(policy.action_value),
                        ).first()
                        if dept:
                            profile.department = dept
                            profile.save(update_fields=['department', 'updated_at'])
                except (ValueError, TypeError):
                    pass
