from django.urls import path
from . import views
from apps.core import excel_views

app_name = 'qms'

urlpatterns = [
    path('', views.QmsDashboardView.as_view(), name='dashboard'),

    # 부적합
    path('nc/', views.NCListView.as_view(), name='nc_list'),
    path('nc/excel/', excel_views.NCExcelView.as_view(), name='nc_excel'),
    path('nc/create/', views.NCCreateView.as_view(), name='nc_create'),
    path('nc/<int:pk>/', views.NCDetailView.as_view(), name='nc_detail'),
    path('nc/<int:pk>/resolve/', views.NCResolveView.as_view(), name='nc_resolve'),

    # CAPA
    path('capa/', views.CAPAListView.as_view(), name='capa_list'),
    path('capa/excel/', excel_views.CAPAExcelView.as_view(), name='capa_excel'),
    path('capa/create/', views.CAPACreateView.as_view(), name='capa_create'),
    path('capa/<int:pk>/', views.CAPADetailView.as_view(), name='capa_detail'),
    path('capa/<int:pk>/verify/', views.CAPAVerifyView.as_view(), name='capa_verify'),

    # 내부감사
    path('audits/', views.AuditListView.as_view(), name='audit_list'),
    path('audits/create/', views.AuditCreateView.as_view(), name='audit_create'),
    path('audits/<int:pk>/', views.AuditDetailView.as_view(), name='audit_detail'),

    # ISO 문서
    path('documents/', views.ISODocListView.as_view(), name='isodoc_list'),
    path('documents/create/', views.ISODocCreateView.as_view(), name='isodoc_create'),
    path('documents/<int:pk>/', views.ISODocDetailView.as_view(), name='isodoc_detail'),
]
