from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Department, Position, EmployeeProfile, PersonnelAction, PayrollConfig, Payroll


@admin.register(Department)
class DepartmentAdmin(SimpleHistoryAdmin):
    list_display = ('code', 'name', 'parent', 'manager', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name')


@admin.register(Position)
class PositionAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'level', 'is_active')
    list_filter = ('is_active',)


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(SimpleHistoryAdmin):
    list_display = ('employee_number', 'user', 'department', 'position', 'status', 'hire_date')
    list_filter = ('status', 'contract_type', 'department')
    search_fields = ('employee_number', 'user__name', 'user__username')


@admin.register(PersonnelAction)
class PersonnelActionAdmin(SimpleHistoryAdmin):
    list_display = ('employee', 'action_type', 'effective_date', 'to_department', 'to_position')
    list_filter = ('action_type', 'effective_date')
    search_fields = ('employee__user__name', 'employee__employee_number')


@admin.register(PayrollConfig)
class PayrollConfigAdmin(SimpleHistoryAdmin):
    list_display = ('year', 'minimum_wage_hourly', 'national_pension_rate', 'health_insurance_rate', 'is_active')
    list_filter = ('is_active', 'year')


@admin.register(Payroll)
class PayrollAdmin(SimpleHistoryAdmin):
    list_display = ('employee', 'year', 'month', 'gross_pay', 'total_deductions', 'net_pay', 'status')
    list_filter = ('status', 'year', 'month')
    search_fields = ('employee__user__name', 'employee__employee_number')
