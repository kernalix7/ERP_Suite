from django.apps import AppConfig


class ExpenseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.expense'
    verbose_name = '경비관리'

    def ready(self):
        import apps.expense.signals  # noqa: F401
