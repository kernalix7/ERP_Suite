from django import forms
from apps.core.forms import BaseForm
from .models import (
    AssetAudit, AssetAuditItem, AssetCategory, AssetTransfer,
    Certification, FixedAsset, LeaseContract, Location,
    ReservableAsset, ReservationRule, AssetReservation, AssetMaintenance,
)


class LocationForm(BaseForm):
    class Meta:
        model = Location
        fields = ['name', 'code', 'building', 'floor', 'room', 'parent', 'notes']


class AssetCategoryForm(BaseForm):
    class Meta:
        model = AssetCategory
        fields = ['name', 'code', 'useful_life_years', 'depreciation_method', 'notes']


class FixedAssetForm(BaseForm):
    class Meta:
        model = FixedAsset
        fields = [
            'asset_number', 'name', 'category',
            'acquisition_date', 'acquisition_cost', 'residual_value',
            'useful_life_years', 'depreciation_method',
            'department', 'location', 'managed_location', 'responsible_person',
            'notes',
        ]
        widgets = {
            'acquisition_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class AssetDisposalForm(BaseForm):
    class Meta:
        model = FixedAsset
        fields = [
            'status', 'disposal_date', 'disposal_amount',
            'disposal_reason', 'condition_assessment', 'disposal_approval',
        ]
        widgets = {
            'disposal_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.approval.models import ApprovalRequest
        self.fields['disposal_approval'].queryset = ApprovalRequest.objects.filter(
            category='ASSET_DISPOSAL', status='APPROVED', is_active=True,
        )
        self.fields['disposal_approval'].required = False

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        instance = self.instance
        if status == FixedAsset.Status.DISPOSED and instance.book_value <= instance.residual_value:
            self.add_error(
                'status',
                '완전상각 자산은 처분(DISPOSED) 불가합니다. 폐기(SCRAPPED)만 허용됩니다.',
            )
        return cleaned_data


class AssetTransferForm(BaseForm):
    class Meta:
        model = AssetTransfer
        fields = ['transfer_date', 'to_department', 'to_person', 'to_location', 'to_managed_location', 'reason']
        widgets = {
            'transfer_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class AssetRegisterFilterForm(forms.Form):
    """자산대장 리포트 필터 폼"""
    start_date = forms.DateField(
        label='시작일',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
    )
    end_date = forms.DateField(
        label='종료일',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
    )
    category = forms.ModelChoiceField(
        label='자산분류',
        queryset=AssetCategory.objects.filter(is_active=True),
        required=False,
        empty_label='전체',
    )
    department = forms.ModelChoiceField(
        label='사용부서',
        queryset=None,
        required=False,
        empty_label='전체',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.hr.models import Department
        self.fields['department'].queryset = Department.objects.filter(is_active=True)


class CertificationForm(BaseForm):
    class Meta:
        model = Certification
        fields = [
            'product', 'asset', 'cert_type', 'cert_number', 'cert_name',
            'issuer', 'issue_date', 'expiry_date',
            'cost', 'is_capitalized', 'attachment', 'notes',
        ]
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class LeaseContractForm(BaseForm):
    class Meta:
        model = LeaseContract
        fields = [
            'asset', 'lease_type', 'lessor',
            'start_date', 'end_date',
            'monthly_payment', 'deposit',
            'auto_voucher', 'notes',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class AssetAuditForm(BaseForm):
    class Meta:
        model = AssetAudit
        fields = ['audit_date', 'auditor', 'department']
        widgets = {
            'audit_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class AssetAuditItemForm(BaseForm):
    class Meta:
        model = AssetAuditItem
        fields = ['status', 'actual_location', 'condition', 'remark']


class DepreciationRunForm(forms.Form):
    """감가상각 일괄실행 폼"""
    year = forms.IntegerField(label='년도', widget=forms.NumberInput(attrs={'class': 'form-input'}))
    month = forms.IntegerField(label='월', min_value=1, max_value=12, widget=forms.NumberInput(attrs={'class': 'form-input'}))


# ============================================================
# 자산 예약 폼
# ============================================================

class ReservableAssetForm(BaseForm):
    class Meta:
        model = ReservableAsset
        fields = [
            'fixed_asset', 'name', 'resource_type', 'description', 'location',
            'capacity', 'min_reserve_minutes', 'max_reserve_hours',
            'advance_days', 'requires_approval', 'image', 'notes',
        ]


class ReservationRuleForm(BaseForm):
    class Meta:
        model = ReservationRule
        fields = ['asset', 'day_of_week', 'open_time', 'close_time', 'is_closed']


class AssetReservationForm(BaseForm):
    class Meta:
        model = AssetReservation
        fields = [
            'asset', 'start_datetime', 'end_datetime',
            'purpose', 'attendee_count', 'notes',
        ]
        widgets = {
            'start_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'}),
            'end_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'}),
        }


class AssetMaintenanceForm(BaseForm):
    class Meta:
        model = AssetMaintenance
        fields = [
            'asset', 'maintenance_type', 'status', 'scheduled_date',
            'completed_date', 'technician', 'vendor', 'description',
            'cost', 'next_maintenance_date', 'notes',
        ]
        widgets = {
            'scheduled_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'completed_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'next_maintenance_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }
