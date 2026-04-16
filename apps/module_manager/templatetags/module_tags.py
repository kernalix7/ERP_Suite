from django import template

register = template.Library()


@register.simple_tag
def module_enabled(module_id):
    """Check if a module is enabled (uses TTL-cached registry).

    Usage: {% module_enabled 'lms' as lms_enabled %}
           {% if lms_enabled %}...{% endif %}
    """
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
