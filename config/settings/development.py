from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ['*']

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
        'NAME': BASE_DIR / 'local' / 'db.sqlite3',  # noqa: F405
    }
}

# Disable whitenoise compression in dev
STORAGES = {
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

# Disable API throttling in dev/test
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {},
}
