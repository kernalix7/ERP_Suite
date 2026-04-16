"""Dynamic URL inclusion helpers for the module system.

Provides ``module_include()`` — a drop-in replacement for Django's
``include()`` that gates all URL access behind module activation status.
When a module is disabled, all its URLs raise Http404.
"""
import logging

from django.http import Http404
from django.urls import include, resolve, Resolver404

logger = logging.getLogger(__name__)

# URL prefix → module_id mapping (used by middleware & template tags)
MODULE_URL_MAP = {
    'lms': 'lms',
    'wiki': 'wiki',
    'project': 'project',
    'visitor': 'visitor',
    'bi': 'bi',
    'rpa': 'rpa',
    'helpdesk': 'helpdesk',
    'portal': 'portal',
    'logistics': 'logistics',
    'edi': 'edi',
    'subscription': 'subscription',
    'document': 'document',
    'expense': 'expense',
    'esg': 'esg',
    'cmms': 'cmms',
    'qms': 'qms',
    'plm': 'plm',
    'forecast': 'forecast',
    'ad': 'ad',
    'advertising': 'advertising',
    'board': 'board',
    'calendar': 'calendar_app',
    'messenger': 'messenger',
}


def is_module_enabled(module_id):
    """Check if module is enabled for URL/view gating.

    Returns True if the module record doesn't exist yet (before seed
    data migration runs), so existing functionality isn't broken.
    Once the seed migration creates records with is_enabled=True,
    this function respects the actual DB state.
    """
    try:
        from .models import InstalledModule
        record = InstalledModule.all_objects.filter(
            module_id=module_id,
        ).values_list('is_enabled', 'is_active').first()
        if record is None:
            # No record yet → allow access (backward compat)
            return True
        is_enabled, is_active = record
        return is_enabled and is_active
    except Exception:
        return True


def module_include(url_module, module_id):
    """Conditional include() that gates URL access by module status.

    Wraps every view function in the included URL conf so that disabled
    modules return Http404. URL *resolution* still works (so ``{% url %}``
    doesn't break at template compile time), but *dispatch* is blocked.

    Usage::

        path('lms/', module_include('apps.lms.urls', 'lms')),
    """
    url_conf = include(url_module)
    urlconf_module, app_ns = url_conf[0], url_conf[1]
    instance_ns = url_conf[2] if len(url_conf) > 2 else app_ns

    # include() returns (module, app_name, namespace) — extract patterns
    if hasattr(urlconf_module, 'urlpatterns'):
        patterns = urlconf_module.urlpatterns
    else:
        patterns = urlconf_module

    def _wrap_patterns(source_patterns, mid):
        """Recursively wrap all view callbacks with a module gate."""
        from django.urls import URLPattern, URLResolver
        wrapped = []
        for pattern in source_patterns:
            if isinstance(pattern, URLPattern):
                original_callback = pattern.callback
                wrapped_callback = _make_gated_view(original_callback, mid)
                new_pattern = URLPattern(
                    pattern.pattern, wrapped_callback,
                    pattern.default_args, pattern.name,
                )
                wrapped.append(new_pattern)
            elif isinstance(pattern, URLResolver):
                new_resolver = URLResolver(
                    pattern.pattern,
                    _wrap_patterns(pattern.url_patterns, mid),
                    pattern.default_kwargs,
                    pattern.app_name,
                    pattern.namespace,
                )
                wrapped.append(new_resolver)
            else:
                wrapped.append(pattern)
        return wrapped

    wrapped_patterns = _wrap_patterns(patterns, module_id)
    return (wrapped_patterns, app_ns, instance_ns)


def _make_gated_view(view_func, module_id):
    """Create a wrapper view that checks module status before dispatch."""
    from functools import wraps

    @wraps(view_func)
    def gated_view(*args, **kwargs):
        if not is_module_enabled(module_id):
            raise Http404(f'Module "{module_id}" is not enabled.')
        return view_func(*args, **kwargs)

    # Preserve class-based view attributes
    if hasattr(view_func, 'view_class'):
        gated_view.view_class = view_func.view_class
    if hasattr(view_func, 'initkwargs'):
        gated_view.initkwargs = view_func.initkwargs

    return gated_view
