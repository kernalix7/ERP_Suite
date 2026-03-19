from django.urls import path

from . import views
from apps.core import excel_views

app_name = 'service'

urlpatterns = [
    path('requests/', views.ServiceRequestListView.as_view(), name='request_list'),
    path('requests/create/', views.ServiceRequestCreateView.as_view(), name='request_create'),
    path('requests/<int:pk>/', views.ServiceRequestDetailView.as_view(), name='request_detail'),
    path('requests/<int:pk>/edit/', views.ServiceRequestUpdateView.as_view(), name='request_update'),
    path('repairs/create/', views.RepairRecordCreateView.as_view(), name='repair_create'),
    # Excel 내보내기
    path('requests/excel/', excel_views.ServiceRequestExcelView.as_view(), name='request_excel'),
]
