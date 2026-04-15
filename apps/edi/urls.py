from django.urls import path

from . import views

app_name = 'edi'

urlpatterns = [
    # Dashboard
    path('', views.EDIDashboardView.as_view(), name='dashboard'),

    # Partners
    path('partners/', views.EDIPartnerListView.as_view(), name='partner_list'),
    path('partners/create/', views.EDIPartnerCreateView.as_view(), name='partner_create'),
    path('partners/<int:pk>/edit/', views.EDIPartnerUpdateView.as_view(), name='partner_update'),

    # Document Types
    path('document-types/', views.DocumentTypeListView.as_view(), name='doctype_list'),
    path('document-types/create/', views.DocumentTypeCreateView.as_view(), name='doctype_create'),
    path('document-types/<int:pk>/edit/', views.DocumentTypeUpdateView.as_view(), name='doctype_update'),

    # Transactions
    path('transactions/', views.TransactionListView.as_view(), name='transaction_list'),
    path('transactions/<str:transaction_id>/', views.TransactionDetailView.as_view(), name='transaction_detail'),
    path('transactions/<str:transaction_id>/retry/', views.TransactionRetryView.as_view(), name='transaction_retry'),

    # Mappings
    path('mappings/', views.MappingListView.as_view(), name='mapping_list'),
    path('mappings/create/', views.MappingCreateView.as_view(), name='mapping_create'),
    path('mappings/<int:pk>/edit/', views.MappingUpdateView.as_view(), name='mapping_update'),

    # Schedules
    path('schedules/', views.ScheduleListView.as_view(), name='schedule_list'),
    path('schedules/create/', views.ScheduleCreateView.as_view(), name='schedule_create'),
    path('schedules/<int:pk>/edit/', views.ScheduleUpdateView.as_view(), name='schedule_update'),
]
