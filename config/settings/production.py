from .base import *  # noqa: F401, F403
import logging
import os

from csp.constants import NONCE

DEBUG = False

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')  # noqa: F405 — 필수, 기본값 없음

DATABASES = {
    'default': env.db('DATABASE_URL'),  # noqa: F405
}

# Security headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True

# Content Security Policy (django-csp v4 format — nonce 기반)
# NOTE: 모든 프론트엔드 라이브러리가 로컬 정적 파일로 전환됨 (static/vendor/).
# 외부 CDN 도메인 불필요.
# script-src: unsafe-inline 완전 제거, nonce 기반만 허용.
# style-src: nonce 기반 + unsafe-inline 병행 (인라인 style="" 속성 허용 위해).
#   — CSP3에서 nonce 존재 시 <style> 블록의 unsafe-inline은 무시되므로
#     실질적으로 <style> 블록은 nonce 필수, style="" 속성만 unsafe-inline 적용.
# 모든 인라인 <script>/<style>에 nonce="{{ request.csp_nonce }}" 필수.
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "script-src": ["'self'", NONCE],
        "style-src": ["'self'", NONCE, "'unsafe-inline'"],
        "font-src": ["'self'"],
        "img-src": ["'self'", "data:", "blob:"],
        "connect-src": ["'self'", "wss:"],
        "frame-src": ["'none'"],
        "object-src": ["'none'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
    }
}

# Session
SESSION_COOKIE_AGE = 3600  # 1시간
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
MAX_CONCURRENT_SESSIONS = 3

# Production startup validation
_logger = logging.getLogger('django')

if not FIELD_ENCRYPTION_KEY:  # noqa: F405
    raise ValueError(
        'FIELD_ENCRYPTION_KEY 환경변수가 설정되지 않았습니다. '
        'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" '
        '로 생성하세요.'
    )

if SECRET_KEY.startswith('django-insecure-') or len(SECRET_KEY) < 50:  # noqa: F405
    raise ValueError('프로덕션 SECRET_KEY가 안전하지 않습니다. 50자 이상의 랜덤 값을 사용하세요.')

if not SENTRY_DSN:  # noqa: F405
    _logger.warning('SENTRY_DSN이 설정되지 않았습니다. 프로덕션 에러 모니터링이 비활성화됩니다.')

# ── SIEM / Security Logging ─────────────────────────────────
_security_log_dir = os.path.join(BASE_DIR, 'local', 'logs')  # noqa: F405
os.makedirs(_security_log_dir, exist_ok=True)

LOGGING['formatters']['json'] = {  # noqa: F405
    '()': 'apps.core.logging.JSONFormatter',
}
LOGGING['handlers']['security_file'] = {  # noqa: F405
    'level': 'INFO',
    'class': 'logging.handlers.RotatingFileHandler',
    'filename': os.path.join(_security_log_dir, 'security.log'),
    'maxBytes': 50 * 1024 * 1024,  # 50MB
    'backupCount': 10,
    'formatter': 'json',
}
LOGGING['loggers']['security'] = {  # noqa: F405
    'handlers': ['security_file', 'console'],
    'level': 'INFO',
    'propagate': False,
}
# Route axes (login failures) through security logger as well
LOGGING['loggers']['axes']['handlers'] = ['file', 'security_file']  # noqa: F405
