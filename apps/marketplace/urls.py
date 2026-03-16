from django.urls import path

from . import views

app_name = 'marketplace'

urlpatterns = [
    path('', views.MarketplaceDashboardView.as_view(), name='dashboard'),
    path('orders/', views.MarketplaceOrderListView.as_view(), name='order_list'),
    path('orders/<int:pk>/', views.MarketplaceOrderDetailView.as_view(), name='order_detail'),
    path('config/', views.MarketplaceConfigView.as_view(), name='config'),
    path('sync-logs/', views.SyncLogListView.as_view(), name='sync_log_list'),
    path('sync/', views.ManualSyncView.as_view(), name='manual_sync'),
]
