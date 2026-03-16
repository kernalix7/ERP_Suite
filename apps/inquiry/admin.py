from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import InquiryChannel, Inquiry, InquiryReply, ReplyTemplate


class InquiryReplyInline(admin.TabularInline):
    model = InquiryReply
    extra = 0
    readonly_fields = ('replied_at',)


@admin.register(InquiryChannel)
class InquiryChannelAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'icon', 'is_active')


@admin.register(Inquiry)
class InquiryAdmin(SimpleHistoryAdmin):
    list_display = ('subject', 'channel', 'customer_name', 'status', 'priority', 'received_date', 'assigned_to')
    list_filter = ('status', 'priority', 'channel', 'received_date')
    search_fields = ('subject', 'customer_name', 'content')
    inlines = [InquiryReplyInline]


@admin.register(InquiryReply)
class InquiryReplyAdmin(SimpleHistoryAdmin):
    list_display = ('inquiry', 'replied_by', 'is_llm_generated', 'replied_at')
    list_filter = ('is_llm_generated', 'replied_at')


@admin.register(ReplyTemplate)
class ReplyTemplateAdmin(SimpleHistoryAdmin):
    list_display = ('category', 'title', 'use_count', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('title', 'content')
