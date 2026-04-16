"""Signal utilities for the module system.

Provides ``@module_signal_handler(module_id)`` — a decorator for Django
signal handlers that skips execution when the referenced module is disabled.
"""
import logging
from functools import wraps

logger = logging.getLogger(__name__)


def module_signal_handler(module_id):
    """Decorator: skip signal handler execution when module is disabled.

    Usage::

        from apps.module_manager.signal_utils import module_signal_handler

        @receiver(post_save, sender=MyModel)
        @module_signal_handler('lms')
        def handle_my_model_save(sender, instance, **kwargs):
            ...

    When the ``lms`` module is disabled in InstalledModule, this handler
    will silently return ``None`` instead of running. This prevents
    disabled module logic from affecting the system.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from .url_utils import is_module_enabled
            if not is_module_enabled(module_id):
                logger.debug(
                    'Signal handler %s skipped: module "%s" is disabled.',
                    func.__qualname__, module_id,
                )
                return None
            return func(*args, **kwargs)
        # Tag for introspection / testing
        wrapper._module_id = module_id
        wrapper._is_module_gated = True
        return wrapper
    return decorator
