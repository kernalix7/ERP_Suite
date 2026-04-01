import warnings

from .base import *  # noqa: F401, F403

DEBUG = True

# Dev/test 환경: FIELD_ENCRYPTION_KEY 미설정 시 고정 키 자동 할당 + 경고
if not FIELD_ENCRYPTION_KEY:  # noqa: F405
    FIELD_ENCRYPTION_KEY = 'miu9vt1XwBwIVqH8hacdPE7lKwQsMhYGMyQ7jF_gV6c='  # noqa: F811
    warnings.warn(
        'FIELD_ENCRYPTION_KEY가 설정되지 않아 개발용 기본 키를 사용합니다. '
        '프로덕션에서는 반드시 고유 키를 설정하세요.',
        stacklevel=1,
    )

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
