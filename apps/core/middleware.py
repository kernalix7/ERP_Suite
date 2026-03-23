import logging
import os
import time

from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('access')


class MaintenanceMiddleware(MiddlewareMixin):
    """점검 모드 미들웨어 — MAINTENANCE_MODE_FILE이 존재하면 503 점검 페이지 반환"""

    BYPASS_PREFIXES = (
        '/static/', '/media/', '/metrics', '/admin/',
    )

    def process_request(self, request):
        flag_file = getattr(
            settings, 'MAINTENANCE_MODE_FILE',
            os.path.join(settings.BASE_DIR, 'local', '.maintenance'),
        )
        if not os.path.exists(flag_file):
            return None

        # 관리자 접속은 허용 (superuser 또는 admin 역할)
        if hasattr(request, 'user') and request.user.is_authenticated:
            if request.user.is_superuser or getattr(request.user, 'role', None) == 'admin':
                return None

        if any(request.path.startswith(p) for p in self.BYPASS_PREFIXES):
            return None

        html = render_to_string('maintenance.html')
        return HttpResponse(html, status=503, content_type='text/html')


class AccessLogMiddleware(MiddlewareMixin):
    """사용자 접근 로그 미들웨어 - 인증된 사용자의 페이지 접근 기록"""

    EXCLUDE_PREFIXES = (
        '/static/', '/media/', '/metrics', '/favicon.ico',
        '/ws/', '/__debug__/',
    )

    def process_request(self, request):
        request._access_start = time.monotonic()

    def process_response(self, request, response):
        if any(request.path.startswith(p) for p in self.EXCLUDE_PREFIXES):
            return response

        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return response

        duration = 0
        if hasattr(request, '_access_start'):
            duration = int(
                (time.monotonic() - request._access_start) * 1000
            )

        # Extract client IP (respect X-Forwarded-For from reverse proxy)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            client_ip = x_forwarded_for.split(',')[0].strip()
        else:
            client_ip = request.META.get('REMOTE_ADDR', '')

        logger.info(
            '%s %s %s %s %dms %s',
            request.user.username,
            request.method,
            request.path,
            response.status_code,
            duration,
            client_ip,
        )

        return response
