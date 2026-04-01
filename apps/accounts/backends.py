import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

User = get_user_model()
logger = logging.getLogger(__name__)


class EmailOrEmployeeNumberBackend(ModelBackend):
    """사번(username) 또는 이메일로 로그인 + AD/LDAP 연동

    User.username = 사번 (키값)
    로그인 순서:
    1. 이메일로 조회 (@가 포함된 경우)
    2. 사번(username)으로 조회
    3. AD/LDAP 바인드 시도 (ADDomain 설정 시)
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        identifier = username.strip()

        # 1) 이메일 포함 시 email 필드로 조회
        user = None
        if '@' in identifier:
            try:
                user = User.objects.get(email=identifier)
            except User.DoesNotExist:
                pass

        # 2) username(사번)으로 직접 조회
        if user is None:
            try:
                user = User.objects.get(username=identifier)
            except User.DoesNotExist:
                pass

        # 3) AD/LDAP 인증 시도
        if user is None:
            user = self._try_ldap_auth(identifier, password)
            if user and self.user_can_authenticate(user):
                return user  # LDAP에서 이미 비밀번호 검증됨
            if user:
                return None

        # 로컬 비밀번호 검증
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    @staticmethod
    def _try_ldap_auth(identifier, password):
        """AD/LDAP 바인드 인증 시도"""
        try:
            from apps.ad.models import ADDomain, ADUserMapping
        except ImportError:
            return None

        domains = ADDomain.objects.filter(is_active=True, sync_enabled=True)
        if not domains.exists():
            return None

        try:
            import ldap3
            from ldap3.core.exceptions import LDAPException
        except ImportError:
            logger.warning('ldap3 패키지 미설치')
            return None

        for domain in domains:
            # UPN 형식으로 바인드
            bind_dn = identifier if '@' in identifier else f'{identifier}@{domain.domain}'
            try:
                server = ldap3.Server(
                    domain.ldap_server,
                    use_ssl=domain.use_ssl,
                    get_info=ldap3.NONE,
                    connect_timeout=5,
                )
                conn = ldap3.Connection(
                    server, user=bind_dn, password=password,
                    auto_bind=True, raise_exceptions=True,
                )
                conn.unbind()
            except (LDAPException, OSError):
                continue

            # LDAP 인증 성공 → 매핑된 ERP User 찾기
            sam_name = identifier.split('@')[0] if '@' in identifier else identifier
            try:
                mapping = ADUserMapping.objects.select_related('user').get(
                    domain=domain,
                    sam_account_name__iexact=sam_name,
                    is_active=True,
                )
                return mapping.user
            except ADUserMapping.DoesNotExist:
                logger.info('LDAP 인증 성공, ERP 매핑 없음: %s', sam_name)

        return None
