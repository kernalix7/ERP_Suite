from django.apps import AppConfig


class RpaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.rpa'
    verbose_name = 'RPA/자동화'

    def ready(self):
        import apps.rpa.signals  # noqa: F401
