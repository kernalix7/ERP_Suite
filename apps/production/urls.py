from django.urls import path

from . import views
from apps.core import excel_views

app_name = 'production'

urlpatterns = [
    # BOM
    path('bom/', views.BOMListView.as_view(), name='bom_list'),
    path('bom/create/', views.BOMCreateView.as_view(), name='bom_create'),
    path('bom/<int:pk>/', views.BOMDetailView.as_view(), name='bom_detail'),
    path('bom/<int:pk>/edit/', views.BOMUpdateView.as_view(), name='bom_update'),
    # 생산계획
    path('plans/', views.ProductionPlanListView.as_view(), name='plan_list'),
    path('plans/create/', views.ProductionPlanCreateView.as_view(), name='plan_create'),
    path('plans/<str:slug>/', views.ProductionPlanDetailView.as_view(), name='plan_detail'),
    path('plans/<str:slug>/edit/', views.ProductionPlanUpdateView.as_view(), name='plan_update'),
    # 작업지시
    path('work-orders/', views.WorkOrderListView.as_view(), name='workorder_list'),
    path('work-orders/create/', views.WorkOrderCreateView.as_view(), name='workorder_create'),
    path('work-orders/<str:slug>/', views.WorkOrderDetailView.as_view(), name='workorder_detail'),
    path('work-orders/<str:slug>/edit/', views.WorkOrderUpdateView.as_view(), name='workorder_update'),
    # 생산실적
    path('records/', views.ProductionRecordListView.as_view(), name='record_list'),
    path('records/create/', views.ProductionRecordCreateView.as_view(), name='record_create'),
    path('records/<int:pk>/edit/', views.ProductionRecordUpdateView.as_view(), name='record_update'),
    # 일괄 가져오기
    path('bom/import/', views.BOMItemImportView.as_view(), name='bom_import'),
    path('bom/import/sample/', views.BOMItemImportSampleView.as_view(), name='bom_import_sample'),
    # MRP (자재 소요량 계획)
    path('mrp/', views.MRPView.as_view(), name='mrp'),
    # 품질검수
    path('qc/', views.QualityInspectionListView.as_view(), name='qc_list'),
    path('qc/create/', views.QualityInspectionCreateView.as_view(), name='qc_create'),
    path('qc/<str:slug>/', views.QualityInspectionDetailView.as_view(), name='qc_detail'),
    path('qc/<str:slug>/edit/', views.QualityInspectionUpdateView.as_view(), name='qc_update'),
    # 표준원가
    path(
        'standard-cost/',
        views.StandardCostListView.as_view(),
        name='stdcost_list',
    ),
    path(
        'standard-cost/create/',
        views.StandardCostCreateView.as_view(),
        name='stdcost_create',
    ),
    path(
        'standard-cost/<int:pk>/',
        views.StandardCostDetailView.as_view(),
        name='stdcost_detail',
    ),
    # 원가차이 분석
    path(
        'cost-variance/',
        views.CostVarianceView.as_view(),
        name='cost_variance',
    ),
    # Excel 내보내기
    path('bom/excel/', excel_views.BOMExcelView.as_view(), name='bom_excel'),
    path('plans/excel/', excel_views.ProductionPlanExcelView.as_view(), name='plan_excel'),
    path('work-orders/excel/', excel_views.WorkOrderExcelView.as_view(), name='workorder_excel'),
    path('records/excel/', excel_views.ProductionRecordExcelView.as_view(), name='record_excel'),
]
