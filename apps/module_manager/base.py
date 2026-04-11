from abc import ABC, abstractmethod


class BaseFeatureModule(ABC):
    module_id: str
    name: str
    category: str
    country_code: str = ''
    version: str = '1.0.0'
    dependencies: list = []
    icon: str = ''
    description: str = ''

    @abstractmethod
    def get_urls(self):
        """Return URL patterns for this module."""
        return []

    @abstractmethod
    def get_sidebar_items(self):
        """Return sidebar menu items.

        Returns:
            list[dict]: [{'label': str, 'url_name': str, 'icon': str, 'parent': str}]
        """
        return []

    def get_settings_schema(self):
        """Return JSON schema for module settings."""
        return {}

    def on_enable(self):
        """Called when module is enabled."""
        pass

    def on_disable(self):
        """Called when module is disabled."""
        pass
