from django.apps import AppConfig


class SalesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sales'
    verbose_name = '판매관리'

    def ready(self):
        import apps.sales.signals  # noqa: F401
