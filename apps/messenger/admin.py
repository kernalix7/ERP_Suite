from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import ChatRoom, ChatParticipant, Message


class ChatParticipantInline(admin.TabularInline):
    model = ChatParticipant
    extra = 0


@admin.register(ChatRoom)
class ChatRoomAdmin(SimpleHistoryAdmin):
    list_display = ('id', 'name', 'room_type', 'created_at', 'is_active')
    list_filter = ('room_type', 'is_active')
    inlines = [ChatParticipantInline]


@admin.register(Message)
class MessageAdmin(SimpleHistoryAdmin):
    list_display = ('id', 'room', 'sender', 'content_preview', 'message_type', 'sent_at')
    list_filter = ('message_type', 'sent_at')
    search_fields = ('content', 'sender__name', 'sender__username')

    def content_preview(self, obj):
        return obj.content[:50]
    content_preview.short_description = '내용'
