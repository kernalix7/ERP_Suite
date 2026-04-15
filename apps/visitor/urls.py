from django.urls import path
from . import views
from apps.core.excel_views import VisitRequestExcelView, VisitLogExcelView

app_name = 'visitor'

urlpatterns = [
    path('export/visit-requests/', VisitRequestExcelView.as_view(), name='visit_request_excel'),
    path('export/visit-logs/', VisitLogExcelView.as_view(), name='visit_log_excel'),
    path('', views.VisitRequestListView.as_view(), name='visit_request_list'),
    path('create/', views.VisitRequestCreateView.as_view(), name='visit_request_create'),
    path('logs/', views.VisitLogListView.as_view(), name='visit_log_list'),
    path('check-in/', views.VisitCheckInView.as_view(), name='check_in'),
    path('visitors/', views.VisitorListView.as_view(), name='visitor_list'),
    path('visitors/create/', views.VisitorCreateView.as_view(), name='visitor_create'),
    path('purposes/', views.VisitorPurposeListView.as_view(), name='purpose_list'),
    path('purposes/create/', views.VisitorPurposeCreateView.as_view(), name='purpose_create'),
    path('<int:pk>/', views.VisitRequestDetailView.as_view(), name='visit_request_detail'),
    path('<int:pk>/approve/', views.VisitRequestApproveView.as_view(), name='visit_request_approve'),
    path('logs/<int:pk>/check-out/', views.VisitCheckOutView.as_view(), name='check_out'),
]
