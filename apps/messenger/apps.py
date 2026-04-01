from django.apps import AppConfig


class MessengerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.messenger'
    verbose_name = '사내 메신저'

    def ready(self):
        pass
