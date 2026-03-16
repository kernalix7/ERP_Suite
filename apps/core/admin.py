from django.contrib import admin

from .notification import Notification
from .attachment import Attachment


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
