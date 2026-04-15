from django.apps import AppConfig


class WmsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.wms'
    verbose_name = '창고관리(WMS)'

    def ready(self):
        import apps.wms.signals  # noqa: F401
