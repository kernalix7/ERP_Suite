from django.urls import path

from . import views

app_name = 'accounting'

urlpatterns = [
    path('', views.AccountingDashboardView.as_view(), name='dashboard'),
    path('tax-rates/', views.TaxRateListView.as_view(), name='taxrate_list'),
    path('tax-rates/create/', views.TaxRateCreateView.as_view(), name='taxrate_create'),
    path('tax-rates/<int:pk>/edit/', views.TaxRateUpdateView.as_view(), name='taxrate_update'),
    path('invoices/', views.TaxInvoiceListView.as_view(), name='taxinvoice_list'),
    path('invoices/create/', views.TaxInvoiceCreateView.as_view(), name='taxinvoice_create'),
    path('invoices/<int:pk>/', views.TaxInvoiceDetailView.as_view(), name='taxinvoice_detail'),
    path('invoices/<int:pk>/edit/', views.TaxInvoiceUpdateView.as_view(), name='taxinvoice_update'),
    path('vat-summary/', views.VATSummaryView.as_view(), name='vat_summary'),
    path('fixed-costs/', views.FixedCostListView.as_view(), name='fixedcost_list'),
    path('fixed-costs/create/', views.FixedCostCreateView.as_view(), name='fixedcost_create'),
    path('fixed-costs/<int:pk>/edit/', views.FixedCostUpdateView.as_view(), name='fixedcost_update'),
    path('breakeven/', views.BreakEvenView.as_view(), name='breakeven'),
    path('monthly-pl/', views.MonthlyPLView.as_view(), name='monthly_pl'),
    path('withholding/', views.WithholdingTaxListView.as_view(), name='withholding_list'),
    path('withholding/create/', views.WithholdingTaxCreateView.as_view(), name='withholding_create'),
    path('withholding/<int:pk>/edit/', views.WithholdingTaxUpdateView.as_view(), name='withholding_update'),
    # 계정과목
    path('accounts/', views.AccountCodeListView.as_view(), name='accountcode_list'),
    path('accounts/create/', views.AccountCodeCreateView.as_view(), name='accountcode_create'),
    path('accounts/<int:pk>/edit/', views.AccountCodeUpdateView.as_view(), name='accountcode_update'),
    # 전표
    path('vouchers/', views.VoucherListView.as_view(), name='voucher_list'),
    path('vouchers/create/', views.VoucherCreateView.as_view(), name='voucher_create'),
    path('vouchers/<int:pk>/', views.VoucherDetailView.as_view(), name='voucher_detail'),
    path('vouchers/<int:pk>/edit/', views.VoucherUpdateView.as_view(), name='voucher_update'),
    # 결재/품의
    path('approvals/', views.ApprovalListView.as_view(), name='approval_list'),
    path('approvals/create/', views.ApprovalCreateView.as_view(), name='approval_create'),
    path('approvals/<int:pk>/', views.ApprovalDetailView.as_view(), name='approval_detail'),
    path('approvals/<int:pk>/submit/', views.ApprovalSubmitView.as_view(), name='approval_submit'),
    path('approvals/<int:pk>/action/', views.ApprovalActionView.as_view(), name='approval_action'),
    path('approvals/<int:pk>/step/<int:step_pk>/action/', views.ApprovalStepActionView.as_view(), name='approval_step_action'),
    # 미수금
    path('receivables/', views.ARListView.as_view(), name='ar_list'),
    path('receivables/create/', views.ARCreateView.as_view(), name='ar_create'),
    path('receivables/<int:pk>/', views.ARDetailView.as_view(), name='ar_detail'),
    path('receivables/<int:pk>/payment/', views.PaymentCreateView.as_view(), name='payment_create'),
    # 미지급금
    path('payables/', views.APListView.as_view(), name='ap_list'),
    path('payables/create/', views.APCreateView.as_view(), name='ap_create'),
    path('payables/<int:pk>/', views.APDetailView.as_view(), name='ap_detail'),
    path('payables/<int:pk>/disbursement/', views.DisbursementCreateView.as_view(), name='disbursement_create'),
    # PDF
    path('invoices/<int:pk>/pdf/', views.TaxInvoicePDFView.as_view(), name='taxinvoice_pdf'),
]
