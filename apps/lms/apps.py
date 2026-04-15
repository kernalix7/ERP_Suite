from django.apps import AppConfig


class LmsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.lms'
    verbose_name = '학습관리'

    def ready(self):
        import apps.lms.signals  # noqa: F401
