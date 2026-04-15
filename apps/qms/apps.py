from django.apps import AppConfig


class QmsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.qms'
    verbose_name = '품질관리(QMS)'

    def ready(self):
        import apps.qms.signals  # noqa: F401
