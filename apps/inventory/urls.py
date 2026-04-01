from django.urls import path

from . import views
from apps.core import excel_views

app_name = 'inventory'

urlpatterns = [
    # 제품
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/create/', views.ProductCreateView.as_view(), name='product_create'),
    path('products/<int:pk>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('products/<int:pk>/edit/', views.ProductUpdateView.as_view(), name='product_update'),
    path('products/<int:pk>/delete/', views.ProductDeleteView.as_view(), name='product_delete'),
    path('products/<int:pk>/bom-cost/', views.ProductBOMCostView.as_view(), name='product_bom_cost'),
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
    # 입고/출고 전용 (slug 패턴보다 먼저 등록)
    path('movements/stock-in/', views.StockInCreateView.as_view(), name='stock_in_create'),
    path('movements/stock-out/', views.StockOutCreateView.as_view(), name='stock_out_create'),
    path('movements/<str:slug>/', views.StockMovementDetailView.as_view(), name='movement_detail'),
    # StockLot 관리
    path('stock-lots/', views.StockLotListView.as_view(), name='stocklot_list'),
    path('stock-lots/<str:slug>/', views.StockLotDetailView.as_view(), name='stocklot_detail'),
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
    # 카테고리 일괄 가져오기
    path('categories/import/', views.CategoryImportView.as_view(), name='category_import'),
    path('categories/import/sample/', views.CategoryImportSampleView.as_view(), name='category_import_sample'),
    # 창고 일괄 가져오기
    path('warehouses/import/', views.WarehouseImportView.as_view(), name='warehouse_import'),
    path('warehouses/import/sample/', views.WarehouseImportSampleView.as_view(), name='warehouse_import_sample'),
    # 재고실사
    path('stock-count/', views.StockCountListView.as_view(), name='stockcount_list'),
    path('stock-count/create/', views.StockCountCreateView.as_view(), name='stockcount_create'),
    path('stock-count/<str:slug>/', views.StockCountDetailView.as_view(), name='stockcount_detail'),
    path('stock-count/<str:slug>/update/', views.StockCountUpdateView.as_view(), name='stockcount_update'),
    path('stock-count/<str:slug>/adjust/', views.StockCountAdjustView.as_view(), name='stockcount_adjust'),
    # 창고별 재고
    path('warehouse-stock/', views.WarehouseStockView.as_view(), name='warehouse_stock'),
    # 재고평가
    path('valuation/', views.InventoryValuationView.as_view(), name='valuation'),
    # 바코드/QR
    path('products/<int:pk>/barcode/', views.ProductBarcodeView.as_view(), name='product_barcode'),
    path('products/<int:pk>/barcode/print/', views.ProductBarcodePrintView.as_view(), name='product_barcode_print'),
    path('scan/', views.BarcodeScanView.as_view(), name='barcode_scan'),
    # Excel 내보내기
    path('movements/excel/', excel_views.StockMovementExcelView.as_view(), name='movement_excel'),
    path('stock/excel/', excel_views.StockStatusExcelView.as_view(), name='stock_excel'),
    path('transfers/excel/', excel_views.StockTransferExcelView.as_view(), name='transfer_excel'),
]
