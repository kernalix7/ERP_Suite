from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Investor, InvestmentRound, Investment, EquityChange, Distribution


@admin.register(Investor)
class InvestorAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'company', 'phone', 'registration_date')
    search_fields = ('name', 'company')


@admin.register(InvestmentRound)
class InvestmentRoundAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'round_type', 'target_amount', 'raised_amount', 'round_date', 'post_valuation')


@admin.register(Investment)
class InvestmentAdmin(SimpleHistoryAdmin):
    list_display = ('investor', 'round', 'amount', 'share_percentage', 'investment_date')


@admin.register(EquityChange)
class EquityChangeAdmin(SimpleHistoryAdmin):
    list_display = ('investor', 'change_type', 'before_percentage', 'after_percentage', 'change_date')


@admin.register(Distribution)
class DistributionAdmin(SimpleHistoryAdmin):
    list_display = ('investor', 'distribution_type', 'amount', 'status', 'scheduled_date', 'fiscal_year')
    list_filter = ('status', 'distribution_type')
