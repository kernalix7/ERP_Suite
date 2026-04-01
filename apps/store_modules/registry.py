import logging

logger = logging.getLogger(__name__)


class ModuleRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._modules = {}
        return cls._instance

    def register(self, module_class):
        module_id = module_class.module_id
        if not module_id:
            raise ValueError(f'{module_class.__name__}.module_id가 비어있습니다.')
        if module_id in self._modules:
            logger.warning('스토어 모듈 중복 등록: %s', module_id)
        self._modules[module_id] = module_class
        logger.info('스토어 모듈 등록: %s (%s)', module_id, module_class.module_name)

    def get(self, module_id: str):
        return self._modules.get(module_id)

    def get_instance(self, module_id: str):
        cls = self.get(module_id)
        return cls() if cls else None

    def all(self) -> dict:
        return dict(self._modules)

    def choices(self) -> list[tuple[str, str]]:
        result = [('', '---------')]
        result.extend(
            (mid, cls.module_name)
            for mid, cls in sorted(self._modules.items())
        )
        return result


registry = ModuleRegistry()
