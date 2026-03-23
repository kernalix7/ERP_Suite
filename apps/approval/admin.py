from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from apps.approval.models import ApprovalRequest, ApprovalStep


class ApprovalStepInline(admin.TabularInline):
    model = ApprovalStep
    extra = 1


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(SimpleHistoryAdmin):
    list_display = (
        'request_number', 'category', 'title',
        'requester', 'approver', 'status', 'current_step',
    )
    list_filter = ('status', 'category')
    inlines = [ApprovalStepInline]


@admin.register(ApprovalStep)
class ApprovalStepAdmin(SimpleHistoryAdmin):
    list_display = (
        'request', 'step_order', 'approver', 'status', 'acted_at',
    )
    list_filter = ('status',)
