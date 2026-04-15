"""Security middleware: 2FA enforcement + password expiry.

IP restriction and concurrent session middleware are in apps.accounts.middleware.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('django.security')


class TwoFactorMiddleware(MiddlewareMixin):
    """2FA 미들웨어 — admin/manager 역할에 TOTP 인증 강제.

    세션에 '2fa_verified' 플래그가 없으면 2FA 검증 페이지로 리다이렉트.
    """

    EXEMPT_PATHS = (
        '/accounts/login/',
        '/accounts/logout/',
        '/accounts/two-factor/',
        '/accounts/password/',
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

        # Only enforce for admin/manager roles
        role = getattr(request.user, 'role', 'staff')
        if role not in ('admin', 'manager'):
            return None

        # Check if user has 2FA enabled and verified
        try:
            device = request.user.totp_device
            if not device.is_verified or not device.is_active:
                return None
        except Exception:
            # No TOTP device — not enforced yet
            return None

        # Check session flag
        if request.session.get('2fa_verified'):
            return None

        return redirect('accounts:two_factor_verify')


class PasswordExpiryMiddleware(MiddlewareMixin):
    """비밀번호 만료 미들웨어 — 90일 초과 시 비밀번호 변경 강제."""

    EXEMPT_PATHS = (
        '/accounts/login/',
        '/accounts/logout/',
        '/accounts/password/change/',
        '/accounts/password/expired/',
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

        expiry_days = getattr(settings, 'PASSWORD_EXPIRY_DAYS', 90)
        from apps.accounts.models import PasswordHistory
        last_change = (
            PasswordHistory.objects
            .filter(user=request.user, is_active=True)
            .order_by('-created_at')
            .values_list('created_at', flat=True)
            .first()
        )
        if last_change is None:
            # No password history — use account creation date
            last_change = request.user.date_joined

        if timezone.now() - last_change > timedelta(days=expiry_days):
            return redirect('accounts:password_expired')

        return None


def _get_client_ip(request):
    """클라이언트 IP 주소 추출 — X-Forwarded-For 우선, 없으면 REMOTE_ADDR."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')
