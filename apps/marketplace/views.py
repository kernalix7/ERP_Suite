from django.contrib import messages
from django.db.models import Count
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView

from apps.core.mixins import ManagerRequiredMixin
from .models import MarketplaceConfig, MarketplaceOrder, SyncLog
from .forms import MarketplaceConfigForm, MarketplaceOrderForm
from .sync_service import sync_orders


class MarketplaceDashboardView(ManagerRequiredMixin, TemplateView):
    template_name = 'marketplace/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['config'] = MarketplaceConfig.objects.first()
        context['recent_logs'] = SyncLog.objects.all()[:10]
        context['order_counts'] = (
            MarketplaceOrder.objects.values('status')
            .annotate(count=Count('id'))
            .order_by('status')
        )
        context['total_orders'] = MarketplaceOrder.objects.count()
        return context


class MarketplaceOrderListView(ManagerRequiredMixin, ListView):
    model = MarketplaceOrder
    template_name = 'marketplace/order_list.html'
    context_object_name = 'orders'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs


class MarketplaceOrderDetailView(ManagerRequiredMixin, DetailView):
    model = MarketplaceOrder
    template_name = 'marketplace/order_detail.html'
    context_object_name = 'order'


class MarketplaceConfigView(ManagerRequiredMixin, UpdateView):
    model = MarketplaceConfig
    form_class = MarketplaceConfigForm
    template_name = 'marketplace/config_form.html'
    success_url = reverse_lazy('marketplace:dashboard')

    def get_object(self, queryset=None):
        obj = MarketplaceConfig.objects.first()
        if obj is None:
            obj = MarketplaceConfig()
        return obj

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        return self.form_invalid(form)

    def form_valid(self, form):
        if not self.object.pk:
            form.instance.created_by = self.request.user
        form.save()
        return HttpResponseRedirect(self.success_url)


class SyncLogListView(ManagerRequiredMixin, ListView):
    model = SyncLog
    template_name = 'marketplace/sync_log_list.html'
    context_object_name = 'logs'
    paginate_by = 20


class ManualSyncView(ManagerRequiredMixin, View):
    def post(self, request):
        config = MarketplaceConfig.objects.first()
        if not config:
            messages.error(request, '스토어 설정이 필요합니다. 먼저 설정을 완료해주세요.')
            return HttpResponseRedirect(reverse_lazy('marketplace:config'))

        sync_log = sync_orders(config=config, user=request.user)

        if sync_log.error_count > 0:
            messages.warning(
                request,
                f'동기화 완료: 성공 {sync_log.success_count}건, 실패 {sync_log.error_count}건',
            )
        else:
            messages.success(
                request,
                f'동기화 완료: {sync_log.success_count}건 수신',
            )

        return HttpResponseRedirect(reverse_lazy('marketplace:sync_log_list'))
