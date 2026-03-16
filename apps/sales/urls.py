from django.urls import path

from . import views

app_name = 'sales'

urlpatterns = [
    # 거래처
    path('partners/', views.PartnerListView.as_view(), name='partner_list'),
    path('partners/create/', views.PartnerCreateView.as_view(), name='partner_create'),
    path('partners/<int:pk>/edit/', views.PartnerUpdateView.as_view(), name='partner_update'),
    # 고객
    path('customers/', views.CustomerListView.as_view(), name='customer_list'),
    path('customers/create/', views.CustomerCreateView.as_view(), name='customer_create'),
    path('customers/<int:pk>/', views.CustomerDetailView.as_view(), name='customer_detail'),
    path('customers/<int:pk>/edit/', views.CustomerUpdateView.as_view(), name='customer_update'),
    # 주문
    path('orders/', views.OrderListView.as_view(), name='order_list'),
    path('orders/create/', views.OrderCreateView.as_view(), name='order_create'),
    path('orders/excel/', views.OrderExcelView.as_view(), name='order_excel'),
    path('orders/<int:pk>/', views.OrderDetailView.as_view(), name='order_detail'),
    path('orders/<int:pk>/edit/', views.OrderUpdateView.as_view(), name='order_update'),
    path('orders/<int:pk>/quote-pdf/', views.OrderQuotePDFView.as_view(), name='order_quote_pdf'),
    path('orders/<int:pk>/po-pdf/', views.OrderPurchaseOrderPDFView.as_view(), name='order_po_pdf'),
    # 수수료율
    path('commissions/rates/', views.CommissionRateListView.as_view(), name='commission_rate_list'),
    path('commissions/rates/create/', views.CommissionRateCreateView.as_view(), name='commission_rate_create'),
    path('commissions/rates/<int:pk>/edit/', views.CommissionRateUpdateView.as_view(), name='commission_rate_update'),
    # 수수료내역
    path('commissions/', views.CommissionRecordListView.as_view(), name='commission_list'),
    path('commissions/create/', views.CommissionRecordCreateView.as_view(), name='commission_create'),
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
    path('quotes/<int:pk>/convert/', views.QuotationConvertView.as_view(), name='quote_convert'),
    # 배송
    path('shipments/', views.ShipmentListView.as_view(), name='shipment_list'),
    path('orders/<int:order_pk>/ship/', views.ShipmentCreateView.as_view(), name='shipment_create'),
    path('shipments/<int:pk>/', views.ShipmentDetailView.as_view(), name='shipment_detail'),
    path('shipments/<int:pk>/edit/', views.ShipmentUpdateView.as_view(), name='shipment_update'),
    # Excel 일괄 가져오기
    path('partners/import/', views.PartnerImportView.as_view(), name='partner_import'),
    path('partners/import/sample/', views.PartnerImportSampleView.as_view(), name='partner_import_sample'),
    path('customers/import/', views.CustomerImportView.as_view(), name='customer_import'),
    path('customers/import/sample/', views.CustomerImportSampleView.as_view(), name='customer_import_sample'),
]
