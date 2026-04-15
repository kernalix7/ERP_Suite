from django.apps import AppConfig


class SubscriptionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.subscription'
    verbose_name = '구독/정기과금'

    def ready(self):
        import apps.subscription.signals  # noqa: F401
