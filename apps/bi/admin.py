from django.contrib import admin

from .models import Report, ReportSchedule, Dashboard, DashboardPanel, SavedFilter


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('name', 'report_type', 'data_source', 'owner', 'is_public', 'is_active')
    list_filter = ('report_type', 'data_source', 'is_public', 'is_active')
    search_fields = ('name', 'description')


@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = ('report', 'frequency', 'format', 'last_sent', 'next_send', 'is_active')
    list_filter = ('frequency', 'format', 'is_active')


@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'is_default', 'is_active')
    list_filter = ('is_default', 'is_active')
    search_fields = ('name',)


@admin.register(DashboardPanel)
class DashboardPanelAdmin(admin.ModelAdmin):
    list_display = ('dashboard', 'report', 'position_x', 'position_y', 'width', 'height')
    list_filter = ('dashboard',)


@admin.register(SavedFilter)
class SavedFilterAdmin(admin.ModelAdmin):
    list_display = ('name', 'data_source', 'owner', 'is_active')
    list_filter = ('data_source', 'is_active')
    search_fields = ('name',)
