from django.contrib import messages
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, DetailView, TemplateView

from apps.core.mixins import ManagerRequiredMixin
from .models import MarketplaceOrder, SyncLog
from .sync_service import sync_orders, fetch_orders_preview, import_selected_orders


class MarketplaceDashboardView(ManagerRequiredMixin, TemplateView):
    template_name = 'marketplace/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .api_client import get_client
        context['has_config'] = get_client() is not None
        context['recent_logs'] = SyncLog.objects.all()[:10]
        context['order_counts'] = (
            MarketplaceOrder.objects.filter(is_active=True).values('status')
            .annotate(count=Count('id'))
            .order_by('status')
        )
        context['total_orders'] = MarketplaceOrder.objects.filter(is_active=True).count()
        return context


class MarketplaceOrderListView(ManagerRequiredMixin, ListView):
    model = MarketplaceOrder
    template_name = 'marketplace/order_list.html'
    context_object_name = 'orders'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True)
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs


class MarketplaceOrderDetailView(ManagerRequiredMixin, DetailView):
    model = MarketplaceOrder
    template_name = 'marketplace/order_detail.html'
    context_object_name = 'order'
    slug_field = 'store_order_id'
    slug_url_kwarg = 'slug'


class MarketplaceConfigView(ManagerRequiredMixin, View):
    """스토어 설정 → 관리자 설정 마켓플레이스 탭으로 리다이렉트"""

    def get(self, request):
        return redirect(f"{reverse_lazy('core:system_settings')}?tab=MARKETPLACE")

    def post(self, request):
        return redirect(f"{reverse_lazy('core:system_settings')}?tab=MARKETPLACE")


class SyncLogListView(ManagerRequiredMixin, ListView):
    model = SyncLog
    template_name = 'marketplace/sync_log_list.html'
    context_object_name = 'logs'
    paginate_by = 20


class ManualSyncView(ManagerRequiredMixin, View):
    def post(self, request):
        from .api_client import get_client
        if not get_client():
            messages.error(request, 'API 설정이 필요합니다. 관리자 설정 → 마켓플레이스에서 API 키를 입력해주세요.')
            return redirect(f"{reverse_lazy('core:system_settings')}?tab=MARKETPLACE")

        sync_log = sync_orders(user=request.user)

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


class SyncPreviewView(ManagerRequiredMixin, TemplateView):
    """주문 미리보기 — API에서 조회만 하고 저장하지 않음"""
    template_name = 'marketplace/sync_preview.html'

    def post(self, request):
        from .api_client import get_client
        if not get_client():
            messages.error(request, 'API 설정이 필요합니다. 관리자 설정 → 마켓플레이스에서 API 키를 입력해주세요.')
            return redirect(f"{reverse_lazy('core:system_settings')}?tab=MARKETPLACE")

        preview = fetch_orders_preview()
        # 세션에 저장 (import 시 재사용)
        request.session['sync_preview_orders'] = preview
        return self.render_to_response({
            'orders': preview,
            'new_count': sum(1 for o in preview if not o.get('already_imported')),
            'existing_count': sum(1 for o in preview if o.get('already_imported')),
        })


class ImportSelectedView(ManagerRequiredMixin, View):
    """선택된 주문만 가져오기"""

    def post(self, request):
        selected_ids = request.POST.getlist('selected_orders')
        if not selected_ids:
            messages.warning(request, '가져올 주문을 선택해주세요.')
            return HttpResponseRedirect(reverse_lazy('marketplace:sync_preview'))

        # 세션에서 미리보기 데이터 가져오기
        preview_orders = request.session.pop('sync_preview_orders', [])
        if not preview_orders:
            messages.error(request, '미리보기 데이터가 만료되었습니다. 다시 조회해주세요.')
            return HttpResponseRedirect(reverse_lazy('marketplace:dashboard'))

        # 선택된 주문만 필터링
        orders_to_import = [
            o for o in preview_orders
            if o.get('store_order_id') in selected_ids
        ]

        if not orders_to_import:
            messages.warning(request, '가져올 주문이 없습니다.')
            return HttpResponseRedirect(reverse_lazy('marketplace:dashboard'))

        sync_log = import_selected_orders(
            orders_data=orders_to_import,
            user=request.user,
        )

        if sync_log.error_count > 0:
            messages.warning(
                request,
                f'가져오기 완료: 성공 {sync_log.success_count}건, 실패 {sync_log.error_count}건',
            )
        else:
            messages.success(
                request,
                f'가져오기 완료: {sync_log.success_count}건 수신',
            )

        return HttpResponseRedirect(reverse_lazy('marketplace:order_list'))
