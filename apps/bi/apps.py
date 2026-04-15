from django.apps import AppConfig


class BiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.bi'
    verbose_name = 'BI 대시보드'

    def ready(self):
        import apps.bi.signals  # noqa: F401
