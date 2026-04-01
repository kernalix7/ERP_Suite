from django.apps import AppConfig


class AssetConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.asset'
    verbose_name = '고정자산'

    def ready(self):
        import apps.asset.signals  # noqa: F401
