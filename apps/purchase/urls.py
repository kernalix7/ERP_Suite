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
    path('receipts/<str:slug>/inspect/', views.GoodsReceiptInspectView.as_view(), name='receipt_inspect'),
    # 견적요청 (RFQ)
    path('rfq/', views.RFQListView.as_view(), name='rfq_list'),
    path('rfq/excel/', excel_views.RFQExcelView.as_view(), name='rfq_excel'),
    path('rfq/create/', views.RFQCreateView.as_view(), name='rfq_create'),
    path('rfq/<str:slug>/', views.RFQDetailView.as_view(), name='rfq_detail'),
    path('rfq/<str:slug>/response/', views.RFQResponseCreateView.as_view(), name='rfq_response_create'),
    path('rfq/<str:slug>/compare/', views.RFQCompareView.as_view(), name='rfq_compare'),
    path('rfq/<str:slug>/convert/', views.RFQConvertView.as_view(), name='rfq_convert'),
    # 공급처 평가
    path('vendor-scores/', views.VendorScoreListView.as_view(), name='vendor_score_list'),
    path('vendor-scores/excel/', excel_views.VendorScoreExcelView.as_view(), name='vendor_score_excel'),
    path('vendor-scores/create/', views.VendorScoreCreateView.as_view(), name='vendor_score_create'),
    path('vendor-scores/scorecard/', views.VendorScoreCardView.as_view(), name='vendor_scorecard'),
]
