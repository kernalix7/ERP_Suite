import tablib
import logging
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Sum, Count, Q, F, ExpressionWrapper, DecimalField, Case, When, Value
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView, TemplateView

from apps.core.mixins import ManagerRequiredMixin
from apps.inventory.models import Product
from .models import (
    Partner, Customer, Order, OrderItem,
    Quotation, QuotationItem, Shipment, ShipmentItem,
    ShippingCarrier, ShipmentTracking,
)
from .forms import (
    PartnerForm, CustomerForm, CustomerPurchaseFormSet,
    OrderForm, OrderItemFormSet,
    QuotationForm, QuotationItemFormSet,
    ShippingCarrierForm,
)


def _product_units_json():
    return {str(p.pk): p.unit or '' for p in Product.objects.filter(is_active=True)}


def _product_costs_json():
    """제품별 생산원가 JSON (최신 생산실적 unit_cost → BOM 원가 → product.cost_price 순)"""
    from django.db.models import Max, Subquery, OuterRef
    from apps.production.models import BOM, ProductionRecord

    products = list(Product.objects.filter(is_active=True))
    product_ids = [p.pk for p in products]

    # 1순위: 제품별 최신 생산실적의 unit_cost (배치 조회)
    latest_costs = dict(
        ProductionRecord.objects.filter(
            work_order__production_plan__product_id__in=product_ids,
            is_active=True,
            unit_cost__gt=0,
        ).values(
            'work_order__production_plan__product_id',
        ).annotate(
            latest_cost=Max('unit_cost'),
        ).values_list(
            'work_order__production_plan__product_id', 'latest_cost',
        )
    )

    # 2순위: BOM 원가 (배치 조회 - 기본BOM 우선)
    bom_costs = {}
    boms = BOM.objects.filter(
        product_id__in=product_ids, is_active=True,
    ).prefetch_related('items__material').order_by(
        'product_id', '-is_default', 'pk',
    )
    for bom in boms:
        pid = bom.product_id
        if pid not in bom_costs:
            cost = bom.total_material_cost
            if cost:
                bom_costs[pid] = int(cost)

    # 결과 조합
    costs = {}
    for p in products:
        if p.pk in latest_costs:
            costs[str(p.pk)] = int(latest_costs[p.pk])
        elif p.pk in bom_costs:
            costs[str(p.pk)] = bom_costs[p.pk]
        else:
            costs[str(p.pk)] = int(p.cost_price or 0)
    return costs
from .commission import CommissionRate, CommissionRecord
from .commission_forms import CommissionRateForm, CommissionRecordForm
from .resources import PartnerResource, CustomerResource, CommissionRateResource


class PartnerListView(LoginRequiredMixin, ListView):
    model = Partner
    template_name = 'sales/partner_list.html'
    context_object_name = 'partners'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).annotate(
            order_count=Count('orders'),
        ).order_by('name')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(name__icontains=q)
        return qs


class PartnerCreateView(LoginRequiredMixin, CreateView):
    model = Partner
    form_class = PartnerForm
    template_name = 'sales/partner_form.html'
    success_url = reverse_lazy('sales:partner_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from .commission_forms import CommissionRateInlineFormSet
        if self.request.POST:
            ctx['commission_formset'] = CommissionRateInlineFormSet(
                self.request.POST, prefix='comm',
            )
        else:
            ctx['commission_formset'] = CommissionRateInlineFormSet(
                prefix='comm',
            )
        return ctx

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        ctx = self.get_context_data()
        formset = ctx['commission_formset']
        if formset.is_valid():
            resp = super().form_valid(form)
            formset.instance = self.object
            formset.save()
            return resp
        return self.form_invalid(form)


class PartnerUpdateView(LoginRequiredMixin, UpdateView):
    model = Partner
    form_class = PartnerForm
    template_name = 'sales/partner_form.html'
    success_url = reverse_lazy('sales:partner_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from .commission_forms import CommissionRateInlineFormSet
        if self.request.POST:
            ctx['commission_formset'] = CommissionRateInlineFormSet(
                self.request.POST, instance=self.object,
                prefix='comm',
            )
        else:
            ctx['commission_formset'] = CommissionRateInlineFormSet(
                instance=self.object, prefix='comm',
            )
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        formset = ctx['commission_formset']
        if formset.is_valid():
            resp = super().form_valid(form)
            formset.save()
            return resp
        return self.form_invalid(form)


class CustomerListView(LoginRequiredMixin, ListView):
    model = Customer
    template_name = 'sales/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).prefetch_related('purchases__product')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(name__icontains=q) | Q(phone__icontains=q)
                | Q(purchases__serial_number__icontains=q)
            ).distinct()
        return qs


class CustomerCreateView(LoginRequiredMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'sales/customer_form.html'
    success_url = reverse_lazy('sales:customer_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = CustomerPurchaseFormSet(self.request.POST)
        else:
            ctx['formset'] = CustomerPurchaseFormSet()
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        formset = ctx['formset']
        if formset.is_valid():
            self.object = form.save(commit=False)
            self.object.created_by = self.request.user
            self.object.save()
            formset.instance = self.object
            formset.save()
            return redirect(self.get_success_url())
        return self.form_invalid(form)


class CustomerDetailView(LoginRequiredMixin, DetailView):
    model = Customer
    template_name = 'sales/customer_detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['purchases'] = self.object.purchases.filter(
            is_active=True,
        ).select_related('product')
        ctx['orders'] = self.object.orders.select_related(
            'partner', 'customer',
        ).all()
        ctx['service_requests'] = (
            self.object.service_requests
            .select_related('product')
            .all()
        )
        from apps.warranty.models import ProductRegistration
        ctx['registrations'] = ProductRegistration.objects.filter(
            customer=self.object, is_active=True,
        ).select_related('product')
        return ctx


class CustomerUpdateView(LoginRequiredMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'sales/customer_form.html'
    success_url = reverse_lazy('sales:customer_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = CustomerPurchaseFormSet(
                self.request.POST, instance=self.object,
            )
        else:
            ctx['formset'] = CustomerPurchaseFormSet(instance=self.object)
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        formset = ctx['formset']
        if formset.is_valid():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
            return redirect(self.get_success_url())
        return self.form_invalid(form)


class OrderListView(LoginRequiredMixin, ListView):
    model = Order
    template_name = 'sales/order_list.html'
    context_object_name = 'orders'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related(
            'partner', 'customer',
        ).prefetch_related('items')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs


class OrderCreateView(LoginRequiredMixin, CreateView):
    model = Order
    form_class = OrderForm
    template_name = 'sales/order_form.html'
    success_url = reverse_lazy('sales:order_list')

    def get_initial(self):
        initial = super().get_initial()
        from apps.core.utils import generate_document_number
        initial['order_number'] = generate_document_number(
            Order, 'order_number', 'ORD',
        )
        from apps.accounting.models import BankAccount
        default_bank = BankAccount.objects.filter(
            is_active=True, is_default=True,
        ).first()
        if default_bank:
            initial['bank_account'] = default_bank.pk
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = OrderItemFormSet(self.request.POST)
        else:
            ctx['formset'] = OrderItemFormSet()
        ctx['product_units_json'] = _product_units_json()
        ctx['product_costs_json'] = _product_costs_json()
        return ctx

    def form_valid(self, form):
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


class OrderDetailView(LoginRequiredMixin, DetailView):
    model = Order
    template_name = 'sales/order_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'partner', 'customer', 'bank_account',
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        items = self.object.items.select_related('product').all()
        ctx['items'] = items
        ctx['status_actions'] = self._build_status_actions()
        total_cost = sum(item.total_cost for item in items)
        total_amount = int(self.object.total_amount)
        shipping_cost = int(self.object.shipping_cost or 0)
        total_profit = total_amount - int(total_cost) - shipping_cost
        ctx['total_cost'] = total_cost
        ctx['shipping_cost'] = shipping_cost
        ctx['total_profit'] = total_profit
        ctx['total_profit_rate'] = (
            round(total_profit / total_amount * 100, 1)
            if total_amount else 0
        )
        # 거래처 수수료 (입금 시 차감용)
        if not self.object.is_paid and self.object.partner:
            partner = self.object.partner
            grand = int(self.object.grand_total or 0)
            comm = partner.calculate_commission(grand)
            if comm > 0:
                rate = partner.total_commission_rate
                ctx['partner_commission_rate'] = float(rate)
                ctx['partner_commission'] = comm
                ctx['auto_deposit'] = grand - comm
        return ctx

    def _build_status_actions(self):
        order = self.object
        allowed = Order.STATUS_TRANSITIONS.get(order.status, [])
        action_map = {
            'CONFIRMED': {
                'label': '주문 확정',
                'css': 'btn-primary',
                'icon': '<svg class="w-4 h-4 inline mr-1 -mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>',
                'confirm': '주문을 확정하시겠습니까?',
            },
            'SHIPPED': {
                'label': '출고 완료',
                'css': 'btn-primary',
                'icon': '<svg class="w-4 h-4 inline mr-1 -mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8"/></svg>',
                'confirm': '출고 처리하시겠습니까?',
            },
            'DELIVERED': {
                'label': '배송 완료',
                'css': 'btn btn-primary bg-green-600 hover:bg-green-700',
                'icon': '<svg class="w-4 h-4 inline mr-1 -mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
                'confirm': '배송 완료 처리하시겠습니까?',
            },
            'CANCELLED': {
                'label': '주문 취소',
                'css': 'btn btn-secondary text-red-600 hover:bg-red-50',
                'icon': '<svg class="w-4 h-4 inline mr-1 -mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>',
                'confirm': '주문을 취소하시겠습니까? 이 작업은 되돌릴 수 없습니다.',
            },
        }
        actions = []
        for status in allowed:
            if status in action_map:
                actions.append({**action_map[status], 'value': status})
        return actions


class OrderUpdateView(ManagerRequiredMixin, UpdateView):
    model = Order
    form_class = OrderForm
    template_name = 'sales/order_form.html'
    success_url = reverse_lazy('sales:order_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = OrderItemFormSet(self.request.POST, instance=self.object)
        else:
            ctx['formset'] = OrderItemFormSet(instance=self.object)
        ctx['product_units_json'] = _product_units_json()
        ctx['product_costs_json'] = _product_costs_json()
        ctx['is_settled'] = self.object.is_settled
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        formset = ctx['formset']
        if formset.is_valid():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
            # vat_included 변경 시 모든 항목 VAT 재계산
            for item in self.object.items.all():
                item.save()
            self.object.update_total()
            return super().form_valid(form)
        return self.form_invalid(form)


class OrderStatusChangeView(ManagerRequiredMixin, View):
    """주문 상태 전환 (POST only)"""

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk, is_active=True)
        new_status = request.POST.get('status')

        allowed = Order.STATUS_TRANSITIONS.get(order.status, [])
        if new_status not in allowed:
            messages.error(request, '허용되지 않는 상태 전환입니다.')
            return redirect('sales:order_detail', pk=order.pk)

        order.status = new_status
        try:
            order.save(update_fields=['status', 'updated_at'])
        except Exception as e:
            messages.error(request, str(e))
            return redirect('sales:order_detail', pk=order.pk)
        messages.success(request, f'주문 상태가 "{order.get_status_display()}"(으)로 변경되었습니다.')
        return redirect('sales:order_detail', pk=order.pk)


class OrderPaymentView(LoginRequiredMixin, View):
    """주문 입금 처리 — 수수료 자동계산 / 실입금액 수동입력"""

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk, is_active=True)

        if order.is_paid:
            messages.warning(request, '이미 입금 처리된 주문입니다.')
            return redirect('sales:order_detail', pk=order.pk)

        mode = request.POST.get('payment_mode', 'full')
        deposit_amount = None
        commission_amount = 0

        if mode == 'auto_commission':
            # 거래처 수수료 항목으로 자동 계산
            if order.partner:
                grand = int(order.grand_total)
                commission_amount = order.partner.calculate_commission(grand)
                if commission_amount > 0:
                    deposit_amount = grand - commission_amount
        elif mode == 'manual':
            # 실 입금액 직접 입력
            raw = request.POST.get('deposit_amount', '')
            if raw:
                try:
                    deposit_amount = int(raw)
                    commission_amount = (
                        int(order.grand_total) - deposit_amount
                    )
                except (ValueError, TypeError):
                    messages.error(request, '입금액을 올바르게 입력해주세요.')
                    return redirect(
                        'sales:order_detail', pk=order.pk,
                    )

        from apps.sales.signals import _auto_create_payment
        try:
            _auto_create_payment(
                order,
                deposit_amount=deposit_amount,
                commission_amount=commission_amount,
            )
            if deposit_amount is not None and commission_amount > 0:
                messages.success(
                    request,
                    f'{order.order_number} 입금 {deposit_amount:,}원'
                    f' (수수료 {commission_amount:,}원 차감)',
                )
            else:
                messages.success(
                    request,
                    f'{order.order_number} 입금 처리 완료',
                )
        except Exception as e:
            messages.error(request, f'입금 처리 실패: {e}')

        return redirect('sales:order_detail', pk=order.pk)


# === Soft Delete Views ===
class _SoftDeleteView(ManagerRequiredMixin, DeleteView):
    """공용 soft delete 뷰 (비활성화)"""
    template_name = 'sales/confirm_delete.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['model_name'] = self.model._meta.verbose_name
        return ctx

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.soft_delete()
        messages.success(request, f'{self.model._meta.verbose_name}이(가) 삭제되었습니다.')
        return HttpResponseRedirect(self.get_success_url())


class OrderDeleteView(_SoftDeleteView):
    model = Order
    success_url = reverse_lazy('sales:order_list')


class QuotationDeleteView(_SoftDeleteView):
    model = Quotation
    success_url = reverse_lazy('sales:quote_list')


class CustomerDeleteView(_SoftDeleteView):
    model = Customer
    success_url = reverse_lazy('sales:customer_list')


class PartnerDeleteView(_SoftDeleteView):
    model = Partner
    success_url = reverse_lazy('sales:partner_list')


class ShipmentDeleteView(_SoftDeleteView):
    model = Shipment
    success_url = reverse_lazy('sales:shipment_list')


# === 수수료율 ===
class CommissionRateListView(LoginRequiredMixin, ListView):
    model = CommissionRate
    template_name = 'sales/commission_rate_list.html'
    context_object_name = 'commission_rates'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True).select_related(
            'partner', 'product',
        ).order_by('-pk')


class CommissionRateCreateView(LoginRequiredMixin, CreateView):
    model = CommissionRate
    form_class = CommissionRateForm
    template_name = 'sales/commission_rate_form.html'
    success_url = reverse_lazy('sales:commission_rate_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class CommissionRateUpdateView(LoginRequiredMixin, UpdateView):
    model = CommissionRate
    form_class = CommissionRateForm
    template_name = 'sales/commission_rate_form.html'
    success_url = reverse_lazy('sales:commission_rate_list')


# === 수수료내역 ===
class CommissionRecordListView(LoginRequiredMixin, ListView):
    model = CommissionRecord
    template_name = 'sales/commission_list.html'
    context_object_name = 'commissions'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related(
            'partner', 'order',
        )
        status = self.request.GET.get('status')
        partner = self.request.GET.get('partner')
        if status:
            qs = qs.filter(status=status)
        if partner:
            qs = qs.filter(partner_id=partner)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['partners'] = Partner.objects.all()
        ctx['status_choices'] = CommissionRecord.Status.choices
        return ctx


class CommissionRecordCreateView(LoginRequiredMixin, CreateView):
    model = CommissionRecord
    form_class = CommissionRecordForm
    template_name = 'sales/commission_form.html'
    success_url = reverse_lazy('sales:commission_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # 주문 금액 데이터 (order_id → total_amount)
        order_amounts = {}
        for o in Order.objects.filter(is_active=True, status='DELIVERED'):
            order_amounts[str(o.pk)] = {
                'amount': int(o.total_amount),
                'partner': o.partner_id,
            }
        ctx['order_amounts_json'] = order_amounts
        # 수수료율 데이터 (partner_id → rate)
        rate_map = {}
        for r in CommissionRate.objects.filter(is_active=True, product__isnull=True):
            rate_map[str(r.partner_id)] = float(r.rate)
        ctx['commission_rates_json'] = rate_map
        return ctx

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


logger = logging.getLogger(__name__)


def _auto_create_commission_payment(record, user):
    """수수료 정산 시 Payment(DISBURSEMENT) + 복식부기 전표 자동 생성"""
    from apps.accounting.models import (
        AccountCode, BankAccount, Payment, Voucher, VoucherLine,
    )

    amount = int(record.commission_amount)
    if amount <= 0:
        return

    # 이미 출금 기록이 있으면 스킵
    if Payment.objects.filter(
        reference__contains=f'수수료 {record.pk}',
        payment_type='DISBURSEMENT',
    ).exists():
        return

    # 기본 출금계좌
    bank = BankAccount.objects.filter(
        is_active=True, is_default=True,
    ).first()
    if not bank:
        logger.warning('출금계좌 미설정 — 수수료 %s 출금 자동생성 불가', record.pk)
        return

    # 복식부기 전표 생성
    acct_commission = AccountCode.objects.filter(code='502', is_active=True).first()  # 수수료비용
    acct_bank = bank.account_code  # 보통예금

    voucher = Voucher.objects.create(
        voucher_type='PAYMENT',
        voucher_date=date.today(),
        description=f'수수료 정산 - {record.partner.name} ({record.order.order_number if record.order else ""})',
        approval_status='APPROVED',
        created_by=user,
    )

    # 차변: 수수료비용
    if acct_commission:
        VoucherLine.objects.create(
            voucher=voucher,
            account=acct_commission,
            debit=amount, credit=0,
            description=f'{record.partner.name} 수수료',
            created_by=user,
        )

    # 대변: 보통예금 (은행계좌)
    if acct_bank:
        VoucherLine.objects.create(
            voucher=voucher,
            account=acct_bank,
            debit=0, credit=amount,
            description=f'{record.partner.name} 수수료 출금 ({bank.name})',
            created_by=user,
        )

    # Payment(DISBURSEMENT) 생성
    Payment.objects.create(
        payment_type='DISBURSEMENT',
        partner=record.partner,
        bank_account=bank,
        voucher=voucher,
        amount=amount,
        payment_date=date.today(),
        payment_method='BANK_TRANSFER',
        reference=f'수수료 {record.pk} ({record.partner.name})',
        created_by=user,
    )
    logger.info(
        'Auto-created DISBURSEMENT for commission %s: %s원 → %s',
        record.pk, amount, bank.name,
    )


class CommissionRecordSettleView(LoginRequiredMixin, View):
    def post(self, request, pk):
        record = get_object_or_404(CommissionRecord, pk=pk)
        if record.status == 'PENDING':
            with transaction.atomic():
                record.status = 'SETTLED'
                record.settled_date = date.today()
                record.save(update_fields=['status', 'settled_date', 'updated_at'])

                # 수수료 출금(DISBURSEMENT) 자동 생성
                _auto_create_commission_payment(record, request.user)

            messages.success(
                request,
                f'{record.partner.name} 수수료 {record.commission_amount:,}원 정산완료 처리',
            )
        return redirect('sales:commission_list')


class CommissionSummaryView(LoginRequiredMixin, TemplateView):
    template_name = 'sales/commission_summary.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        summary = CommissionRecord.objects.values(
            'partner__id', 'partner__name',
        ).annotate(
            total_orders=Count('id'),
            total_commission=Sum('commission_amount'),
            settled=Sum('commission_amount', filter=Q(status='SETTLED')),
            unsettled=Sum('commission_amount', filter=Q(status='PENDING')),
        ).order_by('partner__name')
        ctx['summary'] = summary
        return ctx


# === PDF 다운로드 ===
class OrderQuotePDFView(LoginRequiredMixin, DetailView):
    """견적서 PDF 다운로드"""
    model = Order

    def get(self, request, *args, **kwargs):
        order = self.get_object()
        from apps.core.pdf import generate_quotation_pdf
        return generate_quotation_pdf(order)


class OrderPurchaseOrderPDFView(LoginRequiredMixin, DetailView):
    """발주서 PDF 다운로드"""
    model = Order

    def get(self, request, *args, **kwargs):
        order = self.get_object()
        from apps.core.pdf import generate_purchase_order_pdf
        return generate_purchase_order_pdf(order)


# === Excel 다운로드 ===
class OrderExcelView(LoginRequiredMixin, View):
    def get(self, request):
        from apps.core.excel import export_to_excel
        orders = Order.objects.filter(is_active=True).select_related('partner', 'customer')
        headers = [
            ('주문번호', 18), ('거래처', 20), ('고객', 15), ('주문일', 12),
            ('상태', 10), ('공급가액', 15), ('부가세', 15), ('총합계', 15),
        ]
        rows = [
            [
                o.order_number,
                o.partner.name if o.partner else '',
                o.customer.name if o.customer else '',
                o.order_date.strftime('%Y-%m-%d') if o.order_date else '',
                o.get_status_display(),
                int(o.total_amount),
                int(o.tax_total),
                int(o.grand_total),
            ]
            for o in orders
        ]
        return export_to_excel('주문목록', headers, rows, money_columns=[5, 6, 7])


# === Excel 일괄 가져오기 공통 헬퍼 ===
def _build_preview(result, data):
    headers = list(data.headers) if data.headers else []
    rows = []
    for i, row_result in enumerate(result.rows):
        values = list(data[i]) if i < len(data) else []
        if row_result.errors:
            status = 'error'
        elif row_result.import_type == 'new':
            status = 'new'
        elif row_result.import_type == 'update':
            status = 'update'
        else:
            status = 'skip'
        rows.append({'status': status, 'values': values})

    totals = {
        'new': result.totals.get('new', 0),
        'update': result.totals.get('update', 0),
        'skip': result.totals.get('skip', 0),
        'error': result.totals.get('error', 0) + result.totals.get('invalid', 0),
    }
    return {
        'headers': headers,
        'rows': rows,
        'totals': totals,
        'has_valid_rows': totals['new'] > 0 or totals['update'] > 0,
        'file_name': '',
    }


def _collect_errors(result):
    errors = []
    if result.base_errors:
        for err in result.base_errors:
            errors.append(str(err.error))
    for i, row in enumerate(result.rows):
        if row.errors:
            for err in row.errors:
                errors.append(f'{i + 1}행: {err.error}')
        if hasattr(row, 'validation_error') and row.validation_error:
            errors.append(f'{i + 1}행: {row.validation_error}')
    return errors


def _parse_import_file(request, import_file):
    """업로드된 파일을 tablib Dataset으로 파싱"""
    from apps.core.import_views import parse_import_file
    return parse_import_file(import_file)


class PartnerImportView(ManagerRequiredMixin, TemplateView):
    template_name = 'core/import.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = '거래처 일괄 가져오기'
        ctx['cancel_url'] = reverse_lazy('sales:partner_list')
        ctx['sample_url'] = reverse_lazy('sales:partner_import_sample')
        ctx['field_hints'] = [
            '거래처코드(code)가 동일하면 기존 거래처가 수정됩니다.',
            '유형(partner_type): CUSTOMER(고객), SUPPLIER(공급처), BOTH(고객/공급처)',
        ]
        return ctx

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action', 'preview')
        import_file = request.FILES.get('import_file')

        if not import_file:
            messages.error(request, '파일을 선택해주세요.')
            return self.get(request, *args, **kwargs)

        resource = PartnerResource()

        try:
            data = _parse_import_file(request, import_file)
            if data is None:
                messages.error(request, '지원하지 않는 파일 형식입니다. (.xlsx, .xls, .csv)')
                return self.get(request, *args, **kwargs)
        except (ValueError, KeyError, TypeError, UnicodeDecodeError) as e:
            messages.error(request, f'파일 읽기 오류: {e}')
            return self.get(request, *args, **kwargs)

        if action == 'preview':
            result = resource.import_data(data, dry_run=True)
            ctx = self.get_context_data(**kwargs)
            ctx['preview'] = _build_preview(result, data)
            ctx['errors'] = _collect_errors(result)
            return self.render_to_response(ctx)
        else:
            result = resource.import_data(data, dry_run=False)
            if result.has_errors():
                ctx = self.get_context_data(**kwargs)
                ctx['errors'] = _collect_errors(result)
                return self.render_to_response(ctx)
            total = result.totals.get('new', 0) + result.totals.get('update', 0)
            messages.success(request, f'거래처 {total}건이 성공적으로 가져오기 되었습니다.')
            return HttpResponseRedirect(reverse_lazy('sales:partner_list'))


class PartnerImportSampleView(ManagerRequiredMixin, View):
    def get(self, request):
        from apps.core.excel import export_to_excel
        headers = [
            ('code', 15), ('name', 25), ('partner_type', 12),
            ('business_number', 15), ('representative', 12),
            ('contact_name', 12), ('phone', 15), ('email', 20), ('address', 30),
        ]
        rows = [
            ['PTN-001', '샘플 거래처', 'CUSTOMER', '123-45-67890', '홍길동',
             '김담당', '02-1234-5678', 'sample@example.com', '서울시 강남구'],
            ['PTN-002', '샘플 공급처', 'SUPPLIER', '987-65-43210', '이대표',
             '박담당', '031-9876-5432', 'supplier@example.com', '경기도 성남시'],
        ]
        return export_to_excel(
            '거래처_가져오기_양식', headers, rows,
            filename='거래처_가져오기_양식.xlsx',
            required_columns=[0, 1, 2],  # code, name, partner_type
        )


class CustomerImportView(ManagerRequiredMixin, TemplateView):
    template_name = 'core/import.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = '고객 일괄 가져오기'
        ctx['cancel_url'] = reverse_lazy('sales:customer_list')
        ctx['sample_url'] = reverse_lazy('sales:customer_import_sample')
        ctx['field_hints'] = [
            '고객명(name)과 연락처(phone)가 동일하면 기존 고객이 수정됩니다.',
        ]
        return ctx

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action', 'preview')
        import_file = request.FILES.get('import_file')

        if not import_file:
            messages.error(request, '파일을 선택해주세요.')
            return self.get(request, *args, **kwargs)

        resource = CustomerResource()

        try:
            data = _parse_import_file(request, import_file)
            if data is None:
                messages.error(request, '지원하지 않는 파일 형식입니다. (.xlsx, .xls, .csv)')
                return self.get(request, *args, **kwargs)
        except (ValueError, KeyError, TypeError, UnicodeDecodeError) as e:
            messages.error(request, f'파일 읽기 오류: {e}')
            return self.get(request, *args, **kwargs)

        if action == 'preview':
            result = resource.import_data(data, dry_run=True)
            ctx = self.get_context_data(**kwargs)
            ctx['preview'] = _build_preview(result, data)
            ctx['errors'] = _collect_errors(result)
            return self.render_to_response(ctx)
        else:
            result = resource.import_data(data, dry_run=False)
            if result.has_errors():
                ctx = self.get_context_data(**kwargs)
                ctx['errors'] = _collect_errors(result)
                return self.render_to_response(ctx)
            total = result.totals.get('new', 0) + result.totals.get('update', 0)
            messages.success(request, f'고객 {total}건이 성공적으로 가져오기 되었습니다.')
            return HttpResponseRedirect(reverse_lazy('sales:customer_list'))


class CustomerImportSampleView(ManagerRequiredMixin, View):
    def get(self, request):
        from apps.core.excel import export_to_excel
        headers = [
            ('name', 20), ('phone', 15), ('email', 25), ('address', 35),
        ]
        rows = [
            ['홍길동', '010-1234-5678', 'hong@example.com', '서울시 강남구 테헤란로 123'],
            ['김철수', '010-9876-5432', 'kim@example.com', '경기도 성남시 분당구 판교로 456'],
        ]
        # name, phone 필수 (import_id_fields)
        return export_to_excel(
            '고객_가져오기_양식', headers, rows,
            filename='고객_가져오기_양식.xlsx',
            required_columns=[0, 1],  # name, phone
        )


# === 수수료율 일괄 가져오기 ===

class CommissionRateImportView(ManagerRequiredMixin, TemplateView):
    template_name = 'core/import.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = '수수료율 일괄 가져오기'
        ctx['cancel_url'] = reverse_lazy('sales:commission_rate_list')
        ctx['sample_url'] = reverse_lazy(
            'sales:commission_rate_import_sample',
        )
        ctx['field_hints'] = [
            '거래처코드(partner_code) + 제품코드(product_code) '
            '조합이 동일하면 기존 수수료율이 수정됩니다.',
            'product_code를 비워두면 해당 거래처의 기본 수수료율로 등록됩니다.',
            '수수료율(rate)은 소수점 2자리까지 (예: 3.50)',
        ]
        return ctx

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action', 'preview')
        import_file = request.FILES.get('import_file')

        if not import_file:
            messages.error(request, '파일을 선택해주세요.')
            return self.get(request, *args, **kwargs)

        resource = CommissionRateResource()

        try:
            data = _parse_import_file(request, import_file)
            if data is None:
                messages.error(
                    request,
                    '지원하지 않는 파일 형식입니다. (.xlsx, .xls, .csv)',
                )
                return self.get(request, *args, **kwargs)
        except (ValueError, KeyError, TypeError, UnicodeDecodeError) as e:
            messages.error(request, f'파일 읽기 오류: {e}')
            return self.get(request, *args, **kwargs)

        if action == 'preview':
            result = resource.import_data(data, dry_run=True)
            ctx = self.get_context_data(**kwargs)
            ctx['preview'] = _build_preview(result, data)
            ctx['errors'] = _collect_errors(result)
            return self.render_to_response(ctx)
        else:
            result = resource.import_data(data, dry_run=False)
            if result.has_errors():
                ctx = self.get_context_data(**kwargs)
                ctx['errors'] = _collect_errors(result)
                return self.render_to_response(ctx)
            total = (result.totals.get('new', 0)
                     + result.totals.get('update', 0))
            messages.success(
                request,
                f'{total}건의 수수료율이 가져오기 되었습니다.',
            )
            return HttpResponseRedirect(
                str(reverse_lazy('sales:commission_rate_list')),
            )


class CommissionRateImportSampleView(ManagerRequiredMixin, View):
    def get(self, request):
        from apps.core.excel import export_to_excel
        headers = [
            ('partner_code', 15),
            ('product_code', 15),
            ('rate', 12),
        ]
        rows = [
            ['PTN-001', '', '3.00'],
            ['PTN-001', 'PRD-001', '5.00'],
            ['PTN-002', '', '2.50'],
            ['PTN-002', 'PRD-003', '4.00'],
        ]
        return export_to_excel(
            '수수료율_가져오기_양식', headers, rows,
            filename='수수료율_가져오기_양식.xlsx',
            required_columns=[0, 2],  # partner_code, rate
        )


class CommissionRateExcelView(ManagerRequiredMixin, View):
    """현재 수수료율 전체를 Excel로 내보내기 (템플릿 대용)"""
    def get(self, request):
        from apps.core.excel import export_to_excel
        qs = CommissionRate.objects.filter(
            is_active=True,
        ).select_related('partner', 'product').order_by(
            'partner__code', 'product__code',
        )
        headers = [
            ('partner_code', 15),
            ('product_code', 15),
            ('rate', 12),
        ]
        rows = [
            [
                cr.partner.code,
                cr.product.code if cr.product else '',
                float(cr.rate),
            ]
            for cr in qs
        ]
        return export_to_excel(
            '수수료율_현황', headers, rows,
            filename='수수료율_현황.xlsx',
        )


# === 주문 일괄 가져오기 ===

class OrderImportView(ManagerRequiredMixin, TemplateView):
    template_name = 'core/import.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = '주문 일괄 가져오기'
        ctx['cancel_url'] = reverse_lazy('sales:order_list')
        ctx['sample_url'] = reverse_lazy('sales:order_import_sample')
        ctx['field_hints'] = [
            '주문번호(order_number)가 동일하면 기존 주문이 수정됩니다.',
            'partner_code: 거래처코드, customer_name: 고객명',
            'status: PENDING(대기), CONFIRMED(확정), '
            'SHIPPED(출하), DELIVERED(배송완료), CANCELLED(취소)',
        ]
        return ctx

    def post(self, request, *args, **kwargs):
        from .resources import OrderResource
        action = request.POST.get('action', 'preview')
        import_file = request.FILES.get('import_file')
        if not import_file:
            messages.error(request, '파일을 선택해주세요.')
            return self.get(request, *args, **kwargs)
        resource = OrderResource()
        try:
            data = _parse_import_file(request, import_file)
            if data is None:
                messages.error(
                    request, '지원하지 않는 파일 형식입니다.',
                )
                return self.get(request, *args, **kwargs)
        except (ValueError, KeyError, TypeError, UnicodeDecodeError) as e:
            messages.error(request, f'파일 읽기 오류: {e}')
            return self.get(request, *args, **kwargs)
        if action == 'preview':
            result = resource.import_data(data, dry_run=True)
            ctx = self.get_context_data(**kwargs)
            ctx['preview'] = _build_preview(result, data)
            ctx['errors'] = _collect_errors(result)
            return self.render_to_response(ctx)
        else:
            result = resource.import_data(data, dry_run=False)
            if result.has_errors():
                ctx = self.get_context_data(**kwargs)
                ctx['errors'] = _collect_errors(result)
                return self.render_to_response(ctx)
            total = (result.totals.get('new', 0)
                     + result.totals.get('update', 0))
            messages.success(request, f'{total}건 가져오기 완료.')
            return HttpResponseRedirect(
                str(reverse_lazy('sales:order_list')),
            )


class OrderImportSampleView(ManagerRequiredMixin, View):
    def get(self, request):
        from apps.core.excel import export_to_excel
        headers = [
            ('order_number', 15), ('partner_code', 15),
            ('customer_name', 15), ('order_date', 12),
            ('status', 12), ('shipping_address', 30),
            ('notes', 20),
        ]
        rows = [
            ['ORD-2026-001', 'PTN-001', '홍길동',
             '2026-03-01', 'PENDING', '서울시 강남구', ''],
            ['ORD-2026-002', 'PTN-002', '김철수',
             '2026-03-05', 'CONFIRMED', '경기도 성남시', ''],
        ]
        return export_to_excel(
            '주문_가져오기_양식', headers, rows,
            filename='주문_가져오기_양식.xlsx',
            required_columns=[0, 3],  # order_number, order_date
        )


# === 배송 일괄 가져오기 ===

class ShipmentImportView(ManagerRequiredMixin, TemplateView):
    template_name = 'core/import.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = '배송 일괄 가져오기'
        ctx['cancel_url'] = reverse_lazy('sales:shipment_list')
        ctx['sample_url'] = reverse_lazy(
            'sales:shipment_import_sample',
        )
        ctx['field_hints'] = [
            '배송번호(shipment_number)가 동일하면 수정됩니다.',
            'order_number: 연결할 주문번호',
            'carrier: 택배사명 (CJ, HANJIN, LOTTE 등)',
            'status: READY(준비), SHIPPED(출하), '
            'IN_TRANSIT(배송중), DELIVERED(배송완료)',
        ]
        return ctx

    def post(self, request, *args, **kwargs):
        from .resources import ShipmentResource
        action = request.POST.get('action', 'preview')
        import_file = request.FILES.get('import_file')
        if not import_file:
            messages.error(request, '파일을 선택해주세요.')
            return self.get(request, *args, **kwargs)
        resource = ShipmentResource()
        try:
            data = _parse_import_file(request, import_file)
            if data is None:
                messages.error(
                    request, '지원하지 않는 파일 형식입니다.',
                )
                return self.get(request, *args, **kwargs)
        except (ValueError, KeyError, TypeError, UnicodeDecodeError) as e:
            messages.error(request, f'파일 읽기 오류: {e}')
            return self.get(request, *args, **kwargs)
        if action == 'preview':
            result = resource.import_data(data, dry_run=True)
            ctx = self.get_context_data(**kwargs)
            ctx['preview'] = _build_preview(result, data)
            ctx['errors'] = _collect_errors(result)
            return self.render_to_response(ctx)
        else:
            result = resource.import_data(data, dry_run=False)
            if result.has_errors():
                ctx = self.get_context_data(**kwargs)
                ctx['errors'] = _collect_errors(result)
                return self.render_to_response(ctx)
            total = (result.totals.get('new', 0)
                     + result.totals.get('update', 0))
            messages.success(request, f'{total}건 가져오기 완료.')
            return HttpResponseRedirect(
                str(reverse_lazy('sales:shipment_list')),
            )


class ShipmentImportSampleView(ManagerRequiredMixin, View):
    def get(self, request):
        from apps.core.excel import export_to_excel
        headers = [
            ('shipment_number', 18), ('order_number', 15),
            ('carrier', 10), ('tracking_number', 18),
            ('status', 12), ('shipped_date', 12),
            ('delivered_date', 12), ('receiver_name', 12),
            ('receiver_phone', 15), ('receiver_address', 30),
        ]
        rows = [
            ['SHP-2026-001', 'ORD-2026-001', 'CJ',
             '123456789012', 'SHIPPED', '2026-03-02',
             '', '홍길동', '010-1234-5678', '서울시 강남구'],
        ]
        return export_to_excel(
            '배송_가져오기_양식', headers, rows,
            filename='배송_가져오기_양식.xlsx',
            required_columns=[0, 1],  # shipment_number, order_number
        )


# === 판매제품 통합 관리 ===

def _build_sold_product_queryset(request):
    """판매제품 목록 조회를 위한 공통 쿼리셋 빌더."""
    qs = OrderItem.objects.filter(
        is_active=True,
        order__is_active=True,
        order__status__in=[Order.Status.SHIPPED, Order.Status.DELIVERED],
    ).select_related(
        'order', 'order__customer', 'order__partner', 'product',
    ).order_by('-order__order_date', '-order__pk')

    # 검색
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(product__name__icontains=q)
            | Q(product__code__icontains=q)
            | Q(order__customer__name__icontains=q)
            | Q(order__partner__name__icontains=q)
            | Q(order__customer__purchases__serial_number__icontains=q)
            | Q(order__order_number__icontains=q)
        ).distinct()

    # 날짜 범위 필터
    sold_from = request.GET.get('sold_from', '').strip()
    sold_to = request.GET.get('sold_to', '').strip()
    if sold_from:
        qs = qs.filter(order__order_date__gte=sold_from)
    if sold_to:
        qs = qs.filter(order__order_date__lte=sold_to)

    # 제품유형 필터
    product_type = request.GET.get('product_type', '').strip()
    if product_type:
        qs = qs.filter(product__product_type=product_type)

    return qs


def _get_warranty_map(order_items):
    """OrderItem 목록에 대해 구매내역 맵 + ProductRegistration 맵 생성."""
    from apps.warranty.models import ProductRegistration
    from .models import CustomerPurchase

    customer_ids = set()
    for item in order_items:
        if item.order.customer_id:
            customer_ids.add(item.order.customer_id)

    # CustomerPurchase 맵: (customer_id, product_id) -> purchase
    purchase_map = {}
    if customer_ids:
        purchases = CustomerPurchase.objects.filter(
            customer_id__in=customer_ids, is_active=True,
        ).select_related('product')
        for p in purchases:
            purchase_map[(p.customer_id, p.product_id)] = p

    # ProductRegistration 맵: (product_id, serial_number) -> registration
    serial_numbers = {p.serial_number for p in purchase_map.values() if p.serial_number}
    reg_map = {}
    if serial_numbers:
        regs = ProductRegistration.objects.filter(
            serial_number__in=serial_numbers,
        ).select_related('product')
        for reg in regs:
            reg_map[(reg.product_id, reg.serial_number)] = reg

    return purchase_map, reg_map


def _get_service_count_map(order_items):
    """OrderItem 목록에 대해 (customer_id, product_id) -> AS건수 맵 생성."""
    from apps.service.models import ServiceRequest

    customer_product_pairs = set()
    for item in order_items:
        if item.order.customer_id:
            customer_product_pairs.add((item.order.customer_id, item.product_id))

    if not customer_product_pairs:
        return {}

    customer_ids = {cp[0] for cp in customer_product_pairs}
    product_ids = {cp[1] for cp in customer_product_pairs}

    counts = (
        ServiceRequest.objects.filter(
            customer_id__in=customer_ids,
            product_id__in=product_ids,
        )
        .values('customer_id', 'product_id')
        .annotate(cnt=Count('id'))
    )

    count_map = {}
    for row in counts:
        count_map[(row['customer_id'], row['product_id'])] = row['cnt']

    return count_map


def _enrich_sold_items(items):
    """OrderItem 리스트에 보증/AS 정보를 추가한 dict 리스트 반환."""
    items_list = list(items)
    if not items_list:
        return []

    purchase_map, reg_map = _get_warranty_map(items_list)
    svc_map = _get_service_count_map(items_list)
    today = date.today()

    result = []
    for item in items_list:
        customer = item.order.customer
        partner = item.order.partner

        customer_name = ''
        phone = ''
        serial_number = ''
        warranty_end = None
        warranty_status = 'none'

        if customer:
            customer_name = customer.name
            phone = customer.phone or ''

            # CustomerPurchase에서 해당 제품의 구매내역 조회
            purchase = purchase_map.get((customer.pk, item.product_id))
            if purchase:
                serial_number = purchase.serial_number or ''
                warranty_end = purchase.warranty_end

                # ProductRegistration으로 보증정보 보완
                if serial_number:
                    reg = reg_map.get((item.product_id, serial_number))
                    if reg:
                        warranty_end = reg.warranty_end

            if warranty_end:
                warranty_status = 'valid' if warranty_end >= today else 'expired'
        elif partner:
            customer_name = partner.name
            phone = partner.phone or ''

        service_count = svc_map.get((item.order.customer_id, item.product_id), 0) if customer else 0

        result.append({
            'item': item,
            'order': item.order,
            'product': item.product,
            'customer_name': customer_name,
            'phone': phone,
            'serial_number': serial_number,
            'warranty_end': warranty_end,
            'warranty_status': warranty_status,
            'service_count': service_count,
        })

    return result


class SoldProductListView(LoginRequiredMixin, TemplateView):
    template_name = 'sales/sold_product_list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.inventory.models import Product

        qs = _build_sold_product_queryset(self.request)

        # 보증상태 필터 (post-query)
        warranty_filter = self.request.GET.get('warranty_status', '').strip()

        # 페이지네이션
        paginator = Paginator(qs, 20)
        page_number = self.request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        enriched = _enrich_sold_items(page_obj.object_list)

        # 보증상태 필터 적용 (post-processing)
        if warranty_filter == 'valid':
            enriched = [r for r in enriched if r['warranty_status'] == 'valid']
        elif warranty_filter == 'expired':
            enriched = [r for r in enriched if r['warranty_status'] == 'expired']

        ctx['sold_items'] = enriched
        ctx['page_obj'] = page_obj
        ctx['is_paginated'] = page_obj.has_other_pages()
        ctx['product_type_choices'] = Product.ProductType.choices
        return ctx


class SoldProductDetailView(LoginRequiredMixin, DetailView):
    model = OrderItem
    template_name = 'sales/sold_product_detail.html'
    context_object_name = 'order_item'

    def get_queryset(self):
        return OrderItem.objects.filter(
            order__status__in=[Order.Status.SHIPPED, Order.Status.DELIVERED],
        ).select_related(
            'order', 'order__customer', 'order__partner', 'product',
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.warranty.models import ProductRegistration
        from apps.service.models import ServiceRequest
        from .models import CustomerPurchase

        item = self.object
        customer = item.order.customer
        today = date.today()

        # 보증 정보
        warranty_info = {
            'serial_number': '',
            'warranty_end': None,
            'is_valid': False,
            'source': None,
        }
        if customer:
            # CustomerPurchase에서 해당 제품 구매내역 조회
            purchase = CustomerPurchase.objects.filter(
                customer=customer, product=item.product, is_active=True,
            ).first()
            if purchase:
                warranty_info['serial_number'] = purchase.serial_number or ''
                warranty_info['warranty_end'] = purchase.warranty_end
                if purchase.warranty_end:
                    warranty_info['is_valid'] = purchase.warranty_end >= today
                    warranty_info['source'] = 'customer'

                # ProductRegistration 보완
                if purchase.serial_number:
                    try:
                        reg = ProductRegistration.objects.get(
                            serial_number=purchase.serial_number,
                            product=item.product,
                        )
                        warranty_info['warranty_end'] = reg.warranty_end
                        warranty_info['is_valid'] = reg.warranty_end >= today
                        warranty_info['source'] = 'registration'
                        warranty_info['registration'] = reg
                    except ProductRegistration.DoesNotExist:
                        pass

        ctx['warranty_info'] = warranty_info

        # AS 이력
        service_requests = []
        if customer:
            service_requests = ServiceRequest.objects.filter(
                customer=customer,
                product=item.product,
            ).prefetch_related('repairs').order_by('-received_date')

        ctx['service_requests'] = service_requests
        return ctx


class SoldProductExcelView(LoginRequiredMixin, View):
    def get(self, request):
        from apps.core.excel import export_to_excel

        qs = _build_sold_product_queryset(request)
        enriched = _enrich_sold_items(qs[:5000])  # 최대 5000건

        # 보증상태 필터
        warranty_filter = request.GET.get('warranty_status', '').strip()
        if warranty_filter == 'valid':
            enriched = [r for r in enriched if r['warranty_status'] == 'valid']
        elif warranty_filter == 'expired':
            enriched = [r for r in enriched if r['warranty_status'] == 'expired']

        headers = [
            ('주문번호', 18), ('주문일', 12), ('제품코드', 15), ('제품명', 25),
            ('수량', 8), ('단가', 15), ('금액', 15), ('고객명', 15),
            ('연락처', 15), ('시리얼번호', 20), ('보증만료일', 12),
            ('보증상태', 10), ('AS건수', 8),
        ]

        warranty_label = {'valid': '유효', 'expired': '만료', 'none': '미등록'}

        rows = []
        for r in enriched:
            rows.append([
                r['order'].order_number,
                r['order'].order_date.strftime('%Y-%m-%d') if r['order'].order_date else '',
                r['product'].code,
                r['product'].name,
                r['item'].quantity,
                int(r['item'].unit_price),
                int(r['item'].amount),
                r['customer_name'],
                r['phone'],
                r['serial_number'],
                r['warranty_end'].strftime('%Y-%m-%d') if r['warranty_end'] else '',
                warranty_label.get(r['warranty_status'], '미등록'),
                r['service_count'],
            ])

        return export_to_excel(
            '판매제품목록', headers, rows,
            money_columns=[5, 6],
        )


# ── 견적서 ────────────────────────────────────────────────

class QuotationListView(LoginRequiredMixin, ListView):
    model = Quotation
    template_name = 'sales/quote_list.html'
    context_object_name = 'quotes'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related('partner', 'customer')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(quote_number__icontains=q)
                | Q(partner__name__icontains=q)
                | Q(customer__name__icontains=q)
            )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs


class QuotationCreateView(LoginRequiredMixin, CreateView):
    model = Quotation
    form_class = QuotationForm
    template_name = 'sales/quote_form.html'
    success_url = reverse_lazy('sales:quote_list')

    def get_initial(self):
        initial = super().get_initial()
        from apps.core.utils import generate_document_number
        initial['quote_number'] = generate_document_number(
            Quotation, 'quote_number', 'QT',
        )
        from apps.accounting.models import BankAccount
        default_bank = BankAccount.objects.filter(
            is_active=True, is_default=True,
        ).first()
        if default_bank:
            initial['bank_account'] = default_bank.pk
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = QuotationItemFormSet(self.request.POST)
        else:
            ctx['formset'] = QuotationItemFormSet()
        ctx['product_units_json'] = _product_units_json()
        ctx['product_costs_json'] = _product_costs_json()
        return ctx

    def form_valid(self, form):
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


class QuotationDetailView(LoginRequiredMixin, DetailView):
    model = Quotation
    template_name = 'sales/quote_detail.html'
    context_object_name = 'quote'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'partner', 'customer', 'bank_account',
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        items = self.object.quote_items.select_related('product')
        ctx['items'] = items
        ctx['total_cost'] = sum(i.total_cost for i in items)
        ctx['total_profit'] = sum(i.profit for i in items)
        total_amount = int(self.object.total_amount)
        ctx['total_profit_rate'] = (
            round(ctx['total_profit'] / total_amount * 100, 1)
            if total_amount else 0
        )
        return ctx


class QuotationUpdateView(LoginRequiredMixin, UpdateView):
    model = Quotation
    form_class = QuotationForm
    template_name = 'sales/quote_form.html'
    success_url = reverse_lazy('sales:quote_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = QuotationItemFormSet(
                self.request.POST, instance=self.object,
            )
        else:
            ctx['formset'] = QuotationItemFormSet(instance=self.object)
        ctx['product_units_json'] = _product_units_json()
        ctx['product_costs_json'] = _product_costs_json()
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        formset = ctx['formset']
        if formset.is_valid():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
            # vat_included 변경 시 모든 항목 VAT 재계산
            for item in self.object.quote_items.all():
                item.save()
            self.object.update_total()
            return redirect(self.get_success_url())
        return self.form_invalid(form)


class QuotationConvertView(LoginRequiredMixin, View):
    """견적서 → 주문 전환"""

    def post(self, request, pk):
        quote = get_object_or_404(Quotation, pk=pk)
        if quote.status == Quotation.Status.CONVERTED:
            messages.error(request, '이미 주문으로 전환된 견적입니다.')
            return HttpResponseRedirect(
                reverse_lazy('sales:quote_detail', kwargs={'pk': pk})
            )

        from apps.core.utils import generate_document_number

        with transaction.atomic():
            order = Order.objects.create(
                order_number=generate_document_number(Order, 'order_number', 'ORD'),
                partner=quote.partner,
                customer=quote.customer,
                order_date=date.today(),
                delivery_date=None,
                status=Order.Status.DRAFT,
                vat_included=quote.vat_included,
                bank_account=quote.bank_account,
                shipping_address=getattr(quote, 'shipping_address', ''),
                created_by=request.user,
            )

            for qi in quote.quote_items.all():
                OrderItem.objects.create(
                    order=order,
                    product=qi.product,
                    quantity=qi.quantity,
                    cost_price=qi.cost_price,
                    unit_price=qi.unit_price,
                    discount_rate=qi.discount_rate,
                    discount_amount=qi.discount_amount,
                    created_by=request.user,
                )

            order.update_total()
            quote.status = Quotation.Status.CONVERTED
            quote.converted_order = order
            quote.save(update_fields=[
                'status', 'converted_order', 'updated_at',
            ])

        messages.success(
            request,
            f'주문 {order.order_number}으로 전환되었습니다.',
        )
        return HttpResponseRedirect(
            reverse_lazy('sales:order_detail', kwargs={'pk': order.pk})
        )


class QuotationImportView(ManagerRequiredMixin, TemplateView):
    template_name = 'core/import.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = '견적서 일괄 가져오기'
        ctx['cancel_url'] = reverse_lazy('sales:quote_list')
        ctx['sample_url'] = reverse_lazy(
            'sales:quote_import_sample',
        )
        ctx['field_hints'] = [
            '견적번호(quote_number)가 동일하면 수정됩니다.',
            'partner_code: 거래처코드',
            'customer_name: 고객명',
            'status: DRAFT(작성중), SENT(발송), '
            'ACCEPTED(수락), REJECTED(거절)',
        ]
        return ctx

    def post(self, request, *args, **kwargs):
        from .resources import QuotationResource
        action = request.POST.get('action', 'preview')
        import_file = request.FILES.get('import_file')
        if not import_file:
            messages.error(request, '파일을 선택해주세요.')
            return self.get(request, *args, **kwargs)
        resource = QuotationResource()
        try:
            data = _parse_import_file(request, import_file)
            if data is None:
                messages.error(
                    request, '지원하지 않는 파일 형식입니다.',
                )
                return self.get(request, *args, **kwargs)
        except (ValueError, KeyError, TypeError,
                UnicodeDecodeError) as e:
            messages.error(request, f'파일 읽기 오류: {e}')
            return self.get(request, *args, **kwargs)
        if action == 'preview':
            result = resource.import_data(data, dry_run=True)
            ctx = self.get_context_data(**kwargs)
            ctx['preview'] = _build_preview(result, data)
            ctx['errors'] = _collect_errors(result)
            return self.render_to_response(ctx)
        else:
            result = resource.import_data(data, dry_run=False)
            if result.has_errors():
                ctx = self.get_context_data(**kwargs)
                ctx['errors'] = _collect_errors(result)
                return self.render_to_response(ctx)
            total = (result.totals.get('new', 0)
                     + result.totals.get('update', 0))
            messages.success(
                request, f'{total}건 가져오기 완료.',
            )
            return HttpResponseRedirect(
                str(reverse_lazy('sales:quote_list')),
            )


class QuotationImportSampleView(ManagerRequiredMixin, View):
    def get(self, request):
        from apps.core.excel import export_to_excel
        headers = [
            ('quote_number', 18), ('partner_code', 15),
            ('customer_name', 15), ('quote_date', 12),
            ('valid_until', 12), ('status', 10),
            ('notes', 30),
        ]
        rows = [
            ['QT-2026-001', 'P-001', '홍길동',
             '2026-03-01', '2026-04-01', 'DRAFT', ''],
        ]
        return export_to_excel(
            '견적서_가져오기_양식', headers, rows,
            filename='견적서_가져오기_양식.xlsx',
            required_columns=[0, 3, 4],  # quote_number, quote_date, valid_until
        )


# ── 배송 추적 ─────────────────────────────────────────────

class ShipmentListView(LoginRequiredMixin, ListView):
    model = Shipment
    template_name = 'sales/shipment_list.html'
    context_object_name = 'shipments'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related('order', 'order__partner')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(shipment_number__icontains=q)
                | Q(tracking_number__icontains=q)
                | Q(order__order_number__icontains=q)
            )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs


class ShipmentCreateView(LoginRequiredMixin, CreateView):
    model = Shipment
    fields = [
        'shipment_number', 'shipping_type', 'carrier', 'tracking_number',
        'receiver_name', 'receiver_phone', 'receiver_address', 'notes',
    ]
    template_name = 'sales/shipment_form.html'

    def get_initial(self):
        initial = super().get_initial()
        from apps.core.utils import generate_document_number
        initial['shipment_number'] = generate_document_number(Shipment, 'shipment_number', 'SH')
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            field.widget.attrs.setdefault('class', 'form-input')
        return form

    def form_valid(self, form):
        form.instance.order_id = self.kwargs['order_pk']
        form.instance.created_by = self.request.user
        form.instance.status = Shipment.Status.PREPARING
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy(
            'sales:order_detail',
            kwargs={'pk': self.kwargs['order_pk']},
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['order'] = get_object_or_404(Order, pk=self.kwargs['order_pk'])
        return ctx


class ShipmentDetailView(LoginRequiredMixin, DetailView):
    model = Shipment
    template_name = 'sales/shipment_detail.html'
    context_object_name = 'shipment'


class ShipmentUpdateView(LoginRequiredMixin, UpdateView):
    model = Shipment
    fields = [
        'shipping_type', 'carrier', 'tracking_number', 'status',
        'shipped_date', 'delivered_date',
        'receiver_name', 'receiver_phone', 'receiver_address', 'notes',
    ]
    template_name = 'sales/shipment_form.html'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            field.widget.attrs.setdefault('class', 'form-input')
        return form

    def get_success_url(self):
        return reverse_lazy(
            'sales:shipment_detail', kwargs={'pk': self.object.pk},
        )


class PartialShipmentView(LoginRequiredMixin, TemplateView):
    """부분 출고 — 주문항목별 출고수량 지정"""
    template_name = 'sales/partial_shipment.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        order = get_object_or_404(
            Order.objects.prefetch_related('items__product'),
            pk=self.kwargs['pk'],
        )
        ctx['order'] = order
        ctx['items'] = [
            item for item in order.items.all()
            if item.remaining_quantity > 0
        ]
        return ctx

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        if order.status not in ('CONFIRMED', 'PARTIAL_SHIPPED'):
            messages.error(request, '출고 가능한 상태가 아닙니다.')
            return redirect('sales:order_detail', pk=pk)

        from apps.sales.signals import InsufficientStockError
        from apps.core.utils import generate_document_number

        try:
            with transaction.atomic():
                shipment = Shipment.objects.create(
                    order=order,
                    shipping_type='PARCEL',
                    status='SHIPPED',
                    shipped_date=date.today(),
                    receiver_name=request.POST.get(
                        'receiver_name', '',
                    ),
                    tracking_number=request.POST.get(
                        'tracking_number', '',
                    ),
                    created_by=request.user,
                )

                created_any = False
                for item in order.items.all():
                    qty_str = request.POST.get(
                        f'qty_{item.pk}', '0',
                    )
                    qty = int(qty_str) if qty_str else 0
                    if qty <= 0:
                        continue
                    remaining = item.remaining_quantity
                    if qty > remaining:
                        qty = remaining
                    ShipmentItem.objects.create(
                        shipment=shipment,
                        order_item=item,
                        quantity=qty,
                        created_by=request.user,
                    )
                    created_any = True

                if not created_any:
                    raise ValueError(
                        '출고할 항목이 없습니다.',
                    )

            messages.success(
                request,
                f'부분 출고 완료 ({shipment.shipment_number})',
            )
        except InsufficientStockError as e:
            messages.error(request, str(e))
        except ValueError as e:
            messages.error(request, str(e))

        return redirect('sales:order_detail', pk=pk)


class PartnerAnalysisView(ManagerRequiredMixin, TemplateView):
    """거래처별 매출/수익 분석"""
    template_name = 'sales/partner_analysis.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()

        # 기간 필터 (기본: 올해)
        date_from = self.request.GET.get('date_from', f'{today.year}-01-01')
        date_to = self.request.GET.get('date_to', today.strftime('%Y-%m-%d'))
        sort_by = self.request.GET.get('sort', '-revenue')

        context['date_from'] = date_from
        context['date_to'] = date_to
        context['sort_by'] = sort_by

        # 거래처별 집계: OrderItem 기반
        partner_stats = (
            OrderItem.objects.filter(
                order__is_active=True,
                order__partner__isnull=False,
                order__status__in=['CONFIRMED', 'SHIPPED', 'DELIVERED'],
                order__order_date__gte=date_from,
                order__order_date__lte=date_to,
                is_active=True,
            )
            .values(
                'order__partner__id',
                'order__partner__name',
                'order__partner__code',
            )
            .annotate(
                order_count=Count('order', distinct=True),
                revenue=Sum('amount'),
                total_cost=Sum(
                    ExpressionWrapper(
                        F('quantity') * F('cost_price'),
                        output_field=DecimalField(max_digits=20, decimal_places=0),
                    )
                ),
            )
            .order_by()  # clear default ordering
        )

        # 후처리: 이익, 이익률 계산
        results = []
        total_revenue = Decimal('0')
        total_cost_sum = Decimal('0')
        total_orders = 0
        for row in partner_stats:
            revenue = row['revenue'] or Decimal('0')
            cost = row['total_cost'] or Decimal('0')
            profit = revenue - cost
            profit_rate = (
                round(float(profit) / float(revenue) * 100, 1)
                if revenue > 0 else 0
            )
            results.append({
                'partner_id': row['order__partner__id'],
                'partner_name': row['order__partner__name'],
                'partner_code': row['order__partner__code'],
                'order_count': row['order_count'],
                'revenue': revenue,
                'cost': cost,
                'profit': profit,
                'profit_rate': profit_rate,
            })
            total_revenue += revenue
            total_cost_sum += cost
            total_orders += row['order_count']

        # 정렬
        sort_map = {
            'name': ('partner_name', False),
            '-name': ('partner_name', True),
            'orders': ('order_count', False),
            '-orders': ('order_count', True),
            'revenue': ('revenue', False),
            '-revenue': ('revenue', True),
            'cost': ('cost', False),
            '-cost': ('cost', True),
            'profit': ('profit', False),
            '-profit': ('profit', True),
            'profit_rate': ('profit_rate', False),
            '-profit_rate': ('profit_rate', True),
        }
        sort_key, sort_reverse = sort_map.get(sort_by, ('revenue', True))
        results.sort(key=lambda x: x[sort_key], reverse=sort_reverse)

        context['partner_stats'] = results
        context['total_revenue'] = total_revenue
        context['total_cost'] = total_cost_sum
        context['total_profit'] = total_revenue - total_cost_sum
        context['total_profit_rate'] = (
            round(float(total_revenue - total_cost_sum) / float(total_revenue) * 100, 1)
            if total_revenue > 0 else 0
        )
        context['total_orders'] = total_orders

        return context


# ── 택배사 관리 ────────────────────────────────────────────


class ShippingCarrierListView(LoginRequiredMixin, ListView):
    model = ShippingCarrier
    template_name = 'sales/carrier_list.html'
    context_object_name = 'carriers'

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class ShippingCarrierCreateView(LoginRequiredMixin, CreateView):
    model = ShippingCarrier
    form_class = ShippingCarrierForm
    template_name = 'sales/carrier_form.html'
    success_url = reverse_lazy('sales:carrier_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class ShippingCarrierUpdateView(LoginRequiredMixin, UpdateView):
    model = ShippingCarrier
    form_class = ShippingCarrierForm
    template_name = 'sales/carrier_form.html'
    success_url = reverse_lazy('sales:carrier_list')


# ── 배송 추적 ─────────────────────────────────────────────


class ShipmentTrackingView(LoginRequiredMixin, DetailView):
    """배송 추적 조회 뷰 (Shipment 상세에서 접근)"""
    model = Shipment
    template_name = 'sales/shipment_tracking.html'
    context_object_name = 'shipment'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['tracking_list'] = self.object.tracking_history.filter(
            is_active=True,
        ).order_by('-tracked_at')
        return ctx
