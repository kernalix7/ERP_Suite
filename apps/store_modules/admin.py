from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import StoreModuleConfig


@admin.register(StoreModuleConfig)
class StoreModuleConfigAdmin(SimpleHistoryAdmin):
    list_display = ['module_id', 'display_name', 'value_type', 'is_secret', 'is_active']
    list_filter = ['module_id', 'is_secret']
    search_fields = ['module_id', 'key', 'display_name']
