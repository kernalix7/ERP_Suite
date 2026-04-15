from django.urls import path
from . import views
from apps.core import excel_views

app_name = 'wms'

urlpatterns = [
    path('', views.WmsDashboardView.as_view(), name='dashboard'),

    # 창고구역
    path('zones/', views.ZoneListView.as_view(), name='zone_list'),
    path('zones/excel/', excel_views.WmsZoneExcelView.as_view(), name='zone_excel'),
    path('zones/create/', views.ZoneCreateView.as_view(), name='zone_create'),
    path('zones/<int:pk>/', views.ZoneDetailView.as_view(), name='zone_detail'),
    path('zones/<int:pk>/edit/', views.ZoneUpdateView.as_view(), name='zone_update'),

    # 보관위치
    path('bins/', views.BinListView.as_view(), name='bin_list'),
    path('bins/create/', views.BinCreateView.as_view(), name='bin_create'),
    path('bins/<int:pk>/edit/', views.BinUpdateView.as_view(), name='bin_update'),

    # 피킹오더
    path('pick-orders/', views.PickOrderListView.as_view(), name='pickorder_list'),
    path('pick-orders/excel/', excel_views.WmsPickOrderExcelView.as_view(), name='pickorder_excel'),
    path('pick-orders/create/', views.PickOrderCreateView.as_view(), name='pickorder_create'),
    path('pick-orders/<int:pk>/', views.PickOrderDetailView.as_view(), name='pickorder_detail'),
    path('pick-orders/<int:pk>/edit/', views.PickOrderUpdateView.as_view(), name='pickorder_update'),

    # 입고적치
    path('putaway/', views.PutAwayListView.as_view(), name='putaway_list'),
    path('putaway/excel/', excel_views.WmsPutAwayExcelView.as_view(), name='putaway_excel'),
    path('putaway/create/', views.PutAwayCreateView.as_view(), name='putaway_create'),
    path('putaway/<int:pk>/', views.PutAwayDetailView.as_view(), name='putaway_detail'),
    path('putaway/<int:pk>/edit/', views.PutAwayUpdateView.as_view(), name='putaway_update'),

    # 웨이브계획
    path('waves/', views.WavePlanListView.as_view(), name='waveplan_list'),
    path('waves/create/', views.WavePlanCreateView.as_view(), name='waveplan_create'),
    path('waves/<int:pk>/', views.WavePlanDetailView.as_view(), name='waveplan_detail'),
]
