from django.urls import path

from . import views

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
    path('plans/<int:pk>/', views.ProductionPlanDetailView.as_view(), name='plan_detail'),
    path('plans/<int:pk>/edit/', views.ProductionPlanUpdateView.as_view(), name='plan_update'),
    # 작업지시
    path('work-orders/', views.WorkOrderListView.as_view(), name='workorder_list'),
    path('work-orders/create/', views.WorkOrderCreateView.as_view(), name='workorder_create'),
    path('work-orders/<int:pk>/', views.WorkOrderDetailView.as_view(), name='workorder_detail'),
    path('work-orders/<int:pk>/edit/', views.WorkOrderUpdateView.as_view(), name='workorder_update'),
    # 생산실적
    path('records/', views.ProductionRecordListView.as_view(), name='record_list'),
    path('records/create/', views.ProductionRecordCreateView.as_view(), name='record_create'),
]
