from django import forms

from apps.core.forms import BaseForm
from .models import (
    CarbonEmission, ComplianceRequirement, ESGCategory, ESGMetric,
    ESGRecord, ESGReport, SafetyIncident,
)


class ESGCategoryForm(BaseForm):
    class Meta:
        model = ESGCategory
        fields = ['name', 'code', 'category_type', 'parent', 'notes']


class ESGMetricForm(BaseForm):
    class Meta:
        model = ESGMetric
        fields = ['category', 'name', 'code', 'unit', 'target_value',
                  'measurement_frequency', 'notes']


class ESGRecordForm(BaseForm):
    class Meta:
        model = ESGRecord
        fields = ['metric', 'period_start', 'period_end', 'value', 'notes']
        widgets = {
            'period_start': forms.DateInput(attrs={'type': 'date'}),
            'period_end': forms.DateInput(attrs={'type': 'date'}),
        }


class CarbonEmissionForm(BaseForm):
    class Meta:
        model = CarbonEmission
        fields = ['source', 'scope', 'emission_type', 'amount_kg',
                  'period', 'facility', 'calculation_method', 'notes']
        widgets = {
            'period': forms.DateInput(attrs={'type': 'date'}),
        }


class SafetyIncidentForm(BaseForm):
    class Meta:
        model = SafetyIncident
        fields = ['date', 'location', 'severity', 'description',
                  'injured_count', 'root_cause', 'corrective_action',
                  'status', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }


class ComplianceRequirementForm(BaseForm):
    class Meta:
        model = ComplianceRequirement
        fields = ['name', 'regulation', 'description', 'responsible',
                  'due_date', 'status', 'evidence_file', 'last_review', 'notes']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'last_review': forms.DateInput(attrs={'type': 'date'}),
        }


class ESGReportForm(BaseForm):
    class Meta:
        model = ESGReport
        fields = ['title', 'report_type', 'period_start', 'period_end',
                  'status', 'notes']
        widgets = {
            'period_start': forms.DateInput(attrs={'type': 'date'}),
            'period_end': forms.DateInput(attrs={'type': 'date'}),
        }
