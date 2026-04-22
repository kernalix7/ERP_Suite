from django import forms
from apps.core.forms import BaseForm
from .models import BOM, BOMItem, ProductionPlan, WorkOrder, ProductionRecord, StandardCost, WorkCenter, ProductionSchedule


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
            'work_center', 'quantity', 'status', 'notes',
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

    def clean(self):
        cleaned = super().clean()
        if self.instance and self.instance.pk:
            return cleaned
        wo = cleaned.get('work_order')
        warehouse = cleaned.get('warehouse')
        good = cleaned.get('good_quantity') or 0
        defect = cleaned.get('defect_quantity') or 0
        total = good + defect
        if not wo or not warehouse or total <= 0:
            return cleaned
        plan = wo.production_plan
        bom = plan.bom if plan else None
        if not bom:
            return cleaned
        from apps.inventory.models import WarehouseStock
        lines = []
        for bi in bom.items.select_related('material').all():
            mat = bi.material
            if not mat.is_stockable:
                continue
            needed = bi.effective_quantity * total
            ws = WarehouseStock.objects.filter(
                warehouse=warehouse, product=mat,
            ).first()
            avail = ws.quantity if ws else 0
            if avail < needed:
                lines.append(
                    f'{mat.code} {mat.name}: 필요 {needed}, '
                    f'재고 {avail}, 부족 {needed - avail}'
                )
        if lines:
            raise forms.ValidationError(
                f'선택한 창고({warehouse.code} {warehouse.name})에 '
                f'원자재 재고가 부족합니다. 해당 창고로 자재를 이동하거나 '
                f'자재가 있는 다른 창고를 선택해주세요. — '
                + ' | '.join(lines)
            )
        return cleaned


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


class WorkCenterForm(BaseForm):
    class Meta:
        model = WorkCenter
        fields = ['name', 'code', 'capacity_per_day', 'efficiency_rate', 'operating_hours', 'notes']


class ProductionScheduleForm(BaseForm):
    class Meta:
        model = ProductionSchedule
        fields = [
            'work_order', 'work_center', 'scheduled_start', 'scheduled_end',
            'actual_start', 'actual_end', 'status', 'assigned_workers', 'priority', 'notes',
        ]
        widgets = {
            'scheduled_start': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'}),
            'scheduled_end': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'}),
            'actual_start': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'}),
            'actual_end': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('scheduled_start')
        end = cleaned.get('scheduled_end')
        if start and end and end <= start:
            raise forms.ValidationError('예정종료는 예정시작 이후여야 합니다.')
        actual_start = cleaned.get('actual_start')
        actual_end = cleaned.get('actual_end')
        if actual_start and actual_end and actual_end <= actual_start:
            raise forms.ValidationError('실제종료는 실제시작 이후여야 합니다.')
        return cleaned
