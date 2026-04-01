from django.urls import path

from . import views
from apps.core import excel_views

app_name = 'purchase'

urlpatterns = [
    # 발주서
    path('orders/', views.PurchaseOrderListView.as_view(), name='po_list'),
    path('orders/create/', views.PurchaseOrderCreateView.as_view(), name='po_create'),
    # 일괄 가져오기 (slug 패턴보다 먼저 등록)
    path('orders/import/', views.PurchaseOrderImportView.as_view(), name='po_import'),
    path('orders/import/sample/', views.PurchaseOrderImportSampleView.as_view(), name='po_import_sample'),
    # Excel 내보내기 (slug 패턴보다 먼저 등록)
    path('orders/excel/', excel_views.PurchaseOrderExcelView.as_view(), name='po_excel'),
    # slug 패턴
    path('orders/<str:slug>/', views.PurchaseOrderDetailView.as_view(), name='po_detail'),
    path('orders/<str:slug>/edit/', views.PurchaseOrderUpdateView.as_view(), name='po_update'),
    path('orders/<str:slug>/status/', views.PurchaseOrderStatusChangeView.as_view(), name='po_status_change'),
    path('orders/<str:slug>/delete/', views.PurchaseOrderDeleteView.as_view(), name='po_delete'),
    path('orders/<str:slug>/receive/', views.GoodsReceiptCreateView.as_view(), name='receipt_create'),
    # 입고
    path('receipts/', views.GoodsReceiptListView.as_view(), name='receipt_list'),
    path('receipts/excel/', excel_views.GoodsReceiptExcelView.as_view(), name='receipt_excel'),
    path('receipts/<str:slug>/', views.GoodsReceiptDetailView.as_view(), name='receipt_detail'),
]
