from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import PortalDocument, PortalNotification, PortalUser


@admin.register(PortalUser)
class PortalUserAdmin(SimpleHistoryAdmin):
    list_display = ('user', 'partner', 'portal_type', 'is_verified',
                    'last_portal_login', 'is_active')
    list_filter = ('portal_type', 'is_verified', 'is_active')
    search_fields = ('user__username', 'partner__name')


@admin.register(PortalNotification)
class PortalNotificationAdmin(SimpleHistoryAdmin):
    list_display = ('portal_user', 'title', 'is_read', 'created_at')
    list_filter = ('is_read',)


@admin.register(PortalDocument)
class PortalDocumentAdmin(SimpleHistoryAdmin):
    list_display = ('portal_user', 'document_type', 'title', 'created_at')
    list_filter = ('document_type',)
