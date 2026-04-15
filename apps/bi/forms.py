from django import forms

from apps.core.forms import BaseForm
from .models import Report, ReportSchedule, Dashboard, DashboardPanel, SavedFilter


class ReportForm(BaseForm):
    class Meta:
        model = Report
        fields = [
            'name', 'description', 'report_type', 'data_source',
            'query_config', 'chart_config', 'is_public', 'is_favorite',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'query_config': forms.HiddenInput(),
            'chart_config': forms.HiddenInput(),
        }


class ReportScheduleForm(BaseForm):
    class Meta:
        model = ReportSchedule
        fields = ['report', 'frequency', 'recipients', 'format', 'next_send']
        widgets = {
            'next_send': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'recipients': forms.SelectMultiple(attrs={'class': 'form-input h-32'}),
        }


class DashboardForm(BaseForm):
    class Meta:
        model = Dashboard
        fields = ['name', 'description', 'is_default']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class DashboardPanelForm(BaseForm):
    class Meta:
        model = DashboardPanel
        fields = [
            'dashboard', 'report', 'position_x', 'position_y',
            'width', 'height', 'refresh_interval_minutes',
        ]


class SavedFilterForm(BaseForm):
    class Meta:
        model = SavedFilter
        fields = ['name', 'data_source', 'filter_config']
        widgets = {
            'filter_config': forms.HiddenInput(),
        }
