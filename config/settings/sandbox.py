"""샌드박스 환경 — 시드(데모) 데이터 포함 (테스트/학습용, 포트 8001)"""
from .development import *  # noqa: F401, F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'local' / 'db_sandbox.sqlite3',  # noqa: F405
    }
}

# 동일 도메인(localhost)에서 세션 쿠키 충돌 방지
SESSION_COOKIE_NAME = 'sessionid_sandbox'
CSRF_COOKIE_NAME = 'csrftoken_sandbox'
