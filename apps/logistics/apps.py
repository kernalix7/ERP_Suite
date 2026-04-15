from django.apps import AppConfig


class LogisticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.logistics'
    verbose_name = '물류/배송관리'

    def ready(self):
        import apps.logistics.signals  # noqa: F401
