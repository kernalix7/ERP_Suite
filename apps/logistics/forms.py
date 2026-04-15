from django import forms

from apps.core.forms import BaseForm

from .models import (
    DeliveryRoute,
    DeliveryZone,
    Driver,
    FreightCost,
    RouteStop,
    Vehicle,
)


class DriverForm(BaseForm):
    class Meta:
        model = Driver
        fields = ['user', 'license_number', 'license_type', 'license_expiry',
                  'phone', 'notes']


class VehicleForm(BaseForm):
    class Meta:
        model = Vehicle
        fields = ['name', 'plate_number', 'vehicle_type', 'capacity_kg',
                  'capacity_cbm', 'status', 'driver', 'notes']


class DeliveryZoneForm(BaseForm):
    class Meta:
        model = DeliveryZone
        fields = ['name', 'region', 'base_cost', 'cost_per_kg', 'cost_per_km',
                  'notes']


class DeliveryRouteForm(BaseForm):
    class Meta:
        model = DeliveryRoute
        fields = ['name', 'date', 'vehicle', 'driver', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }


class RouteStopForm(BaseForm):
    class Meta:
        model = RouteStop
        fields = ['sequence', 'order', 'partner', 'address',
                  'estimated_arrival', 'notes']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
            'estimated_arrival': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }


class FreightCostForm(BaseForm):
    class Meta:
        model = FreightCost
        fields = ['cost_type', 'amount', 'description', 'notes']
