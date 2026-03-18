from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, CreateView, UpdateView, DetailView

from .models import PurchaseOrder, PurchaseOrderItem, GoodsReceipt, GoodsReceiptItem
from .forms import (
    PurchaseOrderForm, PurchaseOrderItemFormSet,
    GoodsReceiptForm, GoodsReceiptItemForm,
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


class PurchaseOrderCreateView(LoginRequiredMixin, CreateView):
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'purchase/po_form.html'
    success_url = reverse_lazy('purchase:po_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = PurchaseOrderItemFormSet(self.request.POST)
        else:
            ctx['formset'] = PurchaseOrderItemFormSet()
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


class PurchaseOrderDetailView(LoginRequiredMixin, DetailView):
    model = PurchaseOrder
    template_name = 'purchase/po_detail.html'
    context_object_name = 'order'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['items'] = self.object.items.select_related('product').all()
        ctx['receipts'] = self.object.receipts.prefetch_related('items__po_item__product').all()
        return ctx


class PurchaseOrderUpdateView(LoginRequiredMixin, UpdateView):
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'purchase/po_form.html'
    success_url = reverse_lazy('purchase:po_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = PurchaseOrderItemFormSet(self.request.POST, instance=self.object)
        else:
            ctx['formset'] = PurchaseOrderItemFormSet(instance=self.object)
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        formset = ctx['formset']
        if formset.is_valid():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
            self.object.update_total()
            return super().form_valid(form)
        return self.form_invalid(form)


# ─── 입고 ────────────────────────────────────────────────

class GoodsReceiptCreateView(LoginRequiredMixin, CreateView):
    model = GoodsReceipt
    form_class = GoodsReceiptForm
    template_name = 'purchase/receipt_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.purchase_order = get_object_or_404(PurchaseOrder, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['purchase_order'] = self.purchase_order
        ctx['po_items'] = self.purchase_order.items.select_related('product').all()
        return ctx

    def form_valid(self, form):
        form.instance.purchase_order = self.purchase_order
        form.instance.created_by = self.request.user
        self.object = form.save()

        # 입고 항목 처리
        po_items = self.purchase_order.items.all()
        for po_item in po_items:
            qty = self.request.POST.get(f'recv_qty_{po_item.pk}')
            inspected = self.request.POST.get(f'inspected_{po_item.pk}')
            if qty and int(qty) > 0:
                GoodsReceiptItem.objects.create(
                    goods_receipt=self.object,
                    po_item=po_item,
                    received_quantity=int(qty),
                    is_inspected=bool(inspected),
                )

        return super().form_valid(form)

    def get_success_url(self):
        return reverse('purchase:receipt_detail', kwargs={'pk': self.object.pk})


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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['items'] = self.object.items.select_related('po_item__product').all()
        return ctx
