from django.urls import path

from . import views
from apps.core import excel_views

app_name = 'accounting'

urlpatterns = [
    path('', views.AccountingDashboardView.as_view(), name='dashboard'),
    # 통화
    path('currencies/', views.CurrencyListView.as_view(), name='currency_list'),
    path('currencies/create/', views.CurrencyCreateView.as_view(), name='currency_create'),
    path('currencies/<int:pk>/edit/', views.CurrencyUpdateView.as_view(), name='currency_update'),
    # 환율
    path('exchange-rates/', views.ExchangeRateListView.as_view(), name='exchangerate_list'),
    path('exchange-rates/create/', views.ExchangeRateCreateView.as_view(), name='exchangerate_create'),
    path('tax-rates/', views.TaxRateListView.as_view(), name='taxrate_list'),
    path('tax-rates/create/', views.TaxRateCreateView.as_view(), name='taxrate_create'),
    path('tax-rates/<int:pk>/edit/', views.TaxRateUpdateView.as_view(), name='taxrate_update'),
    path('invoices/', views.TaxInvoiceListView.as_view(), name='taxinvoice_list'),
    path('invoices/create/', views.TaxInvoiceCreateView.as_view(), name='taxinvoice_create'),
    path('invoices/<str:slug>/', views.TaxInvoiceDetailView.as_view(), name='taxinvoice_detail'),
    path('invoices/<str:slug>/edit/', views.TaxInvoiceUpdateView.as_view(), name='taxinvoice_update'),
    path('vat-summary/', views.VATSummaryView.as_view(), name='vat_summary'),
    path('fixed-costs/', views.FixedCostListView.as_view(), name='fixedcost_list'),
    path('fixed-costs/create/', views.FixedCostCreateView.as_view(), name='fixedcost_create'),
    path('fixed-costs/<int:pk>/edit/', views.FixedCostUpdateView.as_view(), name='fixedcost_update'),
    # 결제계좌
    path('bank-accounts/', views.BankAccountListView.as_view(), name='bankaccount_list'),
    path('bank-accounts/dashboard/', views.BankAccountDashboardView.as_view(), name='bankaccount_dashboard'),
    path('bank-accounts/create/', views.BankAccountCreateView.as_view(), name='bankaccount_create'),
    path('bank-accounts/<int:pk>/', views.BankAccountDetailView.as_view(), name='bankaccount_detail'),
    path('bank-accounts/<int:pk>/edit/', views.BankAccountUpdateView.as_view(), name='bankaccount_update'),
    # 계좌이체
    path('transfers/', views.AccountTransferListView.as_view(), name='transfer_list'),
    path('transfers/create/', views.AccountTransferCreateView.as_view(), name='transfer_create'),
    # 결제분배
    path('payments/<str:slug>/distribute/', views.PaymentDistributeView.as_view(), name='payment_distribute'),
    # 원가정산
    path('settlements/', views.CostSettlementListView.as_view(), name='settlement_list'),
    path('settlements/create/', views.CostSettlementCreateView.as_view(), name='settlement_create'),
    path('settlements/<str:slug>/', views.CostSettlementDetailView.as_view(), name='settlement_detail'),
    path('settlements/<str:slug>/recalc/', views.CostSettlementRecalcView.as_view(), name='settlement_recalc'),
    # 매출정산
    path('sales-settlements/', views.SalesSettlementListView.as_view(), name='sales_settlement_list'),
    path('sales-settlements/create/', views.SalesSettlementCreateView.as_view(), name='sales_settlement_create'),
    path('sales-settlements/<str:slug>/', views.SalesSettlementDetailView.as_view(), name='sales_settlement_detail'),
    path('sales-settlements/<str:slug>/payment/', views.SalesSettlementPaymentView.as_view(), name='sales_settlement_payment'),
    path('sales-settlements/<str:slug>/commission-pay/', views.SalesSettlementCommissionPayView.as_view(), name='sales_settlement_commission_pay'),
    path('sales-settlements/<str:slug>/commission-manual/', views.SalesSettlementCommissionManualView.as_view(), name='sales_settlement_commission_manual'),
    path('breakeven/', views.BreakEvenView.as_view(), name='breakeven'),
    path('monthly-pl/', views.MonthlyPLView.as_view(), name='monthly_pl'),
    path('withholding/', views.WithholdingTaxListView.as_view(), name='withholding_list'),
    path('withholding/create/', views.WithholdingTaxCreateView.as_view(), name='withholding_create'),
    path('withholding/<int:pk>/edit/', views.WithholdingTaxUpdateView.as_view(), name='withholding_update'),
    # 계정별 원장 / 시산표 / 은행대사
    path('ledger/', views.AccountLedgerView.as_view(), name='account_ledger'),
    path('trial-balance/', views.TrialBalanceView.as_view(), name='trial_balance'),
    path('bank-reconciliation/', views.BankReconciliationView.as_view(), name='bank_reconciliation'),
    # 예산
    path('budget/', views.BudgetListView.as_view(), name='budget_list'),
    path('budget/create/', views.BudgetCreateView.as_view(), name='budget_create'),
    path('budget/report/', views.BudgetReportView.as_view(), name='budget_report'),
    # 결산 마감
    path('closing/', views.ClosingPeriodListView.as_view(), name='closing_list'),
    path('closing/<int:year>/<int:month>/close/', views.ClosingPeriodCloseView.as_view(), name='closing_close'),
    # 계정과목
    path('accounts/', views.AccountCodeListView.as_view(), name='accountcode_list'),
    path('accounts/create/', views.AccountCodeCreateView.as_view(), name='accountcode_create'),
    path('accounts/<int:pk>/edit/', views.AccountCodeUpdateView.as_view(), name='accountcode_update'),
    # 전표
    path('vouchers/', views.VoucherListView.as_view(), name='voucher_list'),
    path('vouchers/create/', views.VoucherCreateView.as_view(), name='voucher_create'),
    path('vouchers/<str:slug>/', views.VoucherDetailView.as_view(), name='voucher_detail'),
    path('vouchers/<str:slug>/edit/', views.VoucherUpdateView.as_view(), name='voucher_update'),
    # 결재 → apps/approval/ 앱으로 이동
    # 미수금
    path('receivables/', views.ARListView.as_view(), name='ar_list'),
    path('receivables/create/', views.ARCreateView.as_view(), name='ar_create'),
    path('receivables/<int:pk>/', views.ARDetailView.as_view(), name='ar_detail'),
    path('receivables/<int:pk>/payment/', views.PaymentCreateView.as_view(), name='payment_create'),
    path('ar-aging/', views.ARAgingView.as_view(), name='ar_aging'),
    # 미지급금
    path('payables/', views.APListView.as_view(), name='ap_list'),
    path('payables/create/', views.APCreateView.as_view(), name='ap_create'),
    path('payables/<int:pk>/', views.APDetailView.as_view(), name='ap_detail'),
    path('payables/<int:pk>/disbursement/', views.DisbursementCreateView.as_view(), name='disbursement_create'),
    path('ap-aging/', views.APAgingView.as_view(), name='ap_aging'),
    # PDF
    path('invoices/<str:slug>/pdf/', views.TaxInvoicePDFView.as_view(), name='taxinvoice_pdf'),
    # 전자세금계산서
    path('invoices/<str:slug>/electronic/issue/', views.ElectronicInvoiceIssueView.as_view(), name='electronic_invoice_issue'),
    path('invoices/<str:slug>/electronic/status/', views.ElectronicInvoiceStatusView.as_view(), name='electronic_invoice_status'),
    path('invoices/<str:slug>/electronic/cancel/', views.ElectronicInvoiceCancelView.as_view(), name='electronic_invoice_cancel'),
    path('invoices/electronic/batch-issue/', views.ElectronicInvoiceBatchIssueView.as_view(), name='electronic_invoice_batch_issue'),
    # 일괄 가져오기
    path('fixed-costs/import/', views.FixedCostImportView.as_view(), name='fixedcost_import'),
    path('fixed-costs/import/sample/', views.FixedCostImportSampleView.as_view(), name='fixedcost_import_sample'),
    path('accounts/import/', views.AccountCodeImportView.as_view(), name='accountcode_import'),
    path('accounts/import/sample/', views.AccountCodeImportSampleView.as_view(), name='accountcode_import_sample'),
    path('invoices/import/', views.TaxInvoiceImportView.as_view(), name='taxinvoice_import'),
    path('invoices/import/sample/', views.TaxInvoiceImportSampleView.as_view(), name='taxinvoice_import_sample'),
    # 전표 일괄 가져오기
    path('vouchers/import/', views.VoucherImportView.as_view(), name='voucher_import'),
    path('vouchers/import/sample/', views.VoucherImportSampleView.as_view(), name='voucher_import_sample'),
    # 원천징수 일괄 가져오기
    path('withholding/import/', views.WithholdingImportView.as_view(), name='withholding_import'),
    path('withholding/import/sample/', views.WithholdingImportSampleView.as_view(), name='withholding_import_sample'),
    # Excel 내보내기
    path('invoices/excel/', excel_views.TaxInvoiceExcelView.as_view(), name='taxinvoice_excel'),
    path('vouchers/excel/', excel_views.VoucherExcelView.as_view(), name='voucher_excel'),
    path('accounts/excel/', excel_views.AccountCodeExcelView.as_view(), name='accountcode_excel'),
    path('fixed-costs/excel/', excel_views.FixedCostExcelView.as_view(), name='fixedcost_excel'),
    path('receivables/excel/', excel_views.ARExcelView.as_view(), name='ar_excel'),
    path('payables/excel/', excel_views.APExcelView.as_view(), name='ap_excel'),
    path('approvals/excel/', excel_views.ApprovalExcelView.as_view(), name='approval_excel'),
    path('withholding/excel/', excel_views.WithholdingTaxExcelView.as_view(), name='withholding_excel'),
]
