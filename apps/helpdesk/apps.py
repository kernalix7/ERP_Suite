from django.apps import AppConfig


class HelpdeskConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.helpdesk'
    verbose_name = '헬프데스크'

    def ready(self):
        import apps.helpdesk.signals  # noqa: F401
