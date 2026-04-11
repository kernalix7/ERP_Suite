from django.apps import AppConfig


class ModuleManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.module_manager'
    verbose_name = '모듈 관리'
