from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def module_enabled(context, module_id):
    """Check if a module is enabled (request-scoped cached).

    Usage: {% module_enabled 'lms' as lms_enabled %}
           {% if lms_enabled %}...{% endif %}
    """
    request = context.get('request')
    if request is not None:
        cache = getattr(request, '_enabled_modules_cache', None)
        if cache is None:
            from apps.module_manager.models import InstalledModule
            cache = set(
                InstalledModule.objects.filter(
                    is_enabled=True, is_active=True,
                ).values_list('module_id', flat=True)
            )
            request._enabled_modules_cache = cache
        return module_id in cache
    from apps.module_manager.registry import module_registry
    return module_registry.is_enabled(module_id)


@register.simple_tag
def get_module_sidebar_items():
    """Get sidebar items from all enabled modules.

    Usage: {% get_module_sidebar_items as sidebar_items %}
    """
    from apps.module_manager.registry import module_registry
    items = []
    for module in module_registry.get_enabled().values():
        items.extend(module.get_sidebar_items())
    return items
