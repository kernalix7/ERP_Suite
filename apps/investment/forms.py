from django import forms
from apps.core.forms import BaseForm
from .models import Investor, InvestmentRound, Investment, EquityChange, Distribution


class InvestorForm(BaseForm):
    class Meta:
        model = Investor
        fields = ['code', 'name', 'company', 'contact_person', 'phone', 'email', 'address', 'registration_date', 'notes']
        widgets = {
            'registration_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class InvestmentRoundForm(BaseForm):
    class Meta:
        model = InvestmentRound
        fields = [
            'code', 'name', 'round_type', 'target_amount', 'raised_amount',
            'round_date', 'pre_valuation', 'post_valuation', 'notes',
        ]
        widgets = {
            'round_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class InvestmentForm(BaseForm):
    class Meta:
        model = Investment
        fields = ['investor', 'round', 'amount', 'share_percentage', 'investment_date', 'notes']
        widgets = {
            'investment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class EquityChangeForm(BaseForm):
    class Meta:
        model = EquityChange
        fields = [
            'investor', 'change_type', 'change_date',
            'before_percentage', 'after_percentage', 'related_round', 'notes',
        ]
        widgets = {
            'change_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class DistributionForm(BaseForm):
    class Meta:
        model = Distribution
        fields = [
            'investor', 'distribution_type', 'amount',
            'scheduled_date', 'paid_date', 'status', 'fiscal_year', 'notes',
        ]
        widgets = {
            'scheduled_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'paid_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }
