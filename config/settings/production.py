from .base import *  # noqa: F401, F403

DEBUG = False

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost'])  # noqa: F405

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
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'", "https://cdn.tailwindcss.com", "https://cdn.jsdelivr.net", "https://unpkg.com"],
        "style-src": ["'self'", "'unsafe-inline'", "https://cdn.tailwindcss.com", "https://cdn.jsdelivr.net", "https://fonts.googleapis.com"],
        "font-src": ["'self'", "https://fonts.gstatic.com", "https://cdn.jsdelivr.net"],
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
