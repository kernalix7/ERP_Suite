from django.urls import path
from . import views
from apps.core import excel_views

app_name = 'cmms'

urlpatterns = [
    path('', views.CmmsDashboardView.as_view(), name='dashboard'),

    # 설비
    path('equipment/', views.EquipmentListView.as_view(), name='equipment_list'),
    path('equipment/excel/', excel_views.EquipmentExcelView.as_view(), name='equipment_excel'),
    path('equipment/create/', views.EquipmentCreateView.as_view(), name='equipment_create'),
    path('equipment/<int:pk>/', views.EquipmentDetailView.as_view(), name='equipment_detail'),
    path('equipment/<int:pk>/edit/', views.EquipmentUpdateView.as_view(), name='equipment_update'),

    # 보전스케줄
    path('schedules/', views.ScheduleListView.as_view(), name='schedule_list'),
    path('schedules/create/', views.ScheduleCreateView.as_view(), name='schedule_create'),
    path('schedules/<int:pk>/', views.ScheduleDetailView.as_view(), name='schedule_detail'),
    path('schedules/<int:pk>/edit/', views.ScheduleUpdateView.as_view(), name='schedule_update'),

    # 작업지시
    path('work-orders/', views.WorkOrderListView.as_view(), name='workorder_list'),
    path('work-orders/excel/', excel_views.MaintenanceWorkOrderExcelView.as_view(), name='workorder_excel'),
    path('work-orders/create/', views.WorkOrderCreateView.as_view(), name='workorder_create'),
    path('work-orders/<int:pk>/', views.WorkOrderDetailView.as_view(), name='workorder_detail'),
    path('work-orders/<int:pk>/complete/', views.WorkOrderCompleteView.as_view(), name='workorder_complete'),

    # 예비부품
    path('spare-parts/', views.SparePartListView.as_view(), name='sparepart_list'),
    path('spare-parts/excel/', excel_views.SparePartExcelView.as_view(), name='sparepart_excel'),
    path('spare-parts/create/', views.SparePartCreateView.as_view(), name='sparepart_create'),

    # 비가동 기록
    path('downtimes/', views.DowntimeListView.as_view(), name='downtime_list'),
    path('downtimes/create/', views.DowntimeCreateView.as_view(), name='downtime_create'),
]
