"""Country 마스터 admin — KR 단일 행 보호."""
from django.contrib import admin

from .models import Country


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = (
        'code', 'name', 'currency_code', 'locale',
        'is_default', 'is_supported', 'is_active',
    )
    list_filter = ('is_default', 'is_supported', 'is_active')
    search_fields = ('code', 'name', 'currency_code')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('code',)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.code == 'KR':
            return False
        return super().has_delete_permission(request, obj)
