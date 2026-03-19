from django.urls import path

from . import views
from apps.core import excel_views

app_name = 'hr'

urlpatterns = [
    # 조직도
    path('', views.OrgChartView.as_view(), name='org_chart'),
    # 부서
    path('departments/', views.DepartmentListView.as_view(), name='department_list'),
    path('departments/create/', views.DepartmentCreateView.as_view(), name='department_create'),
    path('departments/<int:pk>/edit/', views.DepartmentUpdateView.as_view(), name='department_update'),
    # 직급
    path('positions/', views.PositionListView.as_view(), name='position_list'),
    path('positions/create/', views.PositionCreateView.as_view(), name='position_create'),
    # 직원
    path('employees/', views.EmployeeListView.as_view(), name='employee_list'),
    path('employees/create/', views.EmployeeCreateView.as_view(), name='employee_create'),
    path('employees/<int:pk>/', views.EmployeeDetailView.as_view(), name='employee_detail'),
    path('employees/<int:pk>/edit/', views.EmployeeUpdateView.as_view(), name='employee_update'),
    # 인사발령
    path('personnel-actions/', views.PersonnelActionListView.as_view(), name='action_list'),
    path('personnel-actions/create/', views.PersonnelActionCreateView.as_view(), name='action_create'),
    # Excel 내보내기
    path('employees/excel/', excel_views.EmployeeExcelView.as_view(), name='employee_excel'),
    path('departments/excel/', excel_views.DepartmentExcelView.as_view(), name='department_excel'),
    path('personnel-actions/excel/', excel_views.PersonnelActionExcelView.as_view(), name='action_excel'),
]
