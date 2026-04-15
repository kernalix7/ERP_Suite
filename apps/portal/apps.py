from django.apps import AppConfig


class PortalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.portal'
    verbose_name = '고객/공급처 포털'

    def ready(self):
        import apps.portal.signals  # noqa: F401
