from django.contrib import admin

from .models import (
    CardTransaction, CorporateCard, ExpenseCategory, ExpenseClaim,
    ExpenseItem, ExpensePolicy,
)


@admin.register(ExpensePolicy)
class ExpensePolicyAdmin(admin.ModelAdmin):
    list_display = ['name', 'max_amount', 'daily_limit', 'monthly_limit', 'requires_receipt', 'is_active']
    list_filter = ['requires_receipt', 'requires_approval', 'is_active']


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'account_code', 'parent', 'policy', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code']


class ExpenseItemInline(admin.TabularInline):
    model = ExpenseItem
    extra = 0


@admin.register(ExpenseClaim)
class ExpenseClaimAdmin(admin.ModelAdmin):
    list_display = ['claim_number', 'title', 'employee', 'status', 'total_amount', 'submitted_date']
    list_filter = ['status', 'is_active']
    search_fields = ['claim_number', 'title']
    inlines = [ExpenseItemInline]


@admin.register(CorporateCard)
class CorporateCardAdmin(admin.ModelAdmin):
    list_display = ['card_number_last4', 'employee', 'card_type', 'monthly_limit', 'is_active']
    list_filter = ['is_active']


@admin.register(CardTransaction)
class CardTransactionAdmin(admin.ModelAdmin):
    list_display = ['card', 'transaction_date', 'merchant', 'amount', 'matched_expense', 'is_personal']
    list_filter = ['is_personal', 'is_active']
