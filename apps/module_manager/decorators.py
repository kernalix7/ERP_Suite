from functools import wraps

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404

from .registry import module_registry


class ModuleRequiredMixin(LoginRequiredMixin):
    """Mixin that blocks access if the required module is disabled.

    Usage:
        class MyView(ModuleRequiredMixin, ListView):
            required_module = 'compliance.kr.severance'
    """
    required_module = None

    def dispatch(self, request, *args, **kwargs):
        if self.required_module and not module_registry.is_enabled(self.required_module):
            raise Http404
        return super().dispatch(request, *args, **kwargs)


def module_required(module_id):
    """Decorator for function-based views that blocks access if module is disabled.

    Usage:
        @login_required
        @module_required('compliance.kr.severance')
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not module_registry.is_enabled(module_id):
                raise Http404
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
