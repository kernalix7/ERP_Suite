from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Department, Position, EmployeeProfile, PersonnelAction


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
