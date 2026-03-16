from django.apps import AppConfig


class PurchaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.purchase'
    verbose_name = '구매관리'

    def ready(self):
        import apps.purchase.signals  # noqa: F401
