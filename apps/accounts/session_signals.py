"""Session signals: track UserSession on login/logout."""
import logging

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

logger = logging.getLogger('django.security')


def _get_client_ip(request):
    """클라이언트 IP 추출."""
    if request is None:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


@receiver(user_logged_in)
def create_user_session(sender, request, user, **kwargs):
    """로그인 시 UserSession 레코드 생성."""
    from apps.accounts.models import UserSession

    if request is None or not hasattr(request, 'session'):
        return

    session_key = request.session.session_key
    if not session_key:
        request.session.save()
        session_key = request.session.session_key

    ip_address = _get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

    UserSession.objects.update_or_create(
        session_key=session_key,
        defaults={
            'user': user,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'is_active': True,
        },
    )

    logger.info('Session created for %s from %s', user.username, ip_address)

    # Enforce max concurrent sessions
    from django.conf import settings
    from django.contrib.sessions.backends.db import SessionStore

    max_sessions = getattr(settings, 'MAX_CONCURRENT_SESSIONS', 3)
    active_sessions = (
        UserSession.objects
        .filter(user=user, is_active=True)
        .order_by('-last_activity')
    )

    if active_sessions.count() > max_sessions:
        excess = active_sessions[max_sessions:]
        for old_session in excess:
            old_session.is_active = False
            old_session.save(update_fields=['is_active', 'updated_at'])
            try:
                SessionStore(session_key=old_session.session_key).delete()
            except Exception:
                pass


@receiver(user_logged_out)
def deactivate_user_session(sender, request, user, **kwargs):
    """로그아웃 시 UserSession 비활성화."""
    from apps.accounts.models import UserSession

    if request is None or not hasattr(request, 'session'):
        return

    session_key = request.session.session_key
    if session_key:
        UserSession.objects.filter(session_key=session_key).update(is_active=False)
        logger.info('Session deactivated for %s', user.username if user else 'unknown')
