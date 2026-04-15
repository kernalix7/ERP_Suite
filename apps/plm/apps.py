from django.apps import AppConfig


class PlmConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.plm'
    verbose_name = '제품수명관리(PLM)'

    def ready(self):
        import apps.plm.signals  # noqa: F401
