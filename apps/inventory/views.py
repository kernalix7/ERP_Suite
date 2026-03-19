import tablib
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView, TemplateView

from apps.core.barcode import generate_barcode_image, generate_qr_image, generate_barcode_label_pdf
from apps.core.mixins import ManagerRequiredMixin
from .models import Category, Product, Warehouse, StockMovement, StockTransfer
from .forms import ProductForm, CategoryForm, WarehouseForm, StockMovementForm, StockTransferForm
from .resources import ProductResource


class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'inventory/product_list.html'
    context_object_name = 'products'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().select_related('category')
        q = self.request.GET.get('q')
        product_type = self.request.GET.get('type')
        if q:
            qs = qs.filter(name__icontains=q) | qs.filter(code__icontains=q)
        if product_type:
            qs = qs.filter(product_type=product_type)
        return qs


class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'inventory/product_form.html'
    success_url = reverse_lazy('inventory:product_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class ProductDetailView(LoginRequiredMixin, DetailView):
    model = Product
    template_name = 'inventory/product_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['movements'] = self.object.movements.select_related('warehouse')[:20]
        return context


class ProductUpdateView(LoginRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'inventory/product_form.html'
    success_url = reverse_lazy('inventory:product_list')


class ProductDeleteView(ManagerRequiredMixin, DeleteView):
    model = Product
    success_url = reverse_lazy('inventory:product_list')
    template_name = 'inventory/product_confirm_delete.html'

    def form_valid(self, form):
        self.object.soft_delete()
        return self.get_success_url() and __import__('django.http', fromlist=['HttpResponseRedirect']).HttpResponseRedirect(self.get_success_url())

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.soft_delete()
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(self.get_success_url())


class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = 'inventory/category_list.html'
    context_object_name = 'categories'


class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'inventory/category_form.html'
    success_url = reverse_lazy('inventory:category_list')


class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'inventory/category_form.html'
    success_url = reverse_lazy('inventory:category_list')


class WarehouseListView(LoginRequiredMixin, ListView):
    model = Warehouse
    template_name = 'inventory/warehouse_list.html'
    context_object_name = 'warehouses'


class WarehouseCreateView(LoginRequiredMixin, CreateView):
    model = Warehouse
    form_class = WarehouseForm
    template_name = 'inventory/warehouse_form.html'
    success_url = reverse_lazy('inventory:warehouse_list')


class WarehouseUpdateView(LoginRequiredMixin, UpdateView):
    model = Warehouse
    form_class = WarehouseForm
    template_name = 'inventory/warehouse_form.html'
    success_url = reverse_lazy('inventory:warehouse_list')


class StockMovementListView(LoginRequiredMixin, ListView):
    model = StockMovement
    template_name = 'inventory/movement_list.html'
    context_object_name = 'movements'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().select_related('product', 'warehouse')
        movement_type = self.request.GET.get('type')
        if movement_type:
            qs = qs.filter(movement_type=movement_type)
        return qs


class StockMovementCreateView(LoginRequiredMixin, CreateView):
    model = StockMovement
    form_class = StockMovementForm
    template_name = 'inventory/movement_form.html'
    success_url = reverse_lazy('inventory:movement_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class StockMovementDetailView(LoginRequiredMixin, DetailView):
    model = StockMovement
    template_name = 'inventory/movement_detail.html'


class StockStatusView(LoginRequiredMixin, TemplateView):
    template_name = 'inventory/stock_status.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        products = Product.objects.select_related('category').all()
        q = self.request.GET.get('q')
        if q:
            products = products.filter(name__icontains=q) | products.filter(code__icontains=q)
        context['products'] = products
        context['low_stock'] = [p for p in products if p.is_below_safety_stock]
        return context


# === Excel 다운로드 ===
class ProductExcelView(LoginRequiredMixin, View):
    def get(self, request):
        from apps.core.excel import export_to_excel
        products = Product.objects.select_related('category').all()
        headers = [
            ('제품코드', 15), ('제품명', 25), ('유형', 10),
            ('판매단가', 15), ('원가', 15), ('현재고', 10), ('안전재고', 10),
        ]
        rows = [
            [
                p.code, p.name, p.get_product_type_display(),
                int(p.unit_price), int(p.cost_price),
                p.current_stock, p.safety_stock,
            ]
            for p in products
        ]
        return export_to_excel('제품목록', headers, rows, money_columns=[3, 4])


# === 창고간 이동 ===
class StockTransferListView(LoginRequiredMixin, ListView):
    model = StockTransfer
    template_name = 'inventory/transfer_list.html'
    context_object_name = 'transfers'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().select_related(
            'product', 'from_warehouse', 'to_warehouse',
        )


class StockTransferCreateView(LoginRequiredMixin, CreateView):
    model = StockTransfer
    form_class = StockTransferForm
    template_name = 'inventory/transfer_form.html'
    success_url = reverse_lazy('inventory:transfer_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


# === Excel 일괄 가져오기 ===
class ProductImportView(ManagerRequiredMixin, TemplateView):
    template_name = 'core/import.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = '제품 일괄 가져오기'
        ctx['cancel_url'] = reverse_lazy('inventory:product_list')
        ctx['sample_url'] = reverse_lazy('inventory:product_import_sample')
        ctx['field_hints'] = [
            '제품코드(code)가 동일하면 기존 제품이 수정됩니다.',
            '제품유형(product_type): RAW(원자재), SEMI(반제품), FINISHED(완제품)',
            '카테고리명(category__name)이 존재하지 않으면 자동으로 생성됩니다.',
        ]
        return ctx

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action', 'preview')
        import_file = request.FILES.get('import_file')

        if not import_file:
            messages.error(request, '파일을 선택해주세요.')
            return self.get(request, *args, **kwargs)

        resource = ProductResource()
        ext = import_file.name.rsplit('.', 1)[-1].lower()

        try:
            if ext == 'csv':
                data = tablib.Dataset().load(import_file.read().decode('utf-8-sig'), format='csv')
            elif ext in ('xlsx', 'xls'):
                data = tablib.Dataset().load(import_file.read(), format='xlsx')
            else:
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
            messages.success(request, f'제품 {total}건이 성공적으로 가져오기 되었습니다.')
            return HttpResponseRedirect(reverse_lazy('inventory:product_list'))


class ProductImportSampleView(ManagerRequiredMixin, View):
    def get(self, request):
        from apps.core.excel import export_to_excel
        headers = [
            ('code', 15), ('name', 25), ('product_type', 12),
            ('category__name', 15), ('unit', 8),
            ('unit_price', 15), ('cost_price', 15), ('safety_stock', 12),
        ]
        rows = [
            ['PRD-001', '샘플 제품', 'FINISHED', '전자제품', 'EA', 10000, 7000, 10],
            ['PRD-002', '샘플 원자재', 'RAW', '원자재', 'KG', 5000, 3000, 50],
        ]
        return export_to_excel(
            '제품_가져오기_양식', headers, rows,
            filename='제품_가져오기_양식.xlsx', money_columns=[5, 6],
        )


# === 가져오기 공통 헬퍼 ===
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


# === 바코드/QR코드 ===
class ProductBarcodeView(LoginRequiredMixin, DetailView):
    """제품 바코드 라벨 표시"""
    model = Product
    template_name = 'inventory/product_barcode.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object
        product_url = self.request.build_absolute_uri(
            reverse('inventory:product_detail', kwargs={'pk': product.pk})
        )
        context['barcode_image'] = generate_barcode_image(product.code)
        context['qr_image'] = generate_qr_image(product_url)
        context['product_url'] = product_url
        return context


class ProductBarcodePrintView(LoginRequiredMixin, View):
    """제품 바코드 라벨 PDF 출력"""
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        return generate_barcode_label_pdf(product, request=request)


class BarcodeScanView(LoginRequiredMixin, TemplateView):
    """바코드/QR 스캐너 페이지"""
    template_name = 'inventory/barcode_scan.html'

    def post(self, request, *args, **kwargs):
        code = request.POST.get('code', '').strip()
        if not code:
            messages.error(request, '코드를 입력해주세요.')
            return redirect('inventory:barcode_scan')

        # 제품코드로 검색
        try:
            product = Product.objects.get(code=code)
            return redirect('inventory:product_detail', pk=product.pk)
        except Product.DoesNotExist:
            pass

        # 시리얼번호로 검색 (정품등록)
        from apps.warranty.models import ProductRegistration
        try:
            reg = ProductRegistration.objects.get(serial_number=code)
            return redirect('warranty:registration_detail', pk=reg.pk)
        except ProductRegistration.DoesNotExist:
            pass

        # URL에서 pk 추출 시도 (QR코드가 제품 URL인 경우)
        import re
        match = re.search(r'/inventory/products/(\d+)/', code)
        if match:
            pk = int(match.group(1))
            if Product.objects.filter(pk=pk).exists():
                return redirect('inventory:product_detail', pk=pk)

        messages.warning(request, f'"{code}"에 해당하는 제품을 찾을 수 없습니다.')
        return redirect('inventory:barcode_scan')
