from django.urls import path

from apps.core import excel_views
from . import views

app_name = 'document'

urlpatterns = [
    path('', views.DocumentDashboardView.as_view(), name='dashboard'),
    # Category
    path('categories/', views.DocumentCategoryListView.as_view(), name='category_list'),
    path('categories/create/', views.DocumentCategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/edit/', views.DocumentCategoryUpdateView.as_view(), name='category_update'),
    # Document
    path('documents/', views.DocumentListView.as_view(), name='document_list'),
    path('documents/excel/', excel_views.DocumentExcelView.as_view(), name='document_excel'),
    path('documents/create/', views.DocumentCreateView.as_view(), name='document_create'),
    path('documents/search/', views.DocumentSearchView.as_view(), name='document_search'),
    path('documents/<str:slug>/', views.DocumentDetailView.as_view(), name='document_detail'),
    path('documents/<str:slug>/edit/', views.DocumentUpdateView.as_view(), name='document_update'),
    path('documents/<str:slug>/version/', views.DocumentVersionCreateView.as_view(), name='document_version_create'),
    path('documents/<str:slug>/approve-request/', views.DocumentApprovalRequestView.as_view(), name='document_approval_request'),
    # Approval action
    path('approvals/<int:pk>/<str:action>/', views.DocumentApprovalActionView.as_view(), name='approval_action'),
    # Contract
    path('contracts/', views.ContractListView.as_view(), name='contract_list'),
    path('contracts/excel/', excel_views.ContractExcelView.as_view(), name='contract_excel'),
    path('contracts/create/', views.ContractCreateView.as_view(), name='contract_create'),
    path('contracts/calendar/', views.ContractCalendarView.as_view(), name='contract_calendar'),
    path('contracts/<str:slug>/', views.ContractDetailView.as_view(), name='contract_detail'),
    path('contracts/<str:slug>/edit/', views.ContractUpdateView.as_view(), name='contract_update'),
    path('contracts/<str:slug>/terminate/', views.ContractTerminateView.as_view(), name='contract_terminate'),
    path('contracts/<str:slug>/renew/', views.ContractRenewView.as_view(), name='contract_renew'),
    path('contracts/<str:slug>/milestone/', views.ContractMilestoneCreateView.as_view(), name='milestone_create'),
]
