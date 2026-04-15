from django import forms

from apps.core.forms import BaseForm
from .models import AutomationRule, RuleAction, RuleCondition, AutomationSchedule


class AutomationRuleForm(BaseForm):
    class Meta:
        model = AutomationRule
        fields = ['name', 'description', 'trigger_type', 'trigger_config', 'priority']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'trigger_config': forms.Textarea(attrs={'rows': 4, 'class': 'form-input font-mono text-sm'}),
        }

    def clean_trigger_config(self):
        import json
        val = self.cleaned_data.get('trigger_config')
        if isinstance(val, str):
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                raise forms.ValidationError('올바른 JSON 형식이 아닙니다.')
        return val or {}


class RuleActionForm(BaseForm):
    class Meta:
        model = RuleAction
        fields = ['rule', 'sequence', 'action_type', 'action_config', 'on_error']
        widgets = {
            'action_config': forms.Textarea(attrs={'rows': 4, 'class': 'form-input font-mono text-sm'}),
        }

    def clean_action_config(self):
        import json
        val = self.cleaned_data.get('action_config')
        if isinstance(val, str):
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                raise forms.ValidationError('올바른 JSON 형식이 아닙니다.')
        return val or {}


class RuleConditionForm(BaseForm):
    class Meta:
        model = RuleCondition
        fields = ['rule', 'field', 'operator', 'value', 'logic_op']


class AutomationScheduleForm(BaseForm):
    class Meta:
        model = AutomationSchedule
        fields = ['rule', 'cron_expression', 'timezone', 'next_run', 'is_paused']
        widgets = {
            'next_run': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
