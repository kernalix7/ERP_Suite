from django.apps import AppConfig


class StoreModulesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.store_modules'
    verbose_name = '스토어 모듈'

    def ready(self):
        from django.utils.module_loading import autodiscover_modules
        autodiscover_modules('store_module')
