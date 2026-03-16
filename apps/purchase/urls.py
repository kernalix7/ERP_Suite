from django.urls import path

from . import views

app_name = 'purchase'

urlpatterns = [
    # 발주서
    path('orders/', views.PurchaseOrderListView.as_view(), name='po_list'),
    path('orders/create/', views.PurchaseOrderCreateView.as_view(), name='po_create'),
    path('orders/<int:pk>/', views.PurchaseOrderDetailView.as_view(), name='po_detail'),
    path('orders/<int:pk>/edit/', views.PurchaseOrderUpdateView.as_view(), name='po_update'),
    # 입고
    path('receipts/', views.GoodsReceiptListView.as_view(), name='receipt_list'),
    path('orders/<int:pk>/receive/', views.GoodsReceiptCreateView.as_view(), name='receipt_create'),
    path('receipts/<int:pk>/', views.GoodsReceiptDetailView.as_view(), name='receipt_detail'),
]
