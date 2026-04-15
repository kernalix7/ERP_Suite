from django.urls import path

from apps.core import excel_views
from . import views

app_name = 'esg'

urlpatterns = [
    path('', views.ESGDashboardView.as_view(), name='dashboard'),
    # Metric
    path('metrics/', views.ESGMetricListView.as_view(), name='metric_list'),
    path('metrics/create/', views.ESGMetricCreateView.as_view(), name='metric_create'),
    path('metrics/<int:pk>/edit/', views.ESGMetricUpdateView.as_view(), name='metric_update'),
    # Record
    path('records/', views.ESGRecordListView.as_view(), name='record_list'),
    path('records/create/', views.ESGRecordCreateView.as_view(), name='record_create'),
    # Carbon
    path('carbon/', views.CarbonDashboardView.as_view(), name='carbon_dashboard'),
    path('carbon/list/', views.CarbonEmissionListView.as_view(), name='carbon_list'),
    path('carbon/excel/', excel_views.CarbonEmissionExcelView.as_view(), name='carbon_excel'),
    path('carbon/create/', views.CarbonEmissionCreateView.as_view(), name='carbon_create'),
    # Safety Incident
    path('incidents/', views.SafetyIncidentListView.as_view(), name='incident_list'),
    path('incidents/create/', views.SafetyIncidentCreateView.as_view(), name='incident_create'),
    path('incidents/<str:slug>/', views.SafetyIncidentDetailView.as_view(), name='incident_detail'),
    path('incidents/<str:slug>/edit/', views.SafetyIncidentUpdateView.as_view(), name='incident_update'),
    # Compliance
    path('compliance/', views.ComplianceListView.as_view(), name='compliance_list'),
    path('compliance/excel/', excel_views.ComplianceExcelView.as_view(), name='compliance_excel'),
    path('compliance/create/', views.ComplianceCreateView.as_view(), name='compliance_create'),
    path('compliance/<int:pk>/edit/', views.ComplianceUpdateView.as_view(), name='compliance_update'),
    # Report
    path('reports/', views.ESGReportListView.as_view(), name='report_list'),
    path('reports/create/', views.ESGReportCreateView.as_view(), name='report_create'),
    path('reports/<int:pk>/', views.ESGReportDetailView.as_view(), name='report_detail'),
]
