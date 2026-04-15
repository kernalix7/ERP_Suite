from django.contrib import admin

from .notification import Notification
from .attachment import Attachment
from .notification_center import (
    NotificationChannel, NotificationTemplate,
    NotificationPreference, NotificationLog, PushSubscription,
)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'noti_type', 'is_read', 'created_at')
    list_filter = ('noti_type', 'is_read')
    search_fields = ('title', 'message')


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'doc_type', 'content_type', 'object_id', 'uploaded_by', 'uploaded_at')
    list_filter = ('doc_type',)
    search_fields = ('original_filename', 'description')


@admin.register(NotificationChannel)
class NotificationChannelAdmin(admin.ModelAdmin):
    list_display = ('name', 'channel_type', 'is_active')
    list_filter = ('channel_type', 'is_active')


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'channel', 'is_active')
    list_filter = ('channel', 'is_active')
    search_fields = ('name', 'code')


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'channel', 'event_type', 'is_enabled')
    list_filter = ('channel', 'event_type', 'is_enabled')


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'channel', 'status', 'subject', 'sent_at', 'created_at')
    list_filter = ('status', 'channel')
    search_fields = ('subject',)


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'endpoint', 'is_active', 'created_at')
    list_filter = ('is_active',)
