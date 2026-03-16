import tablib
from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView

from apps.core.mixins import ManagerRequiredMixin
from .models import (
    Partner, Customer, Order, OrderItem,
    Quotation, QuotationItem, Shipment,
)
from .forms import PartnerForm, CustomerForm, OrderForm, OrderItemFormSet
from .commission import CommissionRate, CommissionRecord
from .commission_forms import CommissionRateForm, CommissionRecordForm
from .resources import PartnerResource, CustomerResource


class PartnerListView(LoginRequiredMixin, ListView):
    model = Partner
    template_name = 'sales/partner_list.html'
    context_object_name = 'partners'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(name__icontains=q)
        return qs


class PartnerCreateView(LoginRequiredMixin, CreateView):
    model = Partner
    form_class = PartnerForm
    template_name = 'sales/partner_form.html'
    success_url = reverse_lazy('sales:partner_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class PartnerUpdateView(LoginRequiredMixin, UpdateView):
    model = Partner
    form_class = PartnerForm
    template_name = 'sales/partner_form.html'
    success_url = reverse_lazy('sales:partner_list')


class CustomerListView(LoginRequiredMixin, ListView):
    model = Customer
    template_name = 'sales/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(name__icontains=q) | qs.filter(phone__icontains=q)
        return qs


class CustomerCreateView(LoginRequiredMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'sales/customer_form.html'
    success_url = reverse_lazy('sales:customer_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class CustomerDetailView(LoginRequiredMixin, DetailView):
    model = Customer
    template_name = 'sales/customer_detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['orders'] = self.object.orders.all()
        ctx['service_requests'] = self.object.service_requests.all()
        return ctx


class CustomerUpdateView(LoginRequiredMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'sales/customer_form.html'
    success_url = reverse_lazy('sales:customer_list')


class OrderListView(LoginRequiredMixin, ListView):
    model = Order
    template_name = 'sales/order_list.html'
    context_object_name = 'orders'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs


class OrderCreateView(LoginRequiredMixin, CreateView):
    model = Order
    form_class = OrderForm
    template_name = 'sales/order_form.html'
    success_url = reverse_lazy('sales:order_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = OrderItemFormSet(self.request.POST)
        else:
            ctx['formset'] = OrderItemFormSet()
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
            return super().form_valid(form)
        return self.form_invalid(form)


class OrderDetailView(LoginRequiredMixin, DetailView):
    model = Order
    template_name = 'sales/order_detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['items'] = self.object.items.all()
        return ctx


class OrderUpdateView(LoginRequiredMixin, UpdateView):
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


# === 수수료율 ===
class CommissionRateListView(LoginRequiredMixin, ListView):
    model = CommissionRate
    template_name = 'sales/commission_rate_list.html'
    context_object_name = 'commission_rates'
    paginate_by = 20


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
        qs = super().get_queryset()
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

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


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
        orders = Order.objects.select_related('partner', 'customer').all()
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
    ext = import_file.name.rsplit('.', 1)[-1].lower()
    if ext == 'csv':
        return tablib.Dataset().load(import_file.read().decode('utf-8-sig'), format='csv')
    elif ext in ('xlsx', 'xls'):
        return tablib.Dataset().load(import_file.read(), format='xlsx')
    else:
        return None


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
        except Exception as e:
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
        except Exception as e:
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
        return export_to_excel(
            '고객_가져오기_양식', headers, rows,
            filename='고객_가져오기_양식.xlsx',
        )


# === 판매제품 통합 관리 ===

def _build_sold_product_queryset(request):
    """판매제품 목록 조회를 위한 공통 쿼리셋 빌더."""
    qs = OrderItem.objects.filter(
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
            | Q(order__customer__serial_number__icontains=q)
            | Q(order__order_number__icontains=q)
        )

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
    """OrderItem 목록에 대해 보증정보 맵(customer_id -> info)과 ProductRegistration 맵 생성."""
    from apps.warranty.models import ProductRegistration

    # Customer 기반 보증 정보 (customer_id -> Customer)
    customer_ids = set()
    serial_numbers = set()
    product_ids = set()
    for item in order_items:
        if item.order.customer_id:
            customer_ids.add(item.order.customer_id)
            if item.order.customer and item.order.customer.serial_number:
                serial_numbers.add(item.order.customer.serial_number)
        product_ids.add(item.product_id)

    # ProductRegistration 맵: (product_id, serial_number) -> registration
    reg_map = {}
    if serial_numbers:
        regs = ProductRegistration.objects.filter(
            serial_number__in=serial_numbers,
        ).select_related('product')
        for reg in regs:
            reg_map[(reg.product_id, reg.serial_number)] = reg

    return reg_map


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

    reg_map = _get_warranty_map(items_list)
    svc_map = _get_service_count_map(items_list)
    today = date.today()

    result = []
    for item in items_list:
        customer = item.order.customer
        partner = item.order.partner

        # 고객/거래처명
        customer_name = ''
        phone = ''
        serial_number = ''
        warranty_end = None
        warranty_status = 'none'  # none / valid / expired

        if customer:
            customer_name = customer.name
            phone = customer.phone or ''
            serial_number = customer.serial_number or ''
            warranty_end = customer.warranty_end

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
            warranty_info['serial_number'] = customer.serial_number or ''
            warranty_info['warranty_end'] = customer.warranty_end
            if customer.warranty_end:
                warranty_info['is_valid'] = customer.warranty_end >= today
                warranty_info['source'] = 'customer'

            # ProductRegistration 보완
            if customer.serial_number:
                try:
                    reg = ProductRegistration.objects.get(
                        serial_number=customer.serial_number,
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
        qs = super().get_queryset().select_related('partner', 'customer')
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
    fields = [
        'quote_number', 'partner', 'customer', 'quote_date',
        'valid_until', 'shipping_address', 'notes',
    ]
    template_name = 'sales/quote_form.html'
    success_url = reverse_lazy('sales:quote_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            field.widget.attrs.setdefault('class', 'form-input')
        return form

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class QuotationDetailView(LoginRequiredMixin, DetailView):
    model = Quotation
    template_name = 'sales/quote_detail.html'
    context_object_name = 'quote'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['items'] = self.object.quote_items.select_related('product')
        return ctx


class QuotationUpdateView(LoginRequiredMixin, UpdateView):
    model = Quotation
    fields = [
        'quote_number', 'partner', 'customer', 'quote_date',
        'valid_until', 'status', 'notes',
    ]
    template_name = 'sales/quote_form.html'
    success_url = reverse_lazy('sales:quote_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            field.widget.attrs.setdefault('class', 'form-input')
        return form


class QuotationConvertView(LoginRequiredMixin, View):
    """견적서 → 주문 전환"""

    def post(self, request, pk):
        quote = Quotation.objects.get(pk=pk)
        if quote.status == Quotation.Status.CONVERTED:
            messages.error(request, '이미 주문으로 전환된 견적입니다.')
            return HttpResponseRedirect(
                reverse_lazy('sales:quote_detail', kwargs={'pk': pk})
            )

        from apps.core.utils import generate_number
        order = Order.objects.create(
            order_number=generate_number(Order, 'ORD'),
            partner=quote.partner,
            customer=quote.customer,
            order_date=date.today(),
            delivery_date=None,
            status=Order.Status.DRAFT,
            shipping_address=getattr(quote, 'shipping_address', ''),
            created_by=request.user,
        )

        for qi in quote.quote_items.all():
            OrderItem.objects.create(
                order=order,
                product=qi.product,
                quantity=qi.quantity,
                unit_price=qi.unit_price,
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


# ── 배송 추적 ─────────────────────────────────────────────

class ShipmentListView(LoginRequiredMixin, ListView):
    model = Shipment
    template_name = 'sales/shipment_list.html'
    context_object_name = 'shipments'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().select_related('order', 'order__partner')
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
        'shipment_number', 'carrier', 'tracking_number',
        'receiver_name', 'receiver_phone', 'receiver_address', 'notes',
    ]
    template_name = 'sales/shipment_form.html'

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
        ctx['order'] = Order.objects.get(pk=self.kwargs['order_pk'])
        return ctx


class ShipmentDetailView(LoginRequiredMixin, DetailView):
    model = Shipment
    template_name = 'sales/shipment_detail.html'
    context_object_name = 'shipment'


class ShipmentUpdateView(LoginRequiredMixin, UpdateView):
    model = Shipment
    fields = [
        'carrier', 'tracking_number', 'status',
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
