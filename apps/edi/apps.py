from django.apps import AppConfig


class EdiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.edi'
    verbose_name = 'EDI (전자문서교환)'

    def ready(self):
        import apps.edi.signals  # noqa: F401
