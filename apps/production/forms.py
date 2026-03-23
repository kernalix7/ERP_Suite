from django import forms
from apps.core.forms import BaseForm
from .models import BOM, BOMItem, ProductionPlan, WorkOrder, ProductionRecord, StandardCost


class BOMForm(BaseForm):
    class Meta:
        model = BOM
        fields = ['product', 'version', 'is_default', 'notes']


class BOMItemForm(BaseForm):
    class Meta:
        model = BOMItem
        fields = ['material', 'purchase_qty', 'production_qty', 'quantity', 'loss_rate']


BOMItemFormSet = forms.inlineformset_factory(
    BOM, BOMItem,
    form=BOMItemForm,
    extra=3,
    can_delete=True,
)


class ProductionPlanForm(BaseForm):
    estimated_cost = forms.CharField(
        label='예상원가', required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input money-input',
            'readonly': 'readonly',
        }),
    )
    actual_cost = forms.CharField(
        label='실제원가', required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input money-input',
        }),
    )

    class Meta:
        model = ProductionPlan
        fields = [
            'plan_number', 'product', 'bom', 'planned_quantity',
            'planned_start', 'planned_end', 'status',
            'estimated_cost', 'actual_cost', 'notes',
        ]
        widgets = {
            'planned_start': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'planned_end': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }

    def clean_estimated_cost(self):
        val = self.cleaned_data.get('estimated_cost', '0')
        return int(str(val).replace(',', '').strip() or '0')

    def clean_actual_cost(self):
        val = self.cleaned_data.get('actual_cost', '0')
        return int(str(val).replace(',', '').strip() or '0')

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('planned_start')
        end = cleaned.get('planned_end')
        if start and end and end < start:
            raise forms.ValidationError('계획종료일은 시작일 이후여야 합니다.')
        return cleaned


class WorkOrderForm(BaseForm):
    class Meta:
        model = WorkOrder
        fields = [
            'order_number', 'production_plan', 'assigned_to',
            'quantity', 'status', 'notes',
        ]


class ProductionRecordForm(BaseForm):
    class Meta:
        model = ProductionRecord
        fields = [
            'work_order', 'warehouse', 'good_quantity', 'defect_quantity',
            'actual_material_cost', 'actual_labor_cost', 'actual_overhead_cost',
            'record_date', 'worker', 'notes',
        ]
        widgets = {
            'record_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class StandardCostForm(BaseForm):
    material_cost = forms.CharField(
        label='표준자재원가', required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input money-input',
            'readonly': 'readonly',
        }),
    )
    labor_cost = forms.CharField(
        label='표준노무비', required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input money-input',
            'readonly': 'readonly',
        }),
    )
    overhead_cost = forms.CharField(
        label='표준간접비', required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input money-input',
            'readonly': 'readonly',
        }),
    )
    total_standard_cost = forms.CharField(
        label='표준원가 합계', required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input money-input',
            'readonly': 'readonly',
        }),
    )

    class Meta:
        model = StandardCost
        fields = [
            'product', 'version', 'effective_date', 'is_current',
            'material_cost',
            'direct_labor_hours', 'labor_rate_per_hour', 'labor_cost',
            'overhead_rate', 'overhead_cost',
            'total_standard_cost', 'notes',
        ]
        widgets = {
            'effective_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }

    def clean_material_cost(self):
        val = self.cleaned_data.get('material_cost', '0')
        return int(str(val).replace(',', '').strip() or '0')

    def clean_labor_cost(self):
        val = self.cleaned_data.get('labor_cost', '0')
        return int(str(val).replace(',', '').strip() or '0')

    def clean_overhead_cost(self):
        val = self.cleaned_data.get('overhead_cost', '0')
        return int(str(val).replace(',', '').strip() or '0')

    def clean_total_standard_cost(self):
        val = self.cleaned_data.get('total_standard_cost', '0')
        return int(str(val).replace(',', '').strip() or '0')
