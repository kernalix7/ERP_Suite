from django.urls import path

from . import views
from apps.core import excel_views

app_name = 'sales'

urlpatterns = [
    # 거래처 분석
    path('partner-analysis/', views.PartnerAnalysisView.as_view(), name='partner_analysis'),
    # 거래처 — 고정 경로 먼저
    path('partners/', views.PartnerListView.as_view(), name='partner_list'),
    path('partners/create/', views.PartnerCreateView.as_view(), name='partner_create'),
    path('partners/import/', views.PartnerImportView.as_view(), name='partner_import'),
    path('partners/import/sample/', views.PartnerImportSampleView.as_view(), name='partner_import_sample'),
    path('partners/excel/', excel_views.PartnerExcelView.as_view(), name='partner_excel'),
    path('partners/<str:slug>/edit/', views.PartnerUpdateView.as_view(), name='partner_update'),
    path('partners/<str:slug>/delete/', views.PartnerDeleteView.as_view(), name='partner_delete'),
    # 고객 — 고정 경로 먼저
    path('customers/', views.CustomerListView.as_view(), name='customer_list'),
    path('customers/create/', views.CustomerCreateView.as_view(), name='customer_create'),
    path('customers/import/', views.CustomerImportView.as_view(), name='customer_import'),
    path('customers/import/sample/', views.CustomerImportSampleView.as_view(), name='customer_import_sample'),
    path('customers/excel/', excel_views.CustomerExcelView.as_view(), name='customer_excel'),
    path('customers/purchase-excel/', excel_views.CustomerPurchaseExcelView.as_view(), name='customer_purchase_excel'),
    path('customers/<str:slug>/', views.CustomerDetailView.as_view(), name='customer_detail'),
    path('customers/<str:slug>/edit/', views.CustomerUpdateView.as_view(), name='customer_update'),
    path('customers/<str:slug>/delete/', views.CustomerDeleteView.as_view(), name='customer_delete'),
    # 주문 — 고정 경로 먼저
    path('orders/', views.OrderListView.as_view(), name='order_list'),
    path('orders/create/', views.OrderCreateView.as_view(), name='order_create'),
    path('orders/excel/', views.OrderExcelView.as_view(), name='order_excel'),
    path('orders/import/', views.OrderImportView.as_view(), name='order_import'),
    path('orders/import/sample/', views.OrderImportSampleView.as_view(), name='order_import_sample'),
    path('orders/<str:slug>/', views.OrderDetailView.as_view(), name='order_detail'),
    path('orders/<str:slug>/edit/', views.OrderUpdateView.as_view(), name='order_update'),
    path('orders/<str:slug>/delete/', views.OrderDeleteView.as_view(), name='order_delete'),
    path('orders/<str:slug>/status/', views.OrderStatusChangeView.as_view(), name='order_status_change'),
    path('orders/<str:slug>/payment/', views.OrderPaymentView.as_view(), name='order_payment'),
    path('orders/<str:slug>/quote-pdf/', views.OrderQuotePDFView.as_view(), name='order_quote_pdf'),
    path('orders/<str:slug>/po-pdf/', views.OrderPurchaseOrderPDFView.as_view(), name='order_po_pdf'),
    path('orders/<str:order_slug>/ship/', views.ShipmentCreateView.as_view(), name='shipment_create'),
    path('orders/<str:slug>/partial-ship/', views.PartialShipmentView.as_view(), name='partial_shipment'),
    # 견적서 — 고정 경로 먼저
    path('quotes/', views.QuotationListView.as_view(), name='quote_list'),
    path('quotes/create/', views.QuotationCreateView.as_view(), name='quote_create'),
    path('quotes/import/', views.QuotationImportView.as_view(), name='quote_import'),
    path('quotes/import/sample/', views.QuotationImportSampleView.as_view(), name='quote_import_sample'),
    path('quotes/excel/', excel_views.QuotationExcelView.as_view(), name='quote_excel'),
    path('quotes/<str:slug>/', views.QuotationDetailView.as_view(), name='quote_detail'),
    path('quotes/<str:slug>/edit/', views.QuotationUpdateView.as_view(), name='quote_update'),
    path('quotes/<str:slug>/delete/', views.QuotationDeleteView.as_view(), name='quote_delete'),
    path('quotes/<str:slug>/convert/', views.QuotationConvertView.as_view(), name='quote_convert'),
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
    path('commissions/excel/', excel_views.CommissionExcelView.as_view(), name='commission_excel'),
    # 판매제품
    path('sold-products/', views.SoldProductListView.as_view(), name='sold_product_list'),
    path('sold-products/excel/', views.SoldProductExcelView.as_view(), name='sold_product_excel'),
    path('sold-products/<int:pk>/', views.SoldProductDetailView.as_view(), name='sold_product_detail'),
    # 가격규칙
    path('price-rules/', views.PriceRuleListView.as_view(), name='price_rule_list'),
    path('price-rules/create/', views.PriceRuleCreateView.as_view(), name='price_rule_create'),
    path('price-rules/<int:pk>/edit/', views.PriceRuleUpdateView.as_view(), name='price_rule_update'),
    path('price-rules/<int:pk>/delete/', views.PriceRuleDeleteView.as_view(), name='price_rule_delete'),
    # 가격 조회 API
    path('api/price-lookup/', views.PriceLookupView.as_view(), name='price_lookup'),
    # 택배사
    path('carriers/', views.ShippingCarrierListView.as_view(), name='carrier_list'),
    path('carriers/create/', views.ShippingCarrierCreateView.as_view(), name='carrier_create'),
    path('carriers/<int:pk>/edit/', views.ShippingCarrierUpdateView.as_view(), name='carrier_update'),
    # 배송 — 고정 경로 먼저
    path('shipments/', views.ShipmentListView.as_view(), name='shipment_list'),
    path('shipments/import/', views.ShipmentImportView.as_view(), name='shipment_import'),
    path('shipments/import/sample/', views.ShipmentImportSampleView.as_view(), name='shipment_import_sample'),
    path('shipments/excel/', excel_views.ShipmentExcelView.as_view(), name='shipment_excel'),
    path('shipments/<str:slug>/', views.ShipmentDetailView.as_view(), name='shipment_detail'),
    path('shipments/<str:slug>/edit/', views.ShipmentUpdateView.as_view(), name='shipment_update'),
    path('shipments/<str:slug>/delete/', views.ShipmentDeleteView.as_view(), name='shipment_delete'),
    path('shipments/<str:slug>/tracking/', views.ShipmentTrackingView.as_view(), name='shipment_tracking'),
]
