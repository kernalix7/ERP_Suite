from django.apps import AppConfig


class BoardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.board'
    verbose_name = '게시판'

    def ready(self):
        pass
