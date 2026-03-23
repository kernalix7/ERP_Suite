from django import forms

from apps.core.forms import BaseForm
from .models import Department, Position, EmployeeProfile, PersonnelAction, PayrollConfig, Payroll


class DepartmentForm(BaseForm):
    class Meta:
        model = Department
        fields = ['code', 'name', 'parent', 'manager', 'notes']


class PositionForm(BaseForm):
    class Meta:
        model = Position
        fields = ['name', 'level', 'notes']


class EmployeeProfileForm(BaseForm):
    class Meta:
        model = EmployeeProfile
        fields = [
            'user', 'employee_number', 'department', 'position',
            'hire_date', 'birth_date', 'address', 'emergency_contact',
            'bank_name', 'bank_account', 'contract_type', 'status',
            'resignation_date', 'base_salary', 'notes',
        ]
        widgets = {
            'hire_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'resignation_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class PersonnelActionForm(BaseForm):
    class Meta:
        model = PersonnelAction
        fields = [
            'employee', 'action_type', 'effective_date',
            'from_department', 'to_department',
            'from_position', 'to_position',
            'reason',
        ]
        widgets = {
            'effective_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class PayrollConfigForm(BaseForm):
    class Meta:
        model = PayrollConfig
        fields = [
            'year', 'minimum_wage_hourly',
            'national_pension_rate', 'health_insurance_rate',
            'long_term_care_rate', 'employment_insurance_rate',
            'notes',
        ]


class PayrollForm(BaseForm):
    class Meta:
        model = Payroll
        fields = [
            'employee', 'year', 'month',
            'base_salary', 'overtime_pay', 'bonus', 'allowances',
            'status', 'paid_date', 'notes',
        ]
        widgets = {
            'paid_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class PayrollBulkCreateForm(forms.Form):
    """전사 급여 일괄 생성 폼"""
    year = forms.IntegerField(label='년도', widget=forms.NumberInput(attrs={'class': 'form-input'}))
    month = forms.IntegerField(
        label='월',
        min_value=1, max_value=12,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'min': 1, 'max': 12}),
    )
