from django.urls import path

from . import views

app_name = 'bi'

urlpatterns = [
    # Reports
    path('reports/', views.ReportListView.as_view(), name='report_list'),
    path('reports/create/', views.ReportCreateView.as_view(), name='report_create'),
    path('reports/<int:pk>/', views.ReportUpdateView.as_view(), name='report_update'),
    path('reports/<int:pk>/builder/', views.ReportBuilderView.as_view(), name='report_builder'),
    path('reports/<int:pk>/preview/', views.ReportPreviewView.as_view(), name='report_preview'),
    path('reports/<int:pk>/execute/', views.ReportExecuteView.as_view(), name='report_execute'),
    path('reports/<int:pk>/export/', views.ReportExportView.as_view(), name='report_export'),
    path('reports/<int:pk>/delete/', views.ReportDeleteView.as_view(), name='report_delete'),
    path('reports/<int:pk>/save-config/', views.ReportSaveConfigView.as_view(), name='report_save_config'),
    path('reports/<int:pk>/drill-down/', views.DrillDownView.as_view(), name='report_drill_down'),
    # Dashboards
    path('dashboards/', views.DashboardListView.as_view(), name='dashboard_list'),
    path('dashboards/create/', views.DashboardCreateView.as_view(), name='dashboard_create'),
    path('dashboards/<int:pk>/edit/', views.DashboardEditView.as_view(), name='dashboard_edit'),
    path('dashboards/<int:pk>/delete/', views.DashboardDeleteView.as_view(), name='dashboard_delete'),
    path('dashboards/<int:pk>/save-layout/', views.DashboardSaveLayoutView.as_view(), name='dashboard_save_layout'),
    # Panels
    path('dashboards/<int:dashboard_pk>/panels/create/', views.PanelCreateView.as_view(), name='panel_create'),
    path('dashboards/<int:dashboard_pk>/panels/<int:pk>/delete/', views.PanelDeleteView.as_view(), name='panel_delete'),
    # Data source schema
    path('schema/<str:data_source>/', views.DataSourceSchemaView.as_view(), name='data_source_schema'),
    # Schedules
    path('schedules/', views.ScheduleListView.as_view(), name='schedule_list'),
    path('schedules/create/', views.ScheduleCreateView.as_view(), name='schedule_create'),
    path('schedules/<int:pk>/', views.ScheduleUpdateView.as_view(), name='schedule_update'),
    path('schedules/<int:pk>/delete/', views.ScheduleDeleteView.as_view(), name='schedule_delete'),
]
