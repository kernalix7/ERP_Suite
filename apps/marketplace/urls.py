from django.urls import path

from . import views
from apps.core import excel_views

app_name = 'marketplace'

urlpatterns = [
    path('', views.MarketplaceDashboardView.as_view(), name='dashboard'),
    path('orders/', views.MarketplaceOrderListView.as_view(), name='order_list'),
    path('orders/search/', views.MarketplaceOrderSearchView.as_view(), name='order_search'),
    path('orders/excel/', excel_views.MarketplaceOrderExcelView.as_view(), name='order_excel'),
    path('orders/<str:slug>/', views.MarketplaceOrderDetailView.as_view(), name='order_detail'),
    path('orders/<str:slug>/push-shipment/', views.PushShipmentView.as_view(), name='push_shipment'),
    path('orders/<str:slug>/push-return/', views.PushReturnView.as_view(), name='push_return'),
    path('config/', views.MarketplaceConfigView.as_view(), name='config'),
    path('sync-logs/', views.SyncLogListView.as_view(), name='sync_log_list'),
    path('sync/', views.ManualSyncView.as_view(), name='manual_sync'),
    path('sync/preview/', views.SyncPreviewView.as_view(), name='sync_preview'),
    path('sync/import/', views.ImportSelectedView.as_view(), name='import_selected'),
    path('sync/result/', views.ImportResultView.as_view(), name='import_result'),
    path('sync/save-template/', views.SaveTemplateView.as_view(), name='save_template'),
    # Import Wizard (6-stage)
    path('wizard/fetch/', views.WizardFetchView.as_view(), name='wizard_fetch'),
    path('wizard/<int:session_id>/preview/', views.WizardPreviewView.as_view(), name='wizard_preview'),
    path('wizard/<int:session_id>/customers/', views.WizardCustomerView.as_view(), name='wizard_customers'),
    path('wizard/<int:session_id>/quotations/', views.WizardQuotationView.as_view(), name='wizard_quotations'),
    path('wizard/<int:session_id>/orders/', views.WizardOrderView.as_view(), name='wizard_orders'),
    path('wizard/<int:session_id>/done/', views.WizardDoneView.as_view(), name='wizard_done'),
    # Settlement Reconciliation
    path('reconciliation/', views.ReconciliationListView.as_view(), name='reconciliation_list'),
    path('reconciliation/run/', views.ReconciliationRunView.as_view(), name='reconciliation_run'),
]
