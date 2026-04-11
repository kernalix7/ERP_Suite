import logging

logger = logging.getLogger(__name__)


class ModuleRegistry:
    _instance = None
    _modules = {}

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, module_class):
        """Decorator to register a module."""
        module = module_class()
        self._modules[module.module_id] = module
        logger.info('모듈 등록: %s (%s)', module.module_id, module.name)
        return module_class

    def get_module(self, module_id):
        return self._modules.get(module_id)

    def get_all(self):
        return dict(self._modules)

    def get_enabled(self):
        from .models import InstalledModule
        enabled_ids = set(
            InstalledModule.objects.filter(
                is_enabled=True, is_active=True,
            ).values_list('module_id', flat=True)
        )
        return {k: v for k, v in self._modules.items() if k in enabled_ids}

    def is_enabled(self, module_id):
        from .models import InstalledModule
        return InstalledModule.objects.filter(
            module_id=module_id, is_enabled=True, is_active=True,
        ).exists()


module_registry = ModuleRegistry.instance()
