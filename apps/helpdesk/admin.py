from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    EscalationRule,
    SLA,
    SLABreach,
    Ticket,
    TicketAttachment,
    TicketCategory,
    TicketComment,
)


class TicketCommentInline(admin.TabularInline):
    model = TicketComment
    extra = 0


class TicketAttachmentInline(admin.TabularInline):
    model = TicketAttachment
    extra = 0


@admin.register(SLA)
class SLAAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'response_time_hours', 'resolution_time_hours',
                    'escalation_time_hours', 'is_active')
    list_filter = ('is_active',)


@admin.register(TicketCategory)
class TicketCategoryAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'parent', 'default_priority', 'default_sla', 'is_active')
    list_filter = ('default_priority', 'is_active')
    search_fields = ('name',)


@admin.register(Ticket)
class TicketAdmin(SimpleHistoryAdmin):
    list_display = ('ticket_number', 'title', 'category', 'priority', 'status',
                    'reporter', 'assigned_to', 'sla_breached', 'created_at')
    list_filter = ('status', 'priority', 'channel', 'sla_breached')
    search_fields = ('ticket_number', 'title', 'reporter__username')
    inlines = [TicketCommentInline, TicketAttachmentInline]


@admin.register(TicketComment)
class TicketCommentAdmin(SimpleHistoryAdmin):
    list_display = ('ticket', 'author', 'is_internal', 'created_at')
    list_filter = ('is_internal',)


@admin.register(TicketAttachment)
class TicketAttachmentAdmin(SimpleHistoryAdmin):
    list_display = ('ticket', 'file', 'uploaded_by', 'created_at')


@admin.register(SLABreach)
class SLABreachAdmin(SimpleHistoryAdmin):
    list_display = ('ticket', 'sla', 'breach_type', 'breached_at', 'notified')
    list_filter = ('breach_type', 'notified')
    search_fields = ('ticket__ticket_number',)


@admin.register(EscalationRule)
class EscalationRuleAdmin(SimpleHistoryAdmin):
    list_display = ('category', 'condition_type', 'escalate_to', 'notify_method')
    list_filter = ('condition_type', 'notify_method')
