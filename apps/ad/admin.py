from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    ADDomain, ADOrganizationalUnit, ADGroup,
    ADUserMapping, ADSyncLog, ADGroupPolicy,
)


@admin.register(ADDomain)
class ADDomainAdmin(SimpleHistoryAdmin):
    list_display = ['name', 'domain', 'sync_enabled', 'last_sync_at', 'is_active']
    list_filter = ['sync_enabled', 'use_ssl', 'is_active']
    search_fields = ['name', 'domain']


@admin.register(ADOrganizationalUnit)
class ADOrganizationalUnitAdmin(SimpleHistoryAdmin):
    list_display = ['name', 'domain', 'parent', 'mapped_department']
    list_filter = ['domain']
    search_fields = ['name', 'distinguished_name']


@admin.register(ADGroup)
class ADGroupAdmin(SimpleHistoryAdmin):
    list_display = ['sam_account_name', 'display_name', 'group_type', 'group_scope', 'mapped_role']
    list_filter = ['domain', 'group_type', 'group_scope']
    search_fields = ['sam_account_name', 'display_name']


@admin.register(ADUserMapping)
class ADUserMappingAdmin(SimpleHistoryAdmin):
    list_display = ['sam_account_name', 'user', 'domain', 'sync_status', 'ad_enabled', 'last_sync_at']
    list_filter = ['domain', 'sync_status', 'ad_enabled', 'ad_locked']
    search_fields = ['sam_account_name', 'user_principal_name', 'user__username']
    raw_id_fields = ['user']


@admin.register(ADSyncLog)
class ADSyncLogAdmin(SimpleHistoryAdmin):
    list_display = ['domain', 'sync_type', 'status', 'started_at', 'total_processed', 'errors_count']
    list_filter = ['domain', 'sync_type', 'status']
    readonly_fields = ['started_at']


@admin.register(ADGroupPolicy)
class ADGroupPolicyAdmin(SimpleHistoryAdmin):
    list_display = ['name', 'ad_group', 'action', 'action_value', 'priority']
    list_filter = ['domain', 'action']
    search_fields = ['name']
