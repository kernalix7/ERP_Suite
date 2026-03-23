from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', '.app.github.dev', '.preview.app.github.dev']

# Codespace HTTPS 프록시 대응
CSRF_TRUSTED_ORIGINS = [
    'https://*.app.github.dev',
    'https://*.preview.app.github.dev',
    'http://localhost:8000',
    'https://localhost:8000',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'local' / 'db_prod.sqlite3',  # noqa: F405
    }
}

# Disable whitenoise compression in dev
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

# Relaxed API throttling in dev (not fully disabled)
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '200/min',
        'user': '600/min',
    },
}

# ERP 업무 설정
PO_APPROVAL_REQUIRED = False  # True로 변경 시 발주 확정 전 결재 필수

# 테스트 성능 최적화
import sys
if 'test' in sys.argv:
    PASSWORD_HASHERS = [
        'django.contrib.auth.hashers.MD5PasswordHasher',
    ]
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': True,
        'handlers': {'null': {'class': 'logging.NullHandler'}},
        'root': {'handlers': ['null']},
    }
