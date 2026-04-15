from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    User, ModulePermission, PermissionGroup, PermissionGroupPermission,
    PermissionGroupMembership, UserPermission, TOTPDevice,
    PasswordHistory, IPWhitelist, UserSession,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'name', 'role', 'phone', 'is_active')
    list_filter = ('role', 'is_active')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('추가 정보', {'fields': ('name', 'phone', 'role')}),
    )


@admin.register(ModulePermission)
class ModulePermissionAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'module', 'action', 'is_active', 'created_at']
    list_filter = ['is_active', 'module', 'action']
    search_fields = ['codename', 'description']


@admin.register(PermissionGroup)
class PermissionGroupAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'priority', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(PermissionGroupPermission)
class PermissionGroupPermissionAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['group__name', 'permission__codename']


@admin.register(PermissionGroupMembership)
class PermissionGroupMembershipAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['user__username', 'group__name']


@admin.register(UserPermission)
class UserPermissionAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'grant', 'is_active', 'created_at']
    list_filter = ['is_active', 'grant']
    search_fields = ['user__username', 'permission__codename']


@admin.register(TOTPDevice)
class TOTPDeviceAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'is_verified', 'is_active', 'created_at']
    list_filter = ['is_active', 'is_verified']
    search_fields = ['user__username']


@admin.register(PasswordHistory)
class PasswordHistoryAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['user__username']


@admin.register(IPWhitelist)
class IPWhitelistAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'scope', 'is_active', 'created_at']
    list_filter = ['is_active', 'scope']
    search_fields = ['ip_address', 'description']


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'ip_address', 'is_active', 'last_activity']
    list_filter = ['is_active']
    search_fields = ['user__username', 'ip_address']
