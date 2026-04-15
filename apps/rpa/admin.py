from django.contrib import admin

from .models import AutomationRule, RuleAction, RuleCondition, AutomationLog, AutomationSchedule


class RuleActionInline(admin.TabularInline):
    model = RuleAction
    extra = 0


class RuleConditionInline(admin.TabularInline):
    model = RuleCondition
    extra = 0


@admin.register(AutomationRule)
class AutomationRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'trigger_type', 'priority', 'owner', 'run_count', 'error_count', 'is_active')
    list_filter = ('trigger_type', 'is_active')
    search_fields = ('name', 'description')
    inlines = [RuleActionInline, RuleConditionInline]


@admin.register(AutomationLog)
class AutomationLogAdmin(admin.ModelAdmin):
    list_display = ('rule', 'status', 'actions_executed', 'duration_ms', 'triggered_at')
    list_filter = ('status',)
    search_fields = ('rule__name',)


@admin.register(RuleAction)
class RuleActionAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'action_type', 'sequence', 'is_active', 'created_at']
    list_filter = ['is_active', 'action_type']
    search_fields = ['rule__name']


@admin.register(RuleCondition)
class RuleConditionAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'operator', 'is_active', 'created_at']
    list_filter = ['is_active', 'operator']
    search_fields = ['rule__name', 'field']


@admin.register(AutomationSchedule)
class AutomationScheduleAdmin(admin.ModelAdmin):
    list_display = ('rule', 'cron_expression', 'timezone', 'next_run', 'is_paused')
    list_filter = ('is_paused',)
