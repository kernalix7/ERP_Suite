from django.urls import path

from . import views
from apps.core import excel_views

app_name = 'attendance'

urlpatterns = [
    path('', views.AttendanceDashboardView.as_view(), name='dashboard'),
    path('check-in/', views.CheckInView.as_view(), name='check_in'),
    path('check-out/', views.CheckOutView.as_view(), name='check_out'),
    path('records/', views.AttendanceListView.as_view(), name='record_list'),
    path('admin/', views.AttendanceAdminView.as_view(), name='admin_list'),
    path('leaves/', views.LeaveRequestListView.as_view(), name='leave_list'),
    path('leaves/create/', views.LeaveRequestCreateView.as_view(), name='leave_create'),
    path('leaves/<int:pk>/approve/', views.LeaveApproveView.as_view(), name='leave_approve'),
    path('balance/', views.LeaveBalanceView.as_view(), name='leave_balance'),
    # Excel 내보내기
    path('records/excel/', excel_views.AttendanceExcelView.as_view(), name='record_excel'),
    path('leaves/excel/', excel_views.LeaveRequestExcelView.as_view(), name='leave_excel'),
    path('balance/excel/', excel_views.LeaveBalanceExcelView.as_view(), name='balance_excel'),
]
