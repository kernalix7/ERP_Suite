from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views import View
from django.views.generic import (
    ListView, CreateView, UpdateView, DetailView, TemplateView,
)

from apps.inventory.models import Product

from apps.core.mixins import ManagerRequiredMixin

from .models import PurchaseOrder, PurchaseOrderItem, GoodsReceipt, GoodsReceiptItem, RFQ, RFQItem, RFQResponse, VendorScore


def _product_units_json():
    return {str(p.pk): p.unit or '' for p in Product.objects.filter(is_active=True)}


def _product_prices_json():
    """제품별 원가/단가 JSON (제품 선택 시 자동 반영용)"""
    result = {}
    for p in Product.objects.filter(is_active=True):
        if p.product_type in ('RAW', 'SEMI'):
            result[str(p.pk)] = int(p.cost_price or 0)
        else:
            result[str(p.pk)] = int(p.unit_price or 0)
    return result
from .forms import (
    PurchaseOrderForm, PurchaseOrderItemFormSet,
    GoodsReceiptForm, GoodsReceiptItemForm,
    RFQForm, RFQItemFormSet, RFQResponseForm, VendorScoreForm,
)


# ─── 발주서 ───────────────────────────────────────────────

class PurchaseOrderListView(LoginRequiredMixin, ListView):
    model = PurchaseOrder
    template_name = 'purchase/po_list.html'
    context_object_name = 'orders'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related('partner')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(po_number__icontains=q) | Q(partner__name__icontains=q)
            )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs


class PurchaseOrderCreateView(ManagerRequiredMixin, CreateView):
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'purchase/po_form.html'
    success_url = reverse_lazy('purchase:po_list')

    def get_initial(self):
        initial = super().get_initial()
        from apps.core.utils import generate_document_number
        initial['po_number'] = generate_document_number(PurchaseOrder, 'po_number', 'PO')
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = PurchaseOrderItemFormSet(
                self.request.POST, self.request.FILES,
            )
        else:
            ctx['formset'] = PurchaseOrderItemFormSet()
        ctx['product_units_json'] = _product_units_json()
        ctx['product_prices_json'] = _product_prices_json()
        return ctx

    def form_valid(self, form):
        # 거래처 승인 상태 체크
        partner = form.cleaned_data.get('partner')
        if partner and hasattr(partner, 'approval_status'):
            if partner.approval_status not in ('APPROVED', ''):
                messages.error(
                    self.request,
                    f'거래처 "{partner.name}"이(가) 승인 상태가 아닙니다. '
                    f'(현재: {partner.get_approval_status_display()})',
                )
                return self.form_invalid(form)

        ctx = self.get_context_data()
        formset = ctx['formset']
        if formset.is_valid():
            self.object = form.save(commit=False)
            self.object.created_by = self.request.user
            self.object.save()
            formset.instance = self.object
            formset.save()
            self.object.update_total()
            return redirect(self.get_success_url())
        return self.form_invalid(form)


class PurchaseOrderDetailView(LoginRequiredMixin, DetailView):
    model = PurchaseOrder
    template_name = 'purchase/po_detail.html'
    context_object_name = 'order'
    slug_field = 'po_number'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['items'] = self.object.items.select_related('product').all()
        ctx['receipts'] = (
            self.object.receipts
            .prefetch_related('items__po_item__product').all()
        )
        ctx['status_actions'] = self._build_status_actions()
        return ctx

    def _build_status_actions(self):
        status = self.object.status
        allowed = PurchaseOrder.STATUS_TRANSITIONS.get(status, [])
        action_map = {
            'CONFIRMED': {
                'label': '발주 확정',
                'css': 'btn-primary',
                'confirm': '발주를 확정하시겠습니까?',
                'icon': '<svg class="w-4 h-4 inline mr-1 -mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>',
            },
            'CANCELLED': {
                'label': '발주 취소',
                'css': 'btn-secondary text-red-600',
                'confirm': '발주를 취소하시겠습니까? 이 작업은 되돌릴 수 없습니다.',
                'icon': '<svg class="w-4 h-4 inline mr-1 -mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>',
            },
        }
        actions = []
        for s in allowed:
            if s in action_map:
                actions.append({'value': s, **action_map[s]})
        return actions


class PurchaseOrderDeleteView(ManagerRequiredMixin, View):
    """발주서 삭제 (soft delete, DRAFT만 가능)"""

    def post(self, request, slug):
        order = get_object_or_404(PurchaseOrder, po_number=slug, is_active=True)
        if order.status != 'DRAFT':
            messages.error(request, '작성중 상태의 발주서만 삭제할 수 있습니다.')
            return redirect('purchase:po_detail', slug=order.po_number)

        order.is_active = False
        order.save(update_fields=['is_active', 'updated_at'])
        # 항목도 soft delete
        order.items.update(is_active=False)
        messages.success(request, f'발주서 {order.po_number}이(가) 삭제되었습니다.')
        return redirect('purchase:po_list')


class PurchaseOrderUpdateView(ManagerRequiredMixin, UpdateView):
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'purchase/po_form.html'
    success_url = reverse_lazy('purchase:po_list')
    slug_field = 'po_number'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = PurchaseOrderItemFormSet(
                self.request.POST, self.request.FILES,
                instance=self.object,
            )
        else:
            ctx['formset'] = PurchaseOrderItemFormSet(
                instance=self.object,
            )
        ctx['product_units_json'] = _product_units_json()
        ctx['product_prices_json'] = _product_prices_json()
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        formset = ctx['formset']
        if formset.is_valid():
            vat_changed = 'vat_included' in form.changed_data
            self.object = form.save()
            formset.instance = self.object
            formset.save()
            # VAT 옵션 변경 시 모든 항목 금액 재계산
            if vat_changed:
                for item in self.object.items.all():
                    item.save()
            self.object.update_total()
            return super().form_valid(form)
        return self.form_invalid(form)


# ─── 발주 상태 전환 ──────────────────────────────────────────

class PurchaseOrderStatusChangeView(ManagerRequiredMixin, View):
    """발주서 상태 전환 (POST only)"""

    def post(self, request, slug):
        order = get_object_or_404(PurchaseOrder, po_number=slug, is_active=True)
        new_status = request.POST.get('status')

        allowed = PurchaseOrder.STATUS_TRANSITIONS.get(order.status, [])
        if new_status not in allowed:
            messages.error(request, '허용되지 않는 상태 전환입니다.')
            return redirect('purchase:po_detail', slug=order.po_number)

        order.status = new_status
        try:
            order.save(update_fields=['status', 'updated_at'])
        except Exception as e:
            messages.error(request, str(e))
            return redirect('purchase:po_detail', slug=order.po_number)

        messages.success(
            request,
            f'발주 상태가 "{order.get_status_display()}"(으)로 '
            f'변경되었습니다.',
        )
        return redirect('purchase:po_detail', slug=order.po_number)


# ─── 입고 ────────────────────────────────────────────────

class GoodsReceiptCreateView(ManagerRequiredMixin, CreateView):
    model = GoodsReceipt
    form_class = GoodsReceiptForm
    template_name = 'purchase/receipt_form.html'

    def get_initial(self):
        initial = super().get_initial()
        from apps.core.utils import generate_document_number
        initial['receipt_number'] = generate_document_number(GoodsReceipt, 'receipt_number', 'GR')
        return initial

    def dispatch(self, request, *args, **kwargs):
        self.purchase_order = get_object_or_404(PurchaseOrder, po_number=kwargs['slug'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['purchase_order'] = self.purchase_order
        ctx['po_items'] = self.purchase_order.items.select_related('product').all()
        from apps.asset.models import AssetCategory
        ctx['asset_categories'] = AssetCategory.objects.filter(is_active=True)
        return ctx

    def form_valid(self, form):
        from django.contrib import messages
        from apps.asset.models import AssetCategory

        # 입고 항목 수집 (GR 저장 전에 검증)
        receipt_items = []
        po_items = self.purchase_order.items.all()
        for po_item in po_items:
            qty = self.request.POST.get(f'recv_qty_{po_item.pk}')
            inspected = self.request.POST.get(f'inspected_{po_item.pk}')
            is_asset = self.request.POST.get(f'is_asset_{po_item.pk}')
            asset_cat_id = self.request.POST.get(f'asset_category_{po_item.pk}')
            if qty and int(qty) > 0:
                recv_qty = int(qty)
                if recv_qty > po_item.remaining_quantity:
                    continue
                asset_category = None
                if is_asset and asset_cat_id:
                    try:
                        asset_category = AssetCategory.objects.get(pk=asset_cat_id, is_active=True)
                    except AssetCategory.DoesNotExist:
                        pass
                receipt_items.append((po_item, recv_qty, bool(inspected), bool(is_asset), asset_category))

        if not receipt_items:
            messages.error(self.request, '입고수량을 1개 이상 입력해주세요.')
            return self.form_invalid(form)

        form.instance.purchase_order = self.purchase_order
        form.instance.created_by = self.request.user
        self.object = form.save()

        for po_item, recv_qty, inspected, is_asset, asset_category in receipt_items:
            GoodsReceiptItem.objects.create(
                goods_receipt=self.object,
                po_item=po_item,
                received_quantity=recv_qty,
                is_inspected=inspected,
                is_fixed_asset=is_asset and asset_category is not None,
                asset_category=asset_category,
            )

        return super().form_valid(form)

    def get_success_url(self):
        return reverse('purchase:receipt_detail', kwargs={'slug': self.object.receipt_number})


class GoodsReceiptListView(LoginRequiredMixin, ListView):
    model = GoodsReceipt
    template_name = 'purchase/receipt_list.html'
    context_object_name = 'receipts'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().select_related('purchase_order', 'purchase_order__partner')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(receipt_number__icontains=q)
                | Q(purchase_order__po_number__icontains=q)
                | Q(purchase_order__partner__name__icontains=q)
            )
        return qs


class GoodsReceiptDetailView(LoginRequiredMixin, DetailView):
    model = GoodsReceipt
    template_name = 'purchase/receipt_detail.html'
    context_object_name = 'receipt'
    slug_field = 'receipt_number'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['items'] = self.object.items.select_related('po_item__product').all()
        return ctx


class GoodsReceiptInspectView(ManagerRequiredMixin, View):
    """입고 항목 검수 상태 일괄 저장"""

    def post(self, request, slug):
        receipt = get_object_or_404(GoodsReceipt, receipt_number=slug)
        for item in receipt.items.all():
            inspected = bool(request.POST.get(f'inspected_{item.pk}'))
            if item.is_inspected != inspected:
                item.is_inspected = inspected
                item.save(update_fields=['is_inspected', 'updated_at'])
        messages.success(request, '검수 상태가 저장되었습니다.')
        return redirect('purchase:receipt_detail', slug=receipt.receipt_number)


# ─── 일괄 가져오기 ─────────────────────────────────────────

class PurchaseOrderImportView(ManagerRequiredMixin, TemplateView):
    template_name = 'core/import.html'

    def get(self, request, *args, **kwargs):
        if request.GET.get('action') == 'export':
            from apps.core.import_views import export_resource_data
            from .resources import PurchaseOrderResource
            return export_resource_data(PurchaseOrderResource(), '발주서_데이터')
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = '구매발주 일괄 가져오기'
        ctx['cancel_url'] = reverse_lazy('purchase:po_list')
        ctx['sample_url'] = reverse_lazy('purchase:po_import_sample')
        ctx['field_hints'] = [
            '발주번호(po_number)가 동일하면 기존 발주가 수정됩니다.',
            'partner_code: 거래처코드',
            'status: DRAFT(임시), CONFIRMED(확정)',
        ]
        ctx['supports_export'] = True
        return ctx

    def post(self, request, *args, **kwargs):
        from apps.core.import_views import (
            parse_import_file, build_preview, collect_errors,
        )
        from .resources import PurchaseOrderResource

        action = request.POST.get('action', 'preview')
        import_file = request.FILES.get('import_file')
        if not import_file:
            messages.error(request, '파일을 선택해주세요.')
            return self.get(request, *args, **kwargs)

        resource = PurchaseOrderResource()
        try:
            data = parse_import_file(import_file)
            if data is None:
                messages.error(request, '지원하지 않는 파일 형식입니다.')
                return self.get(request, *args, **kwargs)
        except (ValueError, KeyError, TypeError, UnicodeDecodeError) as e:
            messages.error(request, f'파일 읽기 오류: {e}')
            return self.get(request, *args, **kwargs)

        if action == 'preview':
            result = resource.import_data(data, dry_run=True)
            ctx = self.get_context_data(**kwargs)
            ctx['preview'] = build_preview(result, data)
            ctx['errors'] = collect_errors(result)
            return self.render_to_response(ctx)
        else:
            result = resource.import_data(data, dry_run=False)
            if result.has_errors():
                ctx = self.get_context_data(**kwargs)
                ctx['errors'] = collect_errors(result)
                return self.render_to_response(ctx)
            total = (result.totals.get('new', 0)
                     + result.totals.get('update', 0))
            messages.success(request, f'{total}건 가져오기 완료.')
            return HttpResponseRedirect(
                str(reverse_lazy('purchase:po_list')),
            )


class PurchaseOrderImportSampleView(ManagerRequiredMixin, View):
    def get(self, request):
        from apps.core.excel import export_to_excel
        headers = [
            ('po_number', 15), ('partner_code', 15),
            ('order_date', 12), ('expected_date', 12),
            ('status', 12),
        ]
        rows = [
            ['PO-2026-001', 'PTN-001', '2026-03-01',
             '2026-03-15', 'DRAFT'],
            ['PO-2026-002', 'PTN-002', '2026-03-05',
             '2026-03-20', 'CONFIRMED'],
        ]
        return export_to_excel(
            '구매발주_가져오기_양식', headers, rows,
            filename='구매발주_가져오기_양식.xlsx',
            required_columns=[0, 1, 2],  # po_number, partner_code, order_date
        )


# ─── 견적요청 (RFQ) ─────────────────────────────────────

class RFQListView(LoginRequiredMixin, ListView):
    model = RFQ
    template_name = 'purchase/rfq_list.html'
    context_object_name = 'rfqs'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related('requested_by')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(rfq_number__icontains=q) | Q(title__icontains=q)
            )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs


class RFQCreateView(ManagerRequiredMixin, CreateView):
    model = RFQ
    form_class = RFQForm
    template_name = 'purchase/rfq_form.html'
    success_url = reverse_lazy('purchase:rfq_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = RFQItemFormSet(self.request.POST)
        else:
            ctx['formset'] = RFQItemFormSet()
        ctx['product_units_json'] = _product_units_json()
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        formset = ctx['formset']
        if formset.is_valid():
            self.object = form.save(commit=False)
            self.object.requested_by = self.request.user
            self.object.created_by = self.request.user
            self.object.save()
            formset.instance = self.object
            formset.save()
            return redirect(self.get_success_url())
        return self.form_invalid(form)


class RFQDetailView(LoginRequiredMixin, DetailView):
    model = RFQ
    template_name = 'purchase/rfq_detail.html'
    context_object_name = 'rfq'
    slug_field = 'rfq_number'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['items'] = self.object.items.select_related('product').all()
        ctx['responses'] = self.object.responses.select_related('partner').all()
        ctx['response_form'] = RFQResponseForm()
        return ctx


class RFQResponseCreateView(ManagerRequiredMixin, View):
    """RFQ에 대한 응답 등록"""

    def post(self, request, slug):
        rfq = get_object_or_404(RFQ, rfq_number=slug, is_active=True)
        form = RFQResponseForm(request.POST)
        if form.is_valid():
            response = form.save(commit=False)
            response.rfq = rfq
            response.created_by = request.user
            response.save()
            if rfq.status == RFQ.Status.SENT:
                rfq.status = RFQ.Status.RECEIVED
                rfq.save(update_fields=['status', 'updated_at'])
            messages.success(request, '견적 응답이 등록되었습니다.')
        else:
            for error in form.errors.values():
                messages.error(request, error)
        return redirect('purchase:rfq_detail', slug=rfq.rfq_number)


class RFQCompareView(LoginRequiredMixin, DetailView):
    """RFQ 응답 비교"""
    model = RFQ
    template_name = 'purchase/rfq_compare.html'
    context_object_name = 'rfq'
    slug_field = 'rfq_number'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['items'] = self.object.items.select_related('product').all()
        responses = list(self.object.responses.select_related('partner').filter(is_active=True))
        ctx['responses'] = responses
        if responses:
            ctx['lowest_price'] = min(r.total_amount for r in responses)
            ctx['shortest_delivery'] = min(r.delivery_days for r in responses)
        return ctx


class RFQConvertView(ManagerRequiredMixin, View):
    """선택된 RFQ 응답 -> PurchaseOrder 자동 변환"""

    def post(self, request, slug):
        from django.db import transaction

        rfq = get_object_or_404(RFQ, rfq_number=slug, is_active=True)
        response_id = request.POST.get('response_id')
        if not response_id:
            messages.error(request, '발주로 전환할 응답을 선택하세요.')
            return redirect('purchase:rfq_compare', slug=rfq.rfq_number)

        rfq_response = get_object_or_404(RFQResponse, pk=response_id, rfq=rfq)

        with transaction.atomic():
            # 낙찰 표시
            rfq.responses.update(is_selected=False)
            rfq_response.is_selected = True
            rfq_response.save(update_fields=['is_selected', 'updated_at'])

            # 발주서 생성
            po = PurchaseOrder(
                partner=rfq_response.partner,
                order_date=rfq_response.response_date,
                status=PurchaseOrder.Status.DRAFT,
                created_by=request.user,
                notes=f'RFQ {rfq.rfq_number} 기반 자동 생성',
            )
            if rfq_response.delivery_days:
                from datetime import timedelta
                po.expected_date = rfq_response.response_date + timedelta(days=rfq_response.delivery_days)
            po.save()

            # 발주 항목 생성
            rfq_items = rfq.items.select_related('product').all()
            item_count = rfq_items.count()
            for rfq_item in rfq_items:
                unit_price = (
                    int(rfq_response.total_amount / item_count / rfq_item.quantity)
                    if item_count > 0 and rfq_item.quantity > 0
                    else int(rfq_item.product.cost_price or 0)
                )
                PurchaseOrderItem.objects.create(
                    purchase_order=po,
                    product=rfq_item.product,
                    quantity=int(rfq_item.quantity),
                    unit_price=unit_price,
                    amount=unit_price * int(rfq_item.quantity),
                    created_by=request.user,
                )

            po.update_total()

            # RFQ 종결
            rfq.status = RFQ.Status.CLOSED
            rfq.save(update_fields=['status', 'updated_at'])

        messages.success(
            request,
            f'발주서 {po.po_number}이(가) 생성되었습니다.',
        )
        return redirect('purchase:po_detail', slug=po.po_number)


# ─── 공급처 평가 ─────────────────────────────────────

class VendorScoreListView(LoginRequiredMixin, ListView):
    model = VendorScore
    template_name = 'purchase/vendor_score_list.html'
    context_object_name = 'scores'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related('partner', 'evaluator')
        partner_id = self.request.GET.get('partner')
        if partner_id:
            qs = qs.filter(partner_id=partner_id)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.sales.models import Partner
        ctx['partners'] = Partner.objects.filter(
            is_active=True, partner_type__in=['SUPPLIER', 'BOTH'],
        ).order_by('name')
        return ctx


class VendorScoreCreateView(ManagerRequiredMixin, CreateView):
    model = VendorScore
    form_class = VendorScoreForm
    template_name = 'purchase/vendor_score_form.html'
    success_url = reverse_lazy('purchase:vendor_score_list')

    def form_valid(self, form):
        form.instance.evaluator = self.request.user
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class VendorScoreCardView(LoginRequiredMixin, TemplateView):
    """공급처별 평균 점수 카드"""
    template_name = 'purchase/vendor_scorecard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from django.db.models import Avg, Count
        from apps.sales.models import Partner

        partner_stats = (
            VendorScore.objects.filter(is_active=True)
            .values('partner', 'partner__name', 'partner__code')
            .annotate(
                avg_delivery=Avg('delivery_score'),
                avg_quality=Avg('quality_score'),
                avg_price=Avg('price_score'),
                avg_service=Avg('service_score'),
                avg_overall=Avg('overall_score'),
                eval_count=Count('pk'),
            )
            .order_by('-avg_overall')
        )

        for stat in partner_stats:
            stat['avg_delivery'] = round(stat['avg_delivery'], 1) if stat['avg_delivery'] else 0
            stat['avg_quality'] = round(stat['avg_quality'], 1) if stat['avg_quality'] else 0
            stat['avg_price'] = round(stat['avg_price'], 1) if stat['avg_price'] else 0
            stat['avg_service'] = round(stat['avg_service'], 1) if stat['avg_service'] else 0
            stat['avg_overall'] = round(stat['avg_overall'], 1) if stat['avg_overall'] else 0

        ctx['partner_stats'] = partner_stats
        return ctx
