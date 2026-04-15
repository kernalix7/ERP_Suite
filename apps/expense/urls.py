from django.urls import path

from apps.core import excel_views
from . import views

app_name = 'expense'

urlpatterns = [
    path('', views.ExpenseDashboardView.as_view(), name='dashboard'),
    # Policy
    path('policies/', views.ExpensePolicyListView.as_view(), name='policy_list'),
    path('policies/create/', views.ExpensePolicyCreateView.as_view(), name='policy_create'),
    path('policies/<int:pk>/edit/', views.ExpensePolicyUpdateView.as_view(), name='policy_update'),
    # Category
    path('categories/', views.ExpenseCategoryListView.as_view(), name='category_list'),
    path('categories/create/', views.ExpenseCategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/edit/', views.ExpenseCategoryUpdateView.as_view(), name='category_update'),
    # Claim
    path('claims/', views.ExpenseClaimListView.as_view(), name='claim_list'),
    path('claims/excel/', excel_views.ExpenseClaimExcelView.as_view(), name='claim_excel'),
    path('claims/create/', views.ExpenseClaimCreateView.as_view(), name='claim_create'),
    path('claims/<str:slug>/', views.ExpenseClaimDetailView.as_view(), name='claim_detail'),
    path('claims/<str:slug>/submit/', views.ExpenseClaimSubmitView.as_view(), name='claim_submit'),
    path('claims/<str:slug>/approve/', views.ExpenseClaimApproveView.as_view(), name='claim_approve'),
    path('claims/<str:slug>/reject/', views.ExpenseClaimRejectView.as_view(), name='claim_reject'),
    # Corporate Card
    path('cards/', views.CorporateCardListView.as_view(), name='card_list'),
    path('cards/create/', views.CorporateCardCreateView.as_view(), name='card_create'),
    # Transaction
    path('transactions/', views.CardTransactionListView.as_view(), name='transaction_list'),
    path('transactions/<int:pk>/match/', views.CardTransactionMatchView.as_view(), name='transaction_match'),
]
