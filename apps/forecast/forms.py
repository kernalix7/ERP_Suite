from django import forms

from apps.core.forms import BaseForm
from .models import DemandForecast, ForecastParameter, SOPLineItem, SOPMeeting, SOPScenario


class ForecastParameterForm(BaseForm):
    class Meta:
        model = ForecastParameter
        fields = ['product', 'method', 'lookback_months', 'weight_recent', 'smoothing_factor', 'notes']


class DemandForecastForm(BaseForm):
    class Meta:
        model = DemandForecast
        fields = ['product', 'period_start', 'period_end', 'forecast_method', 'forecast_qty', 'actual_qty', 'notes']
        widgets = {
            'period_start': forms.DateInput(attrs={'type': 'date'}),
            'period_end': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('period_start')
        end = cleaned.get('period_end')
        if start and end and end <= start:
            raise forms.ValidationError('기간종료는 기간시작 이후여야 합니다.')
        return cleaned


class SOPMeetingForm(BaseForm):
    class Meta:
        model = SOPMeeting
        fields = ['title', 'meeting_date', 'period', 'attendees', 'notes']
        widgets = {
            'meeting_date': forms.DateInput(attrs={'type': 'date'}),
        }


class SOPScenarioForm(BaseForm):
    class Meta:
        model = SOPScenario
        fields = ['name', 'description', 'assumptions']


class SOPLineItemForm(BaseForm):
    class Meta:
        model = SOPLineItem
        fields = ['product', 'forecast_qty', 'planned_production', 'planned_purchase', 'planned_inventory']
