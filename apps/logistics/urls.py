from django.urls import path

from . import views

app_name = 'logistics'

urlpatterns = [
    # Dashboard
    path('', views.LogisticsDashboardView.as_view(), name='dashboard'),

    # Vehicles
    path('vehicles/', views.VehicleListView.as_view(), name='vehicle_list'),
    path('vehicles/create/', views.VehicleCreateView.as_view(), name='vehicle_create'),
    path('vehicles/<int:pk>/edit/', views.VehicleUpdateView.as_view(), name='vehicle_update'),

    # Drivers
    path('drivers/', views.DriverListView.as_view(), name='driver_list'),
    path('drivers/create/', views.DriverCreateView.as_view(), name='driver_create'),
    path('drivers/<int:pk>/edit/', views.DriverUpdateView.as_view(), name='driver_update'),

    # Routes
    path('routes/', views.RouteListView.as_view(), name='route_list'),
    path('routes/create/', views.RouteCreateView.as_view(), name='route_create'),
    path('routes/<str:route_number>/', views.RouteDetailView.as_view(), name='route_detail'),
    path('routes/<str:route_number>/edit/', views.RouteUpdateView.as_view(), name='route_update'),
    path('routes/<str:route_number>/stop/', views.RouteStopCreateView.as_view(), name='route_stop_create'),
    path('routes/<str:route_number>/cost/', views.FreightCostCreateView.as_view(), name='route_cost_create'),

    # Delivery Zones
    path('zones/', views.DeliveryZoneListView.as_view(), name='zone_list'),
    path('zones/create/', views.DeliveryZoneCreateView.as_view(), name='zone_create'),
    path('zones/<int:pk>/edit/', views.DeliveryZoneUpdateView.as_view(), name='zone_update'),
]
