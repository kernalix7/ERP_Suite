"""IP restriction and concurrent session middleware."""
import logging

from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore
from django.http import HttpResponseForbidden
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from apps.accounts.security_middleware import _get_client_ip

logger = logging.getLogger('django.security')

# Re-export for backward compatibility
get_client_ip = _get_client_ip

__all__ = ['get_client_ip', 'IPRestrictionMiddleware', 'ConcurrentSessionMiddleware']


class IPRestrictionMiddleware(MiddlewareMixin):
    """IP 제한 미들웨어 — IPWhitelist 기반 접근 제어.

    - 화이트리스트가 비어있으면 모든 IP 허용 (제한 비활성화)
    - 슈퍼유저는 항상 허용
    - ALL scope: 모든 경로 제한
    - ADMIN scope: /admin/ 경로만 제한
    - AUDIT scope: /accounts/audit/ 경로만 제한
    """

    EXEMPT_PATHS = (
        '/accounts/login/',
        '/accounts/logout/',
        '/static/',
        '/media/',
        '/metrics',
        '/api/',
    )

    def process_request(self, request):
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return None

        if any(request.path.startswith(p) for p in self.EXEMPT_PATHS):
            return None

        if request.user.is_superuser:
            return None

        from apps.accounts.models import IPWhitelist

        active_entries = IPWhitelist.objects.filter(is_active=True)
        if not active_entries.exists():
            return None

        client_ip = _get_client_ip(request)
        path = request.path

        # Check each scope
        for scope, path_prefix in [('ALL', ''), ('ADMIN', '/admin/'), ('AUDIT', '/accounts/audit/')]:
            scope_entries = active_entries.filter(scope=scope)
            if not scope_entries.exists():
                continue

            if scope == 'ALL' or path.startswith(path_prefix):
                allowed_ips = set(scope_entries.values_list('ip_address', flat=True))
                if client_ip not in allowed_ips:
                    logger.warning(
                        'IP restriction: %s blocked for %s (scope=%s)',
                        client_ip, path, scope,
                    )
                    return HttpResponseForbidden('접근이 제한된 IP입니다.')

        return None


class ConcurrentSessionMiddleware(MiddlewareMixin):
    """동시 세션 제한 미들웨어 — 최대 세션 수 초과 시 오래된 세션 비활성화."""

    def process_request(self, request):
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return None

        if not hasattr(request, 'session') or not request.session.session_key:
            return None

        from apps.accounts.models import UserSession

        session_key = request.session.session_key

        # Update or create current session record
        user_session, created = UserSession.objects.update_or_create(
            session_key=session_key,
            defaults={
                'user': request.user,
                'ip_address': _get_client_ip(request),
                'last_activity': timezone.now(),
                'is_active': True,
            },
        )

        # Enforce max concurrent sessions
        max_sessions = getattr(settings, 'MAX_CONCURRENT_SESSIONS', 3)
        active_sessions = (
            UserSession.objects
            .filter(user=request.user, is_active=True)
            .order_by('-last_activity')
        )

        if active_sessions.count() > max_sessions:
            excess = active_sessions[max_sessions:]
            for old_session in excess:
                old_session.is_active = False
                old_session.save(update_fields=['is_active', 'updated_at'])
                # Delete the Django session too
                try:
                    SessionStore(session_key=old_session.session_key).delete()
                except Exception:
                    pass

        return None
