from django.apps import AppConfig


class ApprovalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.approval'
    verbose_name = '결재관리'

    def ready(self):
        import apps.approval.signals  # noqa: F401
