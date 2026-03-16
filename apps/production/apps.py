from django.apps import AppConfig


class ProductionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.production'
    verbose_name = '생산관리'

    def ready(self):
        import apps.production.signals  # noqa: F401
