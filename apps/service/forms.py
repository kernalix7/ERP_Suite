from django import forms
from apps.core.forms import BaseForm
from .models import ServiceRequest, RepairRecord


class ServiceRequestForm(BaseForm):
    class Meta:
        model = ServiceRequest
        fields = [
            'request_number', 'customer', 'product', 'serial_number',
            'request_type', 'status', 'symptom', 'received_date',
            'completed_date', 'is_warranty', 'notes',
        ]
        widgets = {
            'received_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'completed_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class RepairRecordForm(BaseForm):
    class Meta:
        model = RepairRecord
        fields = [
            'service_request', 'repair_date', 'description',
            'parts_used', 'cost', 'technician', 'notes',
        ]
        widgets = {
            'repair_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }
