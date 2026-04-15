from django.apps import AppConfig


class ProjectConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.project'
    verbose_name = '프로젝트관리'

    def ready(self):
        import apps.project.signals  # noqa: F401
