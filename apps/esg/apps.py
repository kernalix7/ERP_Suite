from django.apps import AppConfig


class EsgConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.esg'
    verbose_name = 'ESG/컴플라이언스'

    def ready(self):
        import apps.esg.signals  # noqa: F401
