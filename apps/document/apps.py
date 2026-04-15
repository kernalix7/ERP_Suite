from django.apps import AppConfig


class DocumentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.document'
    verbose_name = '전자문서/계약관리'

    def ready(self):
        import apps.document.signals  # noqa: F401
