from django.urls import path
from . import views

app_name = 'asset'

urlpatterns = [
    path('', views.AssetListView.as_view(), name='asset_list'),
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

    # QR 코드
    path('qr/print/', views.AssetQRPrintView.as_view(), name='qr_print'),
    path('qr/scan/', views.AssetQRScanView.as_view(), name='qr_scan'),

    # 개별 자산 (slug 라우트는 맨 마지막)
    path('<str:slug>/', views.AssetDetailView.as_view(), name='asset_detail'),
    path('<str:slug>/edit/', views.AssetUpdateView.as_view(), name='asset_update'),
    path('<str:slug>/dispose/', views.AssetDisposalView.as_view(), name='asset_dispose'),
    path('<str:slug>/transfer/', views.AssetTransferCreateView.as_view(), name='asset_transfer'),
    path('<str:slug>/qr/', views.AssetQRView.as_view(), name='asset_qr'),
]
