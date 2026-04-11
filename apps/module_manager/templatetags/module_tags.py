from django import template

register = template.Library()


@register.simple_tag
def module_enabled(module_id):
    """Check if a module is enabled.

    Usage: {% module_enabled 'core.inventory' as inv_enabled %}
    """
    from apps.module_manager.models import InstalledModule
    return InstalledModule.objects.filter(
        module_id=module_id, is_enabled=True, is_active=True,
    ).exists()


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
