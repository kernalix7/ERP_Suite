from django import forms
from apps.core.forms import BaseForm
from .models import AssetCategory, FixedAsset


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
            'department', 'location', 'responsible_person',
            'notes',
        ]
        widgets = {
            'acquisition_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class AssetDisposalForm(BaseForm):
    class Meta:
        model = FixedAsset
        fields = ['status', 'disposal_date', 'disposal_amount', 'disposal_reason']
        widgets = {
            'disposal_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class DepreciationRunForm(forms.Form):
    """감가상각 일괄실행 폼"""
    year = forms.IntegerField(label='년도', widget=forms.NumberInput(attrs={'class': 'form-input'}))
    month = forms.IntegerField(label='월', min_value=1, max_value=12, widget=forms.NumberInput(attrs={'class': 'form-input'}))
