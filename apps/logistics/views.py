from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from apps.core.mixins import ManagerRequiredMixin

from .forms import (
    DeliveryRouteForm,
    DeliveryZoneForm,
    DriverForm,
    FreightCostForm,
    RouteStopForm,
    VehicleForm,
)
from .models import (
    DeliveryRoute,
    DeliveryZone,
    Driver,
    FreightCost,
    RouteStop,
    Vehicle,
)


# ── Vehicle views ──

class VehicleListView(LoginRequiredMixin, ListView):
    model = Vehicle
    template_name = 'logistics/vehicle_list.html'
    context_object_name = 'vehicles'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True).select_related('driver__user')


class VehicleCreateView(ManagerRequiredMixin, CreateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = 'logistics/vehicle_form.html'
    success_url = reverse_lazy('logistics:vehicle_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class VehicleUpdateView(ManagerRequiredMixin, UpdateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = 'logistics/vehicle_form.html'
    success_url = reverse_lazy('logistics:vehicle_list')


# ── Driver views ──

class DriverListView(LoginRequiredMixin, ListView):
    model = Driver
    template_name = 'logistics/driver_list.html'
    context_object_name = 'drivers'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True).select_related('user')


class DriverCreateView(ManagerRequiredMixin, CreateView):
    model = Driver
    form_class = DriverForm
    template_name = 'logistics/driver_form.html'
    success_url = reverse_lazy('logistics:driver_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class DriverUpdateView(ManagerRequiredMixin, UpdateView):
    model = Driver
    form_class = DriverForm
    template_name = 'logistics/driver_form.html'
    success_url = reverse_lazy('logistics:driver_list')


# ── Route views ──

class RouteListView(LoginRequiredMixin, ListView):
    model = DeliveryRoute
    template_name = 'logistics/route_list.html'
    context_object_name = 'routes'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related('vehicle', 'driver__user')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        date = self.request.GET.get('date')
        if date:
            qs = qs.filter(date=date)
        return qs


class RouteCreateView(ManagerRequiredMixin, CreateView):
    model = DeliveryRoute
    form_class = DeliveryRouteForm
    template_name = 'logistics/route_form.html'
    success_url = reverse_lazy('logistics:route_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class RouteDetailView(LoginRequiredMixin, DetailView):
    model = DeliveryRoute
    template_name = 'logistics/route_detail.html'
    context_object_name = 'route'
    slug_field = 'route_number'
    slug_url_kwarg = 'route_number'

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True).select_related(
            'vehicle', 'driver__user',
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['stops'] = self.object.stops.filter(is_active=True).select_related(
            'partner', 'order',
        ).order_by('sequence')
        ctx['costs'] = self.object.freight_costs.filter(is_active=True)
        ctx['total_freight'] = ctx['costs'].aggregate(total=Sum('amount'))['total'] or 0
        ctx['stop_form'] = RouteStopForm()
        ctx['cost_form'] = FreightCostForm()
        return ctx


class RouteUpdateView(ManagerRequiredMixin, UpdateView):
    model = DeliveryRoute
    form_class = DeliveryRouteForm
    template_name = 'logistics/route_form.html'
    slug_field = 'route_number'
    slug_url_kwarg = 'route_number'

    def get_success_url(self):
        return reverse_lazy('logistics:route_detail', kwargs={'route_number': self.object.route_number})


class RouteStopCreateView(ManagerRequiredMixin, View):
    def post(self, request, route_number):
        route = get_object_or_404(DeliveryRoute, route_number=route_number, is_active=True)
        form = RouteStopForm(request.POST)
        if form.is_valid():
            stop = form.save(commit=False)
            stop.route = route
            stop.created_by = request.user
            stop.save()
        return redirect('logistics:route_detail', route_number=route.route_number)


class FreightCostCreateView(ManagerRequiredMixin, View):
    def post(self, request, route_number):
        route = get_object_or_404(DeliveryRoute, route_number=route_number, is_active=True)
        form = FreightCostForm(request.POST)
        if form.is_valid():
            cost = form.save(commit=False)
            cost.route = route
            cost.created_by = request.user
            cost.save()
        return redirect('logistics:route_detail', route_number=route.route_number)


# ── DeliveryZone views ──

class DeliveryZoneListView(LoginRequiredMixin, ListView):
    model = DeliveryZone
    template_name = 'logistics/zone_list.html'
    context_object_name = 'zones'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class DeliveryZoneCreateView(ManagerRequiredMixin, CreateView):
    model = DeliveryZone
    form_class = DeliveryZoneForm
    template_name = 'logistics/zone_form.html'
    success_url = reverse_lazy('logistics:zone_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class DeliveryZoneUpdateView(ManagerRequiredMixin, UpdateView):
    model = DeliveryZone
    form_class = DeliveryZoneForm
    template_name = 'logistics/zone_form.html'
    success_url = reverse_lazy('logistics:zone_list')


# ── Dashboard ──

class LogisticsDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'logistics/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        routes = DeliveryRoute.objects.filter(is_active=True)
        ctx['planned_count'] = routes.filter(status=DeliveryRoute.RouteStatus.PLANNED).count()
        ctx['in_progress_count'] = routes.filter(status=DeliveryRoute.RouteStatus.IN_PROGRESS).count()
        ctx['completed_count'] = routes.filter(status=DeliveryRoute.RouteStatus.COMPLETED).count()
        ctx['vehicle_available'] = Vehicle.objects.filter(
            is_active=True, status=Vehicle.VehicleStatus.AVAILABLE,
        ).count()
        ctx['recent_routes'] = routes.select_related(
            'vehicle', 'driver__user',
        ).order_by('-date')[:10]
        return ctx
