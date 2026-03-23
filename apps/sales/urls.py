from django.urls import path

from . import views
from apps.core import excel_views

app_name = 'sales'

urlpatterns = [
    # 거래처 분석
    path('partner-analysis/', views.PartnerAnalysisView.as_view(), name='partner_analysis'),
    # 거래처
    path('partners/', views.PartnerListView.as_view(), name='partner_list'),
    path('partners/create/', views.PartnerCreateView.as_view(), name='partner_create'),
    path('partners/<int:pk>/edit/', views.PartnerUpdateView.as_view(), name='partner_update'),
    path('partners/<int:pk>/delete/', views.PartnerDeleteView.as_view(), name='partner_delete'),
    # 고객
    path('customers/', views.CustomerListView.as_view(), name='customer_list'),
    path('customers/create/', views.CustomerCreateView.as_view(), name='customer_create'),
    path('customers/<int:pk>/', views.CustomerDetailView.as_view(), name='customer_detail'),
    path('customers/<int:pk>/edit/', views.CustomerUpdateView.as_view(), name='customer_update'),
    path('customers/<int:pk>/delete/', views.CustomerDeleteView.as_view(), name='customer_delete'),
    # 주문
    path('orders/', views.OrderListView.as_view(), name='order_list'),
    path('orders/create/', views.OrderCreateView.as_view(), name='order_create'),
    path('orders/excel/', views.OrderExcelView.as_view(), name='order_excel'),
    path('orders/<int:pk>/', views.OrderDetailView.as_view(), name='order_detail'),
    path('orders/<int:pk>/edit/', views.OrderUpdateView.as_view(), name='order_update'),
    path('orders/<int:pk>/delete/', views.OrderDeleteView.as_view(), name='order_delete'),
    path('orders/<int:pk>/status/', views.OrderStatusChangeView.as_view(), name='order_status_change'),
    path('orders/<int:pk>/payment/', views.OrderPaymentView.as_view(), name='order_payment'),
    path('orders/<int:pk>/quote-pdf/', views.OrderQuotePDFView.as_view(), name='order_quote_pdf'),
    path('orders/<int:pk>/po-pdf/', views.OrderPurchaseOrderPDFView.as_view(), name='order_po_pdf'),
    # 수수료율
    path('commissions/rates/', views.CommissionRateListView.as_view(), name='commission_rate_list'),
    path('commissions/rates/create/', views.CommissionRateCreateView.as_view(), name='commission_rate_create'),
    path('commissions/rates/<int:pk>/edit/', views.CommissionRateUpdateView.as_view(), name='commission_rate_update'),
    path('commissions/rates/import/', views.CommissionRateImportView.as_view(), name='commission_rate_import'),
    path('commissions/rates/import/sample/', views.CommissionRateImportSampleView.as_view(), name='commission_rate_import_sample'),
    path('commissions/rates/excel/', views.CommissionRateExcelView.as_view(), name='commission_rate_excel'),
    # 수수료내역
    path('commissions/', views.CommissionRecordListView.as_view(), name='commission_list'),
    path('commissions/create/', views.CommissionRecordCreateView.as_view(), name='commission_create'),
    path('commissions/<int:pk>/settle/', views.CommissionRecordSettleView.as_view(), name='commission_settle'),
    path('commissions/summary/', views.CommissionSummaryView.as_view(), name='commission_summary'),
    # 판매제품 통합 관리
    path('sold-products/', views.SoldProductListView.as_view(), name='sold_product_list'),
    path('sold-products/excel/', views.SoldProductExcelView.as_view(), name='sold_product_excel'),
    path('sold-products/<int:pk>/', views.SoldProductDetailView.as_view(), name='sold_product_detail'),
    # 견적서
    path('quotes/', views.QuotationListView.as_view(), name='quote_list'),
    path('quotes/create/', views.QuotationCreateView.as_view(), name='quote_create'),
    path('quotes/<int:pk>/', views.QuotationDetailView.as_view(), name='quote_detail'),
    path('quotes/<int:pk>/edit/', views.QuotationUpdateView.as_view(), name='quote_update'),
    path('quotes/<int:pk>/delete/', views.QuotationDeleteView.as_view(), name='quote_delete'),
    path('quotes/<int:pk>/convert/', views.QuotationConvertView.as_view(), name='quote_convert'),
    path('quotes/import/', views.QuotationImportView.as_view(), name='quote_import'),
    path('quotes/import/sample/', views.QuotationImportSampleView.as_view(), name='quote_import_sample'),
    # 주문 일괄 가져오기
    path('orders/import/', views.OrderImportView.as_view(), name='order_import'),
    path('orders/import/sample/', views.OrderImportSampleView.as_view(), name='order_import_sample'),
    # 택배사
    path('carriers/', views.ShippingCarrierListView.as_view(), name='carrier_list'),
    path('carriers/create/', views.ShippingCarrierCreateView.as_view(), name='carrier_create'),
    path('carriers/<int:pk>/edit/', views.ShippingCarrierUpdateView.as_view(), name='carrier_update'),
    # 배송
    path('shipments/', views.ShipmentListView.as_view(), name='shipment_list'),
    path('orders/<int:order_pk>/ship/', views.ShipmentCreateView.as_view(), name='shipment_create'),
    path('orders/<int:pk>/partial-ship/', views.PartialShipmentView.as_view(), name='partial_shipment'),
    path('shipments/<int:pk>/', views.ShipmentDetailView.as_view(), name='shipment_detail'),
    path('shipments/<int:pk>/edit/', views.ShipmentUpdateView.as_view(), name='shipment_update'),
    path('shipments/<int:pk>/delete/', views.ShipmentDeleteView.as_view(), name='shipment_delete'),
    path('shipments/<int:pk>/tracking/', views.ShipmentTrackingView.as_view(), name='shipment_tracking'),
    path('shipments/import/', views.ShipmentImportView.as_view(), name='shipment_import'),
    path('shipments/import/sample/', views.ShipmentImportSampleView.as_view(), name='shipment_import_sample'),
    # Excel 일괄 가져오기
    path('partners/import/', views.PartnerImportView.as_view(), name='partner_import'),
    path('partners/import/sample/', views.PartnerImportSampleView.as_view(), name='partner_import_sample'),
    path('customers/import/', views.CustomerImportView.as_view(), name='customer_import'),
    path('customers/import/sample/', views.CustomerImportSampleView.as_view(), name='customer_import_sample'),
    # Excel 내보내기
    path('partners/excel/', excel_views.PartnerExcelView.as_view(), name='partner_excel'),
    path('customers/excel/', excel_views.CustomerExcelView.as_view(), name='customer_excel'),
    path('quotes/excel/', excel_views.QuotationExcelView.as_view(), name='quote_excel'),
    path('shipments/excel/', excel_views.ShipmentExcelView.as_view(), name='shipment_excel'),
    path('commissions/excel/', excel_views.CommissionExcelView.as_view(), name='commission_excel'),
]
