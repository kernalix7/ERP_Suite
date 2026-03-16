from django import forms
from apps.inventory.forms import BaseForm
from .models import BOM, BOMItem, ProductionPlan, WorkOrder, ProductionRecord


class BOMForm(BaseForm):
    class Meta:
        model = BOM
        fields = ['product', 'version', 'is_default', 'notes']


class BOMItemForm(BaseForm):
    class Meta:
        model = BOMItem
        fields = ['material', 'quantity', 'loss_rate']


BOMItemFormSet = forms.inlineformset_factory(
    BOM, BOMItem,
    form=BOMItemForm,
    extra=3,
    can_delete=True,
)


class ProductionPlanForm(BaseForm):
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
        fields = ['work_order', 'good_quantity', 'defect_quantity', 'record_date', 'worker', 'notes']
        widgets = {
            'record_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }
