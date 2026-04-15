from django.apps import AppConfig


class CmmsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.cmms'
    verbose_name = '설비보전(CMMS)'

    def ready(self):
        import apps.cmms.signals  # noqa: F401
