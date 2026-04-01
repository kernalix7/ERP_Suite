from django.urls import path

from . import views
from apps.core import excel_views

app_name = 'service'

urlpatterns = [
    path('requests/', views.ServiceRequestListView.as_view(), name='request_list'),
    path('requests/create/', views.ServiceRequestCreateView.as_view(), name='request_create'),
    path('requests/<str:slug>/', views.ServiceRequestDetailView.as_view(), name='request_detail'),
    path('requests/<str:slug>/edit/', views.ServiceRequestUpdateView.as_view(), name='request_update'),
    path('repairs/create/', views.RepairRecordCreateView.as_view(), name='repair_create'),
    # 일괄 가져오기
    path('requests/import/', views.ServiceRequestImportView.as_view(), name='request_import'),
    path('requests/import/sample/', views.ServiceRequestImportSampleView.as_view(), name='request_import_sample'),
    # Excel 내보내기
    path('requests/excel/', excel_views.ServiceRequestExcelView.as_view(), name='request_excel'),
]
