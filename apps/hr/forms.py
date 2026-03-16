from django import forms

from .models import Department, Position, EmployeeProfile, PersonnelAction


class BaseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault('class', 'form-input h-24')
                field.widget.attrs.setdefault('rows', 3)
            elif isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                field.widget.attrs.setdefault('class', 'form-input')
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-checkbox')
            else:
                field.widget.attrs.setdefault('class', 'form-input')


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
            'resignation_date', 'notes',
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
