from django.apps import AppConfig


class ForecastConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.forecast'
    verbose_name = '수요예측/S&OP'

    def ready(self):
        import apps.forecast.signals  # noqa: F401
