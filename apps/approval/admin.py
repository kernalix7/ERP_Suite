from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from apps.approval.models import (
    ApprovalDelegation,
    ApprovalLineTemplate,
    ApprovalRequest,
    ApprovalStep,
)


class ApprovalStepInline(admin.TabularInline):
    model = ApprovalStep
    fields = (
        'step_order', 'approver', 'parallel_mode',
        'delegated_from', 'status', 'acted_at',
    )
    readonly_fields = ('acted_at',)
    extra = 1


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(SimpleHistoryAdmin):
    list_display = (
        'request_number', 'category', 'title',
        'requester', 'approver', 'approval_type',
        'status', 'current_step',
    )
    list_filter = ('status', 'category', 'approval_type')
    search_fields = ('request_number', 'title')
    inlines = [ApprovalStepInline]


@admin.register(ApprovalStep)
class ApprovalStepAdmin(SimpleHistoryAdmin):
    list_display = (
        'request', 'step_order', 'approver', 'parallel_mode',
        'delegated_from', 'status', 'acted_at',
    )
    list_filter = ('status', 'parallel_mode')
    search_fields = ('request__request_number',)


@admin.register(ApprovalLineTemplate)
class ApprovalLineTemplateAdmin(SimpleHistoryAdmin):
    list_display = (
        'name', 'is_default', 'auto_apply', 'priority',
        'step_count', 'is_active', 'updated_at',
    )
    list_filter = ('is_default', 'auto_apply', 'is_active')
    search_fields = ('name', 'description')
    ordering = ('-priority', '-is_default', 'name')
    fieldsets = (
        (None, {'fields': ('name', 'description', 'is_active')}),
        ('자동적용', {'fields': ('auto_apply', 'is_default', 'priority', 'condition')}),
        ('결재 단계', {'fields': ('steps',)}),
    )

    @admin.display(description='단계 수')
    def step_count(self, obj):
        return len(obj.steps) if isinstance(obj.steps, list) else 0


@admin.register(ApprovalDelegation)
class ApprovalDelegationAdmin(SimpleHistoryAdmin):
    list_display = (
        'delegator', 'delegate', 'start_date', 'end_date',
        'is_currently_active', 'is_active',
    )
    list_filter = ('is_active', 'start_date', 'end_date')
    search_fields = (
        'delegator__username', 'delegator__last_name', 'delegator__first_name',
        'delegate__username', 'delegate__last_name', 'delegate__first_name',
        'reason',
    )
    date_hierarchy = 'start_date'

    @admin.display(description='현재 유효', boolean=True)
    def is_currently_active(self, obj):
        from django.utils import timezone
        today = timezone.localdate()
        return bool(
            obj.is_active and obj.start_date <= today <= obj.end_date
        )
