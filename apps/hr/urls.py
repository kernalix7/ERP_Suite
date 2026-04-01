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
    path('positions/<int:pk>/edit/', views.PositionUpdateView.as_view(), name='position_update'),
    # 외부 협력업체
    path('external-companies/', views.ExternalCompanyListView.as_view(), name='external_company_list'),
    path('external-companies/create/', views.ExternalCompanyCreateView.as_view(), name='external_company_create'),
    path('external-companies/<int:pk>/edit/', views.ExternalCompanyUpdateView.as_view(), name='external_company_update'),
    # 직원
    path('employees/', views.EmployeeListView.as_view(), name='employee_list'),
    path('employees/create/', views.EmployeeCreateView.as_view(), name='employee_create'),
    path('employees/<str:slug>/', views.EmployeeDetailView.as_view(), name='employee_detail'),
    path('employees/<str:slug>/edit/', views.EmployeeUpdateView.as_view(), name='employee_update'),
    # 인사발령
    path('personnel-actions/', views.PersonnelActionListView.as_view(), name='action_list'),
    path('personnel-actions/create/', views.PersonnelActionCreateView.as_view(), name='action_create'),
    # 입퇴사 처리
    path('onboarding/', views.OnboardingView.as_view(), name='onboarding'),
    path('offboarding/', views.OffboardingView.as_view(), name='offboarding'),
    # 급여
    path('payroll/', views.PayrollListView.as_view(), name='payroll_list'),
    path('payroll/create/', views.PayrollCreateView.as_view(), name='payroll_create'),
    path('payroll/bulk-create/', views.PayrollBulkCreateView.as_view(), name='payroll_bulk_create'),
    path('payroll/config/', views.PayrollConfigView.as_view(), name='payroll_config'),
    path('payroll/<int:pk>/', views.PayrollDetailView.as_view(), name='payroll_detail'),
    # 일괄 가져오기
    path('departments/import/', views.DepartmentImportView.as_view(), name='department_import'),
    path('departments/import/sample/', views.DepartmentImportSampleView.as_view(), name='department_import_sample'),
    path('positions/import/', views.PositionImportView.as_view(), name='position_import'),
    path('positions/import/sample/', views.PositionImportSampleView.as_view(), name='position_import_sample'),
    # Excel 내보내기
    path('employees/excel/', excel_views.EmployeeExcelView.as_view(), name='employee_excel'),
    path('departments/excel/', excel_views.DepartmentExcelView.as_view(), name='department_excel'),
    path('personnel-actions/excel/', excel_views.PersonnelActionExcelView.as_view(), name='action_excel'),
]
