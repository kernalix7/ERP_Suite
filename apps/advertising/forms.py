from django import forms

from apps.core.forms import BaseForm

from .models import (
    AdPlatform, AdCampaign, AdCreative,
    AdPerformance, AdBudget,
)


class AdPlatformForm(BaseForm):
    class Meta:
        model = AdPlatform
        fields = [
            'name', 'platform_type', 'api_key',
            'api_secret', 'account_id', 'is_connected',
            'website_url', 'notes',
        ]
        widgets = {
            'api_secret': forms.PasswordInput(
                attrs={'class': 'form-input'}
            ),
        }


class AdCampaignForm(BaseForm):
    class Meta:
        model = AdCampaign
        fields = [
            'platform', 'name', 'campaign_type', 'status',
            'budget', 'spent', 'start_date', 'end_date',
            'target_audience', 'description', 'notes',
        ]
        widgets = {
            'start_date': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-input'}
            ),
            'end_date': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-input'}
            ),
        }


class AdCreativeForm(BaseForm):
    class Meta:
        model = AdCreative
        fields = [
            'campaign', 'name', 'creative_type',
            'headline', 'description', 'landing_url',
            'image', 'status', 'notes',
        ]


class AdPerformanceForm(BaseForm):
    class Meta:
        model = AdPerformance
        fields = [
            'campaign', 'creative', 'date',
            'impressions', 'clicks', 'conversions',
            'cost', 'revenue', 'notes',
        ]
        widgets = {
            'date': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-input'}
            ),
        }


class AdBudgetForm(BaseForm):
    class Meta:
        model = AdBudget
        fields = [
            'year', 'month', 'platform',
            'planned_budget', 'actual_spent', 'notes',
        ]
