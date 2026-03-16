from django.urls import path

from . import views

app_name = 'inventory'

urlpatterns = [
    # 제품
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/create/', views.ProductCreateView.as_view(), name='product_create'),
    path('products/<int:pk>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('products/<int:pk>/edit/', views.ProductUpdateView.as_view(), name='product_update'),
    path('products/<int:pk>/delete/', views.ProductDeleteView.as_view(), name='product_delete'),
    # 카테고리
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/create/', views.CategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category_update'),
    # 창고
    path('warehouses/', views.WarehouseListView.as_view(), name='warehouse_list'),
    path('warehouses/create/', views.WarehouseCreateView.as_view(), name='warehouse_create'),
    path('warehouses/<int:pk>/edit/', views.WarehouseUpdateView.as_view(), name='warehouse_update'),
    # 입출고
    path('movements/', views.StockMovementListView.as_view(), name='movement_list'),
    path('movements/create/', views.StockMovementCreateView.as_view(), name='movement_create'),
    path('movements/<int:pk>/', views.StockMovementDetailView.as_view(), name='movement_detail'),
    # 재고현황
    path('stock/', views.StockStatusView.as_view(), name='stock_status'),
    # 창고간 이동
    path('transfers/', views.StockTransferListView.as_view(), name='transfer_list'),
    path('transfers/create/', views.StockTransferCreateView.as_view(), name='transfer_create'),
    # Excel 다운로드
    path('products/excel/', views.ProductExcelView.as_view(), name='product_excel'),
    # Excel 일괄 가져오기
    path('products/import/', views.ProductImportView.as_view(), name='product_import'),
    path('products/import/sample/', views.ProductImportSampleView.as_view(), name='product_import_sample'),
    # 바코드/QR
    path('products/<int:pk>/barcode/', views.ProductBarcodeView.as_view(), name='product_barcode'),
    path('products/<int:pk>/barcode/print/', views.ProductBarcodePrintView.as_view(), name='product_barcode_print'),
    path('scan/', views.BarcodeScanView.as_view(), name='barcode_scan'),
]
