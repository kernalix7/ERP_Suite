import logging
import time

logger = logging.getLogger(__name__)

# TTL for the module-enabled cache (seconds). Short enough that toggle
# effects propagate quickly, long enough to avoid per-request DB hits.
_CACHE_TTL = 2


class ModuleRegistry:
    _instance = None
    _modules = {}

    def __init__(self):
        self._enabled_cache = {}   # module_id → (is_enabled, timestamp)

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
        """Check if module is enabled, with short TTL cache.

        Returns False for nonexistent modules. Seed migration
        (0003_seed_independent_modules) creates all known modules
        with is_enabled=True, preserving backward compatibility.
        """
        now = time.monotonic()
        cached = self._enabled_cache.get(module_id)
        if cached is not None:
            value, ts = cached
            if now - ts < _CACHE_TTL:
                return value

        try:
            from .models import InstalledModule
            result = InstalledModule.objects.filter(
                module_id=module_id, is_enabled=True, is_active=True,
            ).exists()
        except Exception:
            # DB not ready (migrations running)
            result = True

        self._enabled_cache[module_id] = (result, now)
        return result

    def invalidate_cache(self, module_id=None):
        """Clear the enabled-status cache.

        Called after module toggle so changes take effect immediately.
        If ``module_id`` is None, the entire cache is cleared.
        """
        if module_id is None:
            self._enabled_cache.clear()
        else:
            self._enabled_cache.pop(module_id, None)


module_registry = ModuleRegistry.instance()
