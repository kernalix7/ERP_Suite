from django.urls import path

from . import views

app_name = 'portal'

urlpatterns = [
    # Auth
    path('login/', views.PortalLoginView.as_view(), name='login'),
    path('logout/', views.PortalLogoutView.as_view(), name='logout'),

    # Dashboard
    path('', views.PortalDashboardView.as_view(), name='dashboard'),

    # Customer views
    path('orders/', views.PortalOrderListView.as_view(), name='order_list'),
    path('orders/<str:order_number>/', views.PortalOrderDetailView.as_view(), name='order_detail'),
    path('orders/<str:order_number>/confirm-delivery/', views.PortalDeliveryConfirmView.as_view(), name='delivery_confirm'),
    path('invoices/', views.PortalInvoiceListView.as_view(), name='invoice_list'),

    # Supplier views
    path('supplier/orders/', views.SupplierPOListView.as_view(), name='supplier_po_list'),
    path('supplier/delivery-schedule/', views.SupplierDeliveryScheduleView.as_view(), name='supplier_delivery_schedule'),

    # Notifications
    path('notifications/', views.PortalNotificationListView.as_view(), name='notification_list'),

    # Admin (internal)
    path('admin/users/', views.PortalUserListView.as_view(), name='admin_user_list'),
    path('admin/users/create/', views.PortalUserCreateView.as_view(), name='admin_user_create'),
]
