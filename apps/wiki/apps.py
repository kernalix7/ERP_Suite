from django.apps import AppConfig


class WikiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.wiki'
    verbose_name = '지식베이스/위키'

    def ready(self):
        import apps.wiki.signals  # noqa: F401
