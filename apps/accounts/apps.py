from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    verbose_name = '사용자관리'

    def ready(self):
        import apps.accounts.permission_signals  # noqa: F401
