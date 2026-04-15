from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    DeliveryRoute,
    DeliveryZone,
    Driver,
    FreightCost,
    RouteStop,
    Vehicle,
)


class RouteStopInline(admin.TabularInline):
    model = RouteStop
    extra = 0


class FreightCostInline(admin.TabularInline):
    model = FreightCost
    extra = 0


@admin.register(Driver)
class DriverAdmin(SimpleHistoryAdmin):
    list_display = ('user', 'license_number', 'license_type', 'license_expiry', 'phone')
    search_fields = ('user__username', 'license_number')


@admin.register(Vehicle)
class VehicleAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'plate_number', 'vehicle_type', 'capacity_kg', 'status', 'driver')
    list_filter = ('vehicle_type', 'status')
    search_fields = ('name', 'plate_number')


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'region', 'base_cost', 'cost_per_kg', 'cost_per_km')
    search_fields = ('name', 'region')


@admin.register(DeliveryRoute)
class DeliveryRouteAdmin(SimpleHistoryAdmin):
    list_display = ('route_number', 'name', 'date', 'vehicle', 'driver', 'status',
                    'total_distance_km', 'total_cost')
    list_filter = ('status', 'date')
    search_fields = ('route_number', 'name')
    inlines = [RouteStopInline, FreightCostInline]


@admin.register(RouteStop)
class RouteStopAdmin(SimpleHistoryAdmin):
    list_display = ('route', 'sequence', 'partner', 'status', 'estimated_arrival',
                    'actual_arrival')
    list_filter = ('status',)


@admin.register(FreightCost)
class FreightCostAdmin(SimpleHistoryAdmin):
    list_display = ('route', 'cost_type', 'amount', 'description')
    list_filter = ('cost_type',)
