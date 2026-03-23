from .base import *  # noqa: F401, F403
import logging

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

# Content Security Policy (django-csp v4 format)
# NOTE: 모든 프론트엔드 라이브러리가 로컬 정적 파일로 전환됨 (static/vendor/).
# 외부 CDN 도메인 불필요. unsafe-inline은 인라인 스크립트/스타일에 여전히 필요.
# 장기적으로 nonce 기반 CSP로 전환 권장.
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "script-src": ["'self'", "'unsafe-inline'"],
        "style-src": ["'self'", "'unsafe-inline'"],
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
SESSION_COOKIE_AGE = 28800  # 8시간
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

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
