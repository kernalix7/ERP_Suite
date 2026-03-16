import logging
import time

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('access')


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

        logger.info(
            '%s %s %s %s %dms',
            request.user.username,
            request.method,
            request.path,
            response.status_code,
            duration,
        )

        return response
