from django.urls import path
from . import views
from apps.core import excel_views

app_name = 'asset'

urlpatterns = [
    path('', views.AssetListView.as_view(), name='asset_list'),
    path('excel/', excel_views.FixedAssetExcelView.as_view(), name='asset_excel'),
    path('create/', views.AssetCreateView.as_view(), name='asset_create'),
    path('depreciation-run/', views.AssetDepreciationRunView.as_view(), name='depreciation_run'),
    path('categories/', views.AssetCategoryListView.as_view(), name='category_list'),
    path('categories/create/', views.AssetCategoryCreateView.as_view(), name='category_create'),
    path('summary/', views.AssetSummaryView.as_view(), name='summary'),
    path('department-summary/', views.AssetDepartmentSummaryView.as_view(), name='department_summary'),
    path('report/register/', views.AssetRegisterReportView.as_view(), name='register_report'),
    path('report/register/excel/', views.AssetRegisterExcelView.as_view(), name='register_report_excel'),

    # 인증 관리
    path('certifications/', views.CertificationListView.as_view(), name='certification_list'),
    path('certifications/create/', views.CertificationCreateView.as_view(), name='certification_create'),
    path('certifications/<int:pk>/', views.CertificationDetailView.as_view(), name='certification_detail'),

    # 리스 계약
    path('leases/', views.LeaseContractListView.as_view(), name='lease_list'),
    path('leases/create/', views.LeaseContractCreateView.as_view(), name='lease_create'),
    path('leases/<int:pk>/', views.LeaseContractDetailView.as_view(), name='lease_detail'),

    # 자산 실사
    path('audits/', views.AssetAuditListView.as_view(), name='audit_list'),
    path('audits/create/', views.AssetAuditCreateView.as_view(), name='audit_create'),
    path('audits/<int:pk>/', views.AssetAuditDetailView.as_view(), name='audit_detail'),
    path('audits/<int:pk>/execute/', views.AssetAuditExecuteView.as_view(), name='audit_execute'),

    # 위치 관리
    path('locations/', views.LocationListView.as_view(), name='location_list'),
    path('locations/create/', views.LocationCreateView.as_view(), name='location_create'),
    path('locations/<int:pk>/edit/', views.LocationUpdateView.as_view(), name='location_update'),

    # 자산 이관
    path('transfers/', views.AssetTransferListView.as_view(), name='transfer_list'),
    path('transfers/excel/', excel_views.AssetTransferExcelView.as_view(), name='transfer_excel'),

    # QR 코드
    path('qr/print/', views.AssetQRPrintView.as_view(), name='qr_print'),
    path('qr/scan/', views.AssetQRScanView.as_view(), name='qr_scan'),

    # 자산 예약
    path('reservable/', views.ReservableAssetListView.as_view(), name='reservable_asset_list'),
    path('reservable/create/', views.ReservableAssetCreateView.as_view(), name='reservable_asset_create'),
    path('reservable/<int:pk>/', views.ReservableAssetDetailView.as_view(), name='reservable_asset_detail'),
    path('reservations/', views.AssetReservationListView.as_view(), name='reservation_list'),
    path('reservations/create/', views.AssetReservationCreateView.as_view(), name='reservation_create'),
    path('reservations/<int:pk>/', views.AssetReservationDetailView.as_view(), name='reservation_detail'),
    path('reservations/<int:pk>/approve/', views.AssetReservationApproveView.as_view(), name='reservation_approve'),

    # 유지보수
    path('maintenance/', views.AssetMaintenanceListView.as_view(), name='maintenance_list'),
    path('maintenance/create/', views.AssetMaintenanceCreateView.as_view(), name='maintenance_create'),
    path('maintenance/<int:pk>/edit/', views.AssetMaintenanceUpdateView.as_view(), name='maintenance_update'),

    # 개별 자산 (slug 라우트는 맨 마지막)
    path('<str:slug>/', views.AssetDetailView.as_view(), name='asset_detail'),
    path('<str:slug>/edit/', views.AssetUpdateView.as_view(), name='asset_update'),
    path('<str:slug>/dispose/', views.AssetDisposalView.as_view(), name='asset_dispose'),
    path('<str:slug>/transfer/', views.AssetTransferCreateView.as_view(), name='asset_transfer'),
    path('<str:slug>/qr/', views.AssetQRView.as_view(), name='asset_qr'),
]
