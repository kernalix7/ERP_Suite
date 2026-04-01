from django.apps import AppConfig


class ServiceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.service'
    verbose_name = 'AS관리'

    def ready(self):
        import apps.service.signals  # noqa: F401
