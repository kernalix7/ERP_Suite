from django.contrib import admin

from .models import InstalledModule


@admin.register(InstalledModule)
class InstalledModuleAdmin(admin.ModelAdmin):
    list_display = ['module_id', 'name', 'category', 'country_code', 'is_enabled', 'version', 'sort_order']
    list_filter = ['category', 'is_enabled', 'country_code']
    search_fields = ['module_id', 'name']
    list_editable = ['is_enabled', 'sort_order']
