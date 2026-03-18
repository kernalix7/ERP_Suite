from django.apps import AppConfig


class AdConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ad'
    verbose_name = 'Active Directory'

    def ready(self):
        import apps.ad.signals  # noqa: F401
