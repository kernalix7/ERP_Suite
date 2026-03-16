from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import AttendanceRecord, LeaveRequest, AnnualLeaveBalance


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(SimpleHistoryAdmin):
    list_display = ('user', 'date', 'check_in', 'check_out', 'status', 'overtime_hours', 'is_active')
    list_filter = ('status', 'date', 'is_active')
    search_fields = ('user__name', 'user__username')
    date_hierarchy = 'date'


@admin.register(LeaveRequest)
class LeaveRequestAdmin(SimpleHistoryAdmin):
    list_display = ('user', 'leave_type', 'start_date', 'end_date', 'days', 'status', 'approved_by')
    list_filter = ('leave_type', 'status')
    search_fields = ('user__name', 'user__username')


@admin.register(AnnualLeaveBalance)
class AnnualLeaveBalanceAdmin(SimpleHistoryAdmin):
    list_display = ('user', 'year', 'total_days', 'used_days', 'is_active')
    list_filter = ('year',)
    search_fields = ('user__name', 'user__username')
