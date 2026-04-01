from django import forms

from apps.core.forms import BaseForm
from .models import Department, ExternalCompany, Position, EmployeeProfile, PersonnelAction, PayrollConfig, Payroll


class OnboardingForm(forms.Form):
    """신규 입사 통합 폼"""
    name = forms.CharField(
        label='이름', max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-input'}),
    )
    email = forms.EmailField(
        label='이메일 (로그인 계정)', max_length=150,
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'user@company.com'}),
        help_text='이 이메일로 로그인합니다.',
    )
    employee_type = forms.ChoiceField(
        label='고용유형', choices=EmployeeProfile.EmployeeType.choices,
        widget=forms.Select(attrs={'class': 'form-input'}),
        initial='INTERNAL',
    )
    external_company = forms.ModelChoiceField(
        label='소속 외부업체',
        queryset=ExternalCompany.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-input'}),
        required=False,
    )
    department = forms.ModelChoiceField(
        label='부서', queryset=Department.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-input'}),
        required=False,
    )
    position = forms.ModelChoiceField(
        label='직급', queryset=Position.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-input'}),
        required=False,
    )
    hire_date = forms.DateField(
        label='입사일',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
    )
    contract_type = forms.ChoiceField(
        label='계약유형', choices=EmployeeProfile.ContractType.choices,
        widget=forms.Select(attrs={'class': 'form-input'}),
    )
    contract_start = forms.DateField(
        label='계약시작일', required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
    )
    contract_end = forms.DateField(
        label='계약종료일', required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
    )
    base_salary = forms.DecimalField(
        label='기본급', max_digits=15, decimal_places=0, initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
    )
    employee_number = forms.CharField(
        label='사번', max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-input'}),
        required=False,
        help_text='비워두면 자동 생성됩니다.',
    )

    def clean(self):
        cleaned = super().clean()
        emp_type = cleaned.get('employee_type')
        if emp_type in ('EXTERNAL', 'DISPATCH') and not cleaned.get('external_company'):
            self.add_error('external_company', '외부협력/파견 유형은 소속 업체를 선택해야 합니다.')
        return cleaned

    def clean_email(self):
        from apps.accounts.models import User
        email = self.cleaned_data['email']
        if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
            raise forms.ValidationError('이미 사용 중인 이메일입니다.')
        return email


class OffboardingForm(forms.Form):
    """퇴사 처리 폼"""
    employee = forms.ModelChoiceField(
        label='직원',
        queryset=EmployeeProfile.objects.filter(
            is_active=True, status=EmployeeProfile.Status.ACTIVE,
        ).select_related('user'),
        widget=forms.Select(attrs={'class': 'form-input'}),
    )
    resignation_date = forms.DateField(
        label='퇴사일',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
    )
    reason = forms.CharField(
        label='퇴사 사유', required=False,
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
    )


class ExternalCompanyForm(BaseForm):
    class Meta:
        model = ExternalCompany
        fields = [
            'name', 'business_number', 'representative', 'contact_person',
            'phone', 'email', 'address', 'contract_start', 'contract_end', 'notes',
        ]
        widgets = {
            'contract_start': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'contract_end': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'address': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
        }


class DepartmentForm(BaseForm):
    class Meta:
        model = Department
        fields = ['code', 'name', 'parent', 'manager', 'notes']


class PositionForm(BaseForm):
    class Meta:
        model = Position
        fields = ['code', 'name', 'level', 'notes']


class EmployeeProfileForm(BaseForm):
    class Meta:
        model = EmployeeProfile
        fields = [
            'user', 'employee_number', 'department', 'position',
            'hire_date', 'birth_date', 'address', 'emergency_contact',
            'bank_name', 'bank_account', 'contract_type', 'status',
            'resignation_date', 'base_salary',
            'employee_type', 'external_company', 'contract_start', 'contract_end',
            'notes',
        ]
        widgets = {
            'hire_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'resignation_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'contract_start': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'contract_end': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
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
