from django.urls import path
from . import views
from apps.core import excel_views

app_name = 'warranty'

urlpatterns = [
    path('', views.RegistrationListView.as_view(), name='registration_list'),
    path('create/', views.RegistrationCreateView.as_view(), name='registration_create'),
    path('<int:pk>/', views.RegistrationDetailView.as_view(), name='registration_detail'),
    path('<int:pk>/edit/', views.RegistrationUpdateView.as_view(), name='registration_update'),
    # 일괄 가져오기
    path('import/', views.RegistrationImportView.as_view(), name='registration_import'),
    path('import/sample/', views.RegistrationImportSampleView.as_view(), name='registration_import_sample'),
    path('check/', views.SerialCheckView.as_view(), name='serial_check'),
    path('verify/', views.WarrantyVerifyView.as_view(), name='warranty_verify'),
    # Excel 내보내기
    path('excel/', excel_views.WarrantyExcelView.as_view(), name='warranty_excel'),
]
