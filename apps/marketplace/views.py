from datetime import datetime, timedelta

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, DetailView, TemplateView

from django.db.models import Q

from apps.core.mixins import ManagerRequiredMixin
from .forms import ReconciliationRunForm
from .models import (
    ImportSession, ImportTemplate, MarketplaceOrder, ProductMapping,
    SettlementReconciliation, SyncLog,
)
from .sync_service import (
    sync_orders, fetch_orders_preview, import_selected_orders,
    push_shipping_info, push_return_info,
)


class MarketplaceDashboardView(ManagerRequiredMixin, TemplateView):
    template_name = 'marketplace/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .api_client import get_client
        context['has_config'] = get_client() is not None

        active_orders = MarketplaceOrder.objects.filter(is_active=True)
        context['new_order_count'] = active_orders.filter(status=MarketplaceOrder.Status.NEW).count()
        context['confirmed_count'] = active_orders.filter(status=MarketplaceOrder.Status.CONFIRMED).count()
        context['shipped_count'] = active_orders.filter(status=MarketplaceOrder.Status.SHIPPED).count()
        context['delivered_count'] = active_orders.filter(status=MarketplaceOrder.Status.DELIVERED).count()
        context['total_orders'] = active_orders.count()
        context['recent_orders'] = active_orders.order_by('-ordered_at')[:10]
        context['sync_logs'] = SyncLog.objects.order_by('-started_at')[:5]
        context['last_sync'] = SyncLog.objects.order_by('-started_at').first()
        context['templates'] = ImportTemplate.objects.filter(is_active=True)
        return context


class MarketplaceOrderListView(ManagerRequiredMixin, ListView):
    model = MarketplaceOrder
    template_name = 'marketplace/order_list.html'
    context_object_name = 'orders'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related('erp_order', 'erp_quotation')
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

        period = int(request.POST.get('period', 7))
        from_date = datetime.now() - timedelta(days=period)
        sync_log = sync_orders(user=request.user, from_date=from_date)

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
        from apps.inventory.models import Product

        if not get_client():
            messages.error(request, 'API 설정이 필요합니다. 관리자 설정 → 마켓플레이스에서 API 키를 입력해주세요.')
            return redirect(f"{reverse_lazy('core:system_settings')}?tab=MARKETPLACE")

        # 템플릿 선택 처리
        template_id = request.POST.get('template_id') or None
        template = None
        if template_id:
            template = ImportTemplate.objects.filter(pk=template_id, is_active=True).first()

        period = int(request.POST.get('period', 0))
        if not period and template:
            period = template.default_period
        if not period:
            period = 7

        from_date = datetime.now() - timedelta(days=period)
        preview = fetch_orders_preview(
            from_date=from_date,
            template_id=int(template_id) if template_id else None,
        )

        # 세션에 저장 (import 시 재사용)
        request.session['sync_preview_orders'] = preview
        request.session['sync_template_id'] = int(template_id) if template_id else None

        new_orders = [o for o in preview if not o.get('already_imported')]
        matched_count = sum(1 for o in new_orders if o.get('match_type') in ('saved', 'exact'))
        unmatched_count = sum(1 for o in new_orders if o.get('match_type') in ('partial', 'none'))

        products = Product.objects.filter(is_active=True).order_by('name').values('pk', 'name')

        return self.render_to_response({
            'orders': preview,
            'new_count': len(new_orders),
            'existing_count': sum(1 for o in preview if o.get('already_imported')),
            'matched_count': matched_count,
            'unmatched_count': unmatched_count,
            'products': list(products),
            'period': period,
            'templates': ImportTemplate.objects.filter(is_active=True),
            'selected_template': template,
        })


class ImportSelectedView(ManagerRequiredMixin, View):
    """선택된 주문만 가져오기 — 수동 매칭 + 매핑 규칙 저장"""

    def post(self, request):
        selected_ids = request.POST.getlist('selected_orders')
        if not selected_ids:
            messages.warning(request, '가져올 주문을 선택해주세요.')
            return HttpResponseRedirect(reverse_lazy('marketplace:sync_preview'))

        # 세션에서 미리보기 데이터 가져오기
        preview_orders = request.session.pop('sync_preview_orders', [])
        template_id = request.session.pop('sync_template_id', None)
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

        # POST에서 수동 매칭 정보 주입 + 매핑 규칙 저장
        # 템플릿 저장용 매핑 정보 수집
        mapping_pairs = []
        for order_data in orders_to_import:
            store_id = order_data.get('store_order_id', '')
            manual_product_id = request.POST.get(f'product_for_{store_id}')
            if manual_product_id:
                order_data['matched_product_id'] = int(manual_product_id)

            product_id = order_data.get('matched_product_id')
            if product_id:
                mapping_pairs.append({
                    'store_product_name': order_data.get('product_name', ''),
                    'store_option_name': order_data.get('option_name', ''),
                    'product_id': product_id,
                })

            # 개별 규칙 저장 체크 (기존 템플릿 또는 전역)
            save_rule = request.POST.get(f'save_rule_{store_id}')
            if save_rule and product_id:
                ProductMapping.objects.update_or_create(
                    template_id=template_id,
                    store_product_name=order_data.get('product_name', ''),
                    store_option_name=order_data.get('option_name', ''),
                    defaults={
                        'product_id': product_id,
                        'created_by': request.user,
                    },
                )

        sync_log = import_selected_orders(
            orders_data=orders_to_import,
            user=request.user,
        )

        # 결과를 세션에 저장 (결과 페이지에서 템플릿 저장 제공)
        request.session['import_result'] = {
            'success_count': sync_log.success_count,
            'error_count': sync_log.error_count,
            'mapping_pairs': mapping_pairs,
            'template_id': template_id,
        }

        return HttpResponseRedirect(reverse_lazy('marketplace:import_result'))


class ImportResultView(ManagerRequiredMixin, TemplateView):
    """가져오기 결과 + 템플릿 저장 제안"""
    template_name = 'marketplace/import_result.html'

    def get(self, request, *args, **kwargs):
        result = request.session.get('import_result')
        if not result:
            return HttpResponseRedirect(reverse_lazy('marketplace:dashboard'))

        context = self.get_context_data(**kwargs)
        context['success_count'] = result.get('success_count', 0)
        context['error_count'] = result.get('error_count', 0)
        context['mapping_count'] = len(result.get('mapping_pairs', []))
        context['has_mappings'] = context['mapping_count'] > 0
        context['template_id'] = result.get('template_id')
        context['store_types'] = ImportTemplate.StoreType.choices
        return self.render_to_response(context)


class SaveTemplateView(ManagerRequiredMixin, View):
    """가져오기 결과에서 템플릿으로 저장"""

    def post(self, request):
        result = request.session.pop('import_result', None)
        if not result:
            messages.error(request, '저장할 데이터가 없습니다.')
            return HttpResponseRedirect(reverse_lazy('marketplace:dashboard'))

        template_name = request.POST.get('template_name', '').strip()
        store_type = request.POST.get('store_type', 'OTHER')
        default_period = int(request.POST.get('default_period', 7))

        if not template_name:
            messages.error(request, '템플릿명을 입력해주세요.')
            request.session['import_result'] = result
            return HttpResponseRedirect(reverse_lazy('marketplace:import_result'))

        existing_template_id = result.get('template_id')
        mapping_pairs = result.get('mapping_pairs', [])

        if existing_template_id:
            # 기존 템플릿에 새 매핑 추가
            template = ImportTemplate.objects.filter(
                pk=existing_template_id, is_active=True,
            ).first()
            if template:
                template.name = template_name
                template.store_type = store_type
                template.default_period = default_period
                template.save(update_fields=['name', 'store_type', 'default_period', 'updated_at'])
            else:
                template = ImportTemplate.objects.create(
                    name=template_name,
                    store_type=store_type,
                    default_period=default_period,
                    created_by=request.user,
                )
        else:
            template = ImportTemplate.objects.create(
                name=template_name,
                store_type=store_type,
                default_period=default_period,
                created_by=request.user,
            )

        # 매핑 일괄 저장
        for pair in mapping_pairs:
            ProductMapping.objects.update_or_create(
                template=template,
                store_product_name=pair['store_product_name'],
                store_option_name=pair['store_option_name'],
                defaults={
                    'product_id': pair['product_id'],
                    'created_by': request.user,
                },
            )

        messages.success(
            request,
            f'템플릿 "{template.name}" 저장 완료 ({len(mapping_pairs)}건 매핑)',
        )
        return HttpResponseRedirect(reverse_lazy('marketplace:order_list'))


# === Import Wizard (6-stage) ===

class WizardFetchView(ManagerRequiredMixin, TemplateView):
    """1단계: API 조회 or Excel 업로드"""
    template_name = 'marketplace/wizard/fetch.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['store_types'] = ImportTemplate.StoreType.choices
        return context

    def post(self, request):
        from .wizard_service import WizardService
        ws = WizardService()

        source_type = request.POST.get('source_type', 'API')
        platform = request.POST.get('platform', '')
        session = ws.create_session(source_type, platform, request.user)

        if source_type == 'API':
            period = int(request.POST.get('period', 7))
            from_date = datetime.now() - timedelta(days=period)
            count = ws.fetch_from_api(session, from_date, None, user=request.user)
            if count == 0:
                messages.warning(request, '신규 주문이 없습니다.')
                return redirect('marketplace:wizard_fetch')
        else:
            uploaded_file = request.FILES.get('excel_file')
            if not uploaded_file:
                messages.error(request, '엑셀 파일을 선택해주세요.')
                return redirect('marketplace:wizard_fetch')
            store_type = request.POST.get('store_type', 'OTHER')
            try:
                count = ws.fetch_from_excel(session, uploaded_file, store_type, user=request.user)
            except ValueError as e:
                messages.error(request, str(e))
                return redirect('marketplace:wizard_fetch')
            if count == 0:
                messages.warning(request, '신규 주문이 없습니다.')
                return redirect('marketplace:wizard_fetch')

        ws.advance_stage(session)
        return redirect('marketplace:wizard_preview', session_id=session.pk)


class WizardPreviewView(ManagerRequiredMixin, TemplateView):
    """2단계: 미리보기 + 선택"""
    template_name = 'marketplace/wizard/preview.html'

    def get_context_data(self, **kwargs):
        from .wizard_service import WizardService
        from apps.inventory.models import Product
        context = super().get_context_data(**kwargs)
        ws = WizardService()
        session = ws.get_session(self.kwargs['session_id'])
        context['session'] = session
        context['preview'] = ws.get_preview_data(session) if session else []
        context['products'] = list(
            Product.objects.filter(is_active=True).order_by('name').values('pk', 'name'),
        )
        context['summary'] = ws.get_summary(session) if session else {}
        return context

    def post(self, request, session_id):
        from .wizard_service import WizardService
        ws = WizardService()
        session = ws.get_session(session_id)
        if not session:
            messages.error(request, '세션이 만료되었습니다.')
            return redirect('marketplace:dashboard')

        # 건너뛸 주문 처리
        all_order_ids = [
            int(pk) for pk in request.POST.getlist('all_order_ids')
        ]
        selected_ids = [
            int(pk) for pk in request.POST.getlist('selected_orders')
        ]
        skipped_ids = [pk for pk in all_order_ids if pk not in selected_ids]
        ws.update_selections(session, selected_ids, skipped_ids)

        ws.advance_stage(session)
        return redirect('marketplace:wizard_customers', session_id=session.pk)


class WizardCustomerView(ManagerRequiredMixin, TemplateView):
    """3단계: 고객 등록"""
    template_name = 'marketplace/wizard/customers.html'

    def get_context_data(self, **kwargs):
        from .wizard_service import WizardService
        context = super().get_context_data(**kwargs)
        ws = WizardService()
        session = ws.get_session(self.kwargs['session_id'])
        context['session'] = session
        context['summary'] = ws.get_summary(session) if session else {}
        return context

    def post(self, request, session_id):
        from .wizard_service import WizardService
        ws = WizardService()
        session = ws.get_session(session_id)
        if not session:
            messages.error(request, '세션이 만료되었습니다.')
            return redirect('marketplace:dashboard')

        success, errors = ws.register_customers(session, user=request.user)
        messages.info(request, f'고객 등록: {success}건 성공, {errors}건 실패')
        ws.advance_stage(session)
        return redirect('marketplace:wizard_quotations', session_id=session.pk)


class WizardQuotationView(ManagerRequiredMixin, TemplateView):
    """4단계: 견적 생성"""
    template_name = 'marketplace/wizard/quotations.html'

    def get_context_data(self, **kwargs):
        from .wizard_service import WizardService
        context = super().get_context_data(**kwargs)
        ws = WizardService()
        session = ws.get_session(self.kwargs['session_id'])
        context['session'] = session
        context['summary'] = ws.get_summary(session) if session else {}
        context['orders'] = session.orders.filter(
            is_active=True,
        ).exclude(import_status='SKIPPED').select_related('erp_quotation') if session else []
        return context

    def post(self, request, session_id):
        from .wizard_service import WizardService
        ws = WizardService()
        session = ws.get_session(session_id)
        if not session:
            messages.error(request, '세션이 만료되었습니다.')
            return redirect('marketplace:dashboard')

        success, errors = ws.create_quotations(session, user=request.user)
        messages.info(request, f'견적 생성: {success}건 성공, {errors}건 실패')
        ws.advance_stage(session)
        return redirect('marketplace:wizard_orders', session_id=session.pk)


class WizardOrderView(ManagerRequiredMixin, TemplateView):
    """5단계: 주문 전환"""
    template_name = 'marketplace/wizard/orders.html'

    def get_context_data(self, **kwargs):
        from .wizard_service import WizardService
        context = super().get_context_data(**kwargs)
        ws = WizardService()
        session = ws.get_session(self.kwargs['session_id'])
        context['session'] = session
        context['summary'] = ws.get_summary(session) if session else {}
        context['orders'] = session.orders.filter(
            is_active=True,
        ).exclude(import_status__in=['SKIPPED', 'ERROR']).select_related(
            'erp_quotation', 'erp_order',
        ) if session else []
        return context

    def post(self, request, session_id):
        from .wizard_service import WizardService
        ws = WizardService()
        session = ws.get_session(session_id)
        if not session:
            messages.error(request, '세션이 만료되었습니다.')
            return redirect('marketplace:dashboard')

        success, errors = ws.convert_to_orders(session, user=request.user)
        messages.info(request, f'주문 전환: {success}건 성공, {errors}건 실패')
        ws.advance_stage(session)
        return redirect('marketplace:wizard_done', session_id=session.pk)


class WizardDoneView(ManagerRequiredMixin, TemplateView):
    """6단계: 완료"""
    template_name = 'marketplace/wizard/done.html'

    def get_context_data(self, **kwargs):
        from .wizard_service import WizardService
        context = super().get_context_data(**kwargs)
        ws = WizardService()
        session = ws.get_session(self.kwargs['session_id'])
        context['session'] = session
        context['summary'] = ws.get_summary(session) if session else {}
        context['completed_orders'] = session.orders.filter(
            is_active=True, import_status='ORDER_DONE',
        ).select_related('erp_order') if session else []
        context['error_orders'] = session.orders.filter(
            is_active=True, import_status='ERROR',
        ) if session else []
        return context


# === Reverse Sync (ERP → Marketplace) ===


class PushShipmentView(ManagerRequiredMixin, View):
    """배송정보를 마켓플레이스로 역전송"""

    def post(self, request, slug):
        order = MarketplaceOrder.objects.filter(
            store_order_id=slug, is_active=True,
        ).first()
        if not order:
            messages.error(request, '주문을 찾을 수 없습니다.')
            return HttpResponseRedirect(reverse_lazy('marketplace:order_list'))

        if not order.delivery_company or not order.tracking_number:
            messages.error(request, '택배사와 운송장번호가 입력되어야 합니다.')
            return HttpResponseRedirect(
                reverse_lazy('marketplace:order_detail', kwargs={'slug': slug}),
            )

        from django.conf import settings as _settings
        from .tasks import push_shipping_async

        eager = getattr(_settings, 'CELERY_TASK_ALWAYS_EAGER', False)
        if eager:
            result = push_shipping_async.apply(args=[order.pk]).result
            if result:
                messages.success(request, f'배송정보 전송 완료: {order.store_order_id}')
            else:
                messages.error(request, f'배송정보 전송 실패: {order.store_order_id}')
        else:
            push_shipping_async.delay(order.pk)
            messages.info(
                request,
                f'배송정보 전송이 큐에 등록되었습니다: {order.store_order_id} '
                '(실패 시 자동 재시도됨)',
            )

        return HttpResponseRedirect(
            reverse_lazy('marketplace:order_detail', kwargs={'slug': slug}),
        )


class PushReturnView(ManagerRequiredMixin, View):
    """반품정보를 마켓플레이스로 역전송"""

    def post(self, request, slug):
        order = MarketplaceOrder.objects.filter(
            store_order_id=slug, is_active=True,
        ).first()
        if not order:
            messages.error(request, '주문을 찾을 수 없습니다.')
            return HttpResponseRedirect(reverse_lazy('marketplace:order_list'))

        reason = request.POST.get('reason', '')
        success = push_return_info(order, reason=reason)
        if success:
            MarketplaceOrder.objects.filter(pk=order.pk).update(
                status=MarketplaceOrder.Status.RETURNED,
            )
            messages.success(request, f'반품정보 전송 완료: {order.store_order_id}')
        else:
            messages.warning(
                request,
                f'반품 전송 결과를 확인해주세요: {order.store_order_id} '
                '(수동 처리가 필요할 수 있습니다)',
            )

        return HttpResponseRedirect(
            reverse_lazy('marketplace:order_detail', kwargs={'slug': slug}),
        )


# === Store Order Search ===

class MarketplaceOrderSearchView(ManagerRequiredMixin, ListView):
    """스토어 주문번호 검색 — AJAX/일반 모두 지원"""
    model = MarketplaceOrder
    template_name = 'marketplace/order_search.html'
    context_object_name = 'orders'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True)
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(store_order_id__icontains=q)
                | Q(product_name__icontains=q)
                | Q(buyer_name__icontains=q)
                | Q(platform_order_id__icontains=q)
            )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs.select_related('erp_order', 'erp_quotation')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '')
        context['status_choices'] = MarketplaceOrder.Status.choices
        context['current_status'] = self.request.GET.get('status', '')
        return context


# === Settlement Reconciliation ===

class ReconciliationListView(ManagerRequiredMixin, ListView):
    """정산 대사 결과 목록"""
    model = SettlementReconciliation
    template_name = 'marketplace/reconciliation_list.html'
    context_object_name = 'reconciliations'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True)
        store = self.request.GET.get('store')
        if store:
            qs = qs.filter(store_module=store)
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        from_date = self.request.GET.get('from_date')
        if from_date:
            qs = qs.filter(settlement_date__gte=from_date)
        to_date = self.request.GET.get('to_date')
        if to_date:
            qs = qs.filter(settlement_date__lte=to_date)
        return qs.select_related('partner')

    def get_context_data(self, **kwargs):
        from apps.store_modules.registry import registry
        context = super().get_context_data(**kwargs)
        context['status_choices'] = SettlementReconciliation.Status.choices
        context['current_status'] = self.request.GET.get('status', '')
        context['current_store'] = self.request.GET.get('store', '')
        context['from_date'] = self.request.GET.get('from_date', '')
        context['to_date'] = self.request.GET.get('to_date', '')
        context['store_choices'] = registry.choices()
        return context


class ReconciliationRunView(ManagerRequiredMixin, TemplateView):
    """정산 대사 실행 폼"""
    template_name = 'marketplace/reconciliation_run.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ReconciliationRunForm()
        return context

    def post(self, request):
        form = ReconciliationRunForm(request.POST)
        if not form.is_valid():
            return self.render_to_response({'form': form})

        from .reconciliation_service import reconcile_settlements
        store_module = form.cleaned_data['store_module']
        from_date = form.cleaned_data['from_date']
        to_date = form.cleaned_data['to_date']

        results = reconcile_settlements(store_module, from_date, to_date)

        matched = sum(1 for r in results if r.status == SettlementReconciliation.Status.MATCHED)
        mismatched = sum(1 for r in results if r.status == SettlementReconciliation.Status.MISMATCHED)
        manual = sum(1 for r in results if r.status == SettlementReconciliation.Status.MANUAL)
        pending = sum(1 for r in results if r.status == SettlementReconciliation.Status.PENDING)

        parts = []
        if matched:
            parts.append(f'일치 {matched}건')
        if mismatched:
            parts.append(f'불일치 {mismatched}건')
        if manual:
            parts.append(f'수동처리 {manual}건')
        if pending:
            parts.append(f'대기 {pending}건')

        if parts:
            messages.success(request, f'정산 대사 완료: {", ".join(parts)}')
        else:
            messages.info(request, '해당 기간에 매칭할 데이터가 없습니다.')

        return HttpResponseRedirect(reverse_lazy('marketplace:reconciliation_list'))
