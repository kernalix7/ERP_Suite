from django.urls import path
from . import views
from apps.core import excel_views

app_name = 'forecast'

urlpatterns = [
    # 수요예측
    path('', views.ForecastListView.as_view(), name='forecast_list'),
    path('excel/', excel_views.DemandForecastExcelView.as_view(), name='forecast_excel'),
    path('create/', views.ForecastCreateView.as_view(), name='forecast_create'),
    path('<int:pk>/', views.ForecastDetailView.as_view(), name='forecast_detail'),
    path('accuracy/', views.ForecastAccuracyView.as_view(), name='accuracy_dashboard'),

    # 파라미터
    path('parameters/', views.ParameterListView.as_view(), name='parameter_list'),
    path('parameters/create/', views.ParameterCreateView.as_view(), name='parameter_create'),

    # S&OP
    path('sop/', views.SOPMeetingListView.as_view(), name='sop_list'),
    path('sop/excel/', excel_views.SOPMeetingExcelView.as_view(), name='sop_excel'),
    path('sop/create/', views.SOPMeetingCreateView.as_view(), name='sop_create'),
    path('sop/<int:pk>/', views.SOPMeetingDetailView.as_view(), name='sop_detail'),
]
