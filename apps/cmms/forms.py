from django import forms

from apps.core.forms import BaseForm
from .models import Equipment, EquipmentDowntime, MaintenanceSchedule, MaintenanceWorkOrder, SparePart


class EquipmentForm(BaseForm):
    class Meta:
        model = Equipment
        fields = [
            'name', 'code', 'category', 'location', 'manufacturer',
            'model_number', 'serial_number', 'purchase_date', 'purchase_cost',
            'status', 'department', 'notes',
        ]
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
        }


class MaintenanceScheduleForm(BaseForm):
    class Meta:
        model = MaintenanceSchedule
        fields = [
            'equipment', 'maintenance_type', 'title', 'frequency_days',
            'last_performed', 'next_due', 'assigned_to', 'instructions', 'notes',
        ]
        widgets = {
            'last_performed': forms.DateInput(attrs={'type': 'date'}),
            'next_due': forms.DateInput(attrs={'type': 'date'}),
        }


class MaintenanceWorkOrderForm(BaseForm):
    class Meta:
        model = MaintenanceWorkOrder
        fields = [
            'schedule', 'equipment', 'priority', 'description',
            'assigned_to', 'notes',
        ]


class WorkOrderCompleteForm(BaseForm):
    class Meta:
        model = MaintenanceWorkOrder
        fields = ['findings', 'parts_used', 'cost']


class SparePartForm(BaseForm):
    class Meta:
        model = SparePart
        fields = ['name', 'code', 'equipment_types', 'current_stock', 'min_stock', 'unit_cost', 'notes']


class EquipmentDowntimeForm(BaseForm):
    class Meta:
        model = EquipmentDowntime
        fields = ['equipment', 'start_time', 'end_time', 'reason', 'work_order', 'notes']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_time')
        end = cleaned.get('end_time')
        if start and end and end <= start:
            raise forms.ValidationError('종료시각은 시작시각 이후여야 합니다.')
        return cleaned
