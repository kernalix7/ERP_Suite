"""베타 환경 — AI 임포트 데이터 확인용 (포트 8001)"""
from .development import *  # noqa: F401, F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'local' / 'db_beta.sqlite3',  # noqa: F405
    }
}

# 동일 도메인(localhost)에서 세션 쿠키 충돌 방지
SESSION_COOKIE_NAME = 'sessionid_beta'
CSRF_COOKIE_NAME = 'csrftoken_beta'
