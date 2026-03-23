import tablib
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models, transaction
from django.db.models import F, Sum
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView, TemplateView

from apps.core.barcode import generate_barcode_image, generate_qr_image, generate_barcode_label_pdf
from apps.core.import_views import BaseImportView
from apps.core.mixins import ManagerRequiredMixin

from .models import Category, Product, Warehouse, StockMovement, StockTransfer, StockCount, StockCountItem, StockLot
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
        # BOM 원가 정보
        if self.object.product_type == 'FINISHED':
            from apps.production.models import BOM
            bom = BOM.objects.filter(
                product=self.object, is_default=True,
            ).prefetch_related('items__material').first()
            if bom:
                context['default_bom'] = bom
                context['bom_cost'] = bom.total_material_cost
        return context


class ProductUpdateView(LoginRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'inventory/product_form.html'
    success_url = reverse_lazy('inventory:product_list')


class ProductBOMCostView(LoginRequiredMixin, View):
    """BOM 원가 조회 API (HTMX/JS용)"""
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        from apps.production.models import BOM
        bom = BOM.objects.filter(
            product=product, is_default=True,
        ).prefetch_related('items__material').first()
        if bom:
            return JsonResponse({
                'bom_cost': int(bom.total_material_cost),
                'bom_name': bom.name,
                'items': [
                    {
                        'material': item.material.name,
                        'quantity': float(item.quantity),
                        'unit_cost': int(item.material.cost_price),
                        'cost': int(item.material_cost),
                    }
                    for item in bom.items.select_related('material').all()
                ],
            })
        return JsonResponse({'bom_cost': None, 'message': 'BOM이 없습니다.'})


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
    paginate_by = 20


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
    paginate_by = 20


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

    def get_initial(self):
        initial = super().get_initial()
        from apps.core.utils import generate_document_number
        initial['movement_number'] = generate_document_number(StockMovement, 'movement_number', 'SM')
        return initial

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class StockMovementDetailView(LoginRequiredMixin, DetailView):
    model = StockMovement
    template_name = 'inventory/movement_detail.html'
    context_object_name = 'movement'


class StockStatusView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'inventory/stock_status.html'
    context_object_name = 'products'
    paginate_by = 50

    def get_queryset(self):
        qs = Product.objects.filter(is_active=True).select_related('category')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                models.Q(name__icontains=q) | models.Q(code__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        context['low_stock'] = qs.filter(
            current_stock__lt=F('safety_stock'),
        )
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

    def get_initial(self):
        initial = super().get_initial()
        from apps.core.utils import generate_document_number
        initial['transfer_number'] = generate_document_number(StockTransfer, 'transfer_number', 'ST')
        return initial

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

        try:
            from apps.core.import_views import parse_import_file
            data = parse_import_file(import_file)
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
            required_columns=[0, 1, 2],  # code, name, product_type
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


# === 카테고리/창고 일괄 가져오기 ===

class CategoryImportView(BaseImportView):
    resource_class = None  # lazy import
    page_title = '카테고리 일괄 가져오기'
    cancel_url = reverse_lazy('inventory:category_list')
    sample_url = reverse_lazy('inventory:category_import_sample')
    field_hints = [
        '카테고리명(name)이 동일하면 기존 카테고리가 수정됩니다.',
        'parent_name: 상위 카테고리명 (없으면 비워두세요)',
    ]

    def get_resource(self):
        from .resources import CategoryResource
        return CategoryResource()


class CategoryImportSampleView(ManagerRequiredMixin, View):
    def get(self, request):
        from apps.core.excel import export_to_excel
        headers = [('name', 20), ('parent_name', 20)]
        rows = [
            ['전자제품', ''],
            ['스마트폰', '전자제품'],
            ['원자재', ''],
        ]
        return export_to_excel(
            '카테고리_가져오기_양식', headers, rows,
            filename='카테고리_가져오기_양식.xlsx',
            required_columns=[0],  # name
        )


class WarehouseImportView(BaseImportView):
    resource_class = None
    page_title = '창고 일괄 가져오기'
    cancel_url = reverse_lazy('inventory:warehouse_list')
    sample_url = reverse_lazy('inventory:warehouse_import_sample')
    field_hints = [
        '창고코드(code)가 동일하면 기존 창고가 수정됩니다.',
    ]

    def get_resource(self):
        from .resources import WarehouseResource
        return WarehouseResource()


class WarehouseImportSampleView(ManagerRequiredMixin, View):
    def get(self, request):
        from apps.core.excel import export_to_excel
        headers = [('code', 15), ('name', 25), ('location', 30)]
        rows = [
            ['WH-001', '본사 창고', '서울시 강남구'],
            ['WH-002', '공장 창고', '경기도 화성시'],
        ]
        return export_to_excel(
            '창고_가져오기_양식', headers, rows,
            filename='창고_가져오기_양식.xlsx',
            required_columns=[0, 1],  # code, name
        )


# === 재고실사 ===
class StockCountListView(LoginRequiredMixin, ListView):
    model = StockCount
    template_name = 'inventory/stockcount_list.html'
    context_object_name = 'stock_counts'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(
            is_active=True,
        ).select_related('warehouse')


class StockCountCreateView(ManagerRequiredMixin, TemplateView):
    """재고실사 생성 — 선택한 창고의 모든 활성 제품을 항목으로 추가"""
    template_name = 'inventory/stockcount_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['warehouses'] = Warehouse.objects.filter(is_active=True)
        return ctx

    def post(self, request, *args, **kwargs):
        from datetime import date
        warehouse_id = request.POST.get('warehouse')
        count_date = request.POST.get('count_date', date.today().isoformat())

        if not warehouse_id:
            messages.error(request, '창고를 선택해주세요.')
            return self.get(request, *args, **kwargs)

        warehouse = get_object_or_404(Warehouse, pk=warehouse_id)

        with transaction.atomic():
            sc = StockCount.objects.create(
                warehouse=warehouse,
                count_date=count_date,
                status='DRAFT',
                created_by=request.user,
            )
            # 모든 활성 제품에 대해 항목 생성
            products = Product.objects.filter(is_active=True).order_by('code')
            items = []
            for product in products:
                items.append(StockCountItem(
                    stock_count=sc,
                    product=product,
                    system_quantity=product.current_stock,
                    actual_quantity=product.current_stock,  # 기본값=시스템재고
                    created_by=request.user,
                ))
            StockCountItem.objects.bulk_create(items)

        messages.success(request, f'재고실사 {sc.count_number} 생성 ({len(items)}개 제품)')
        return redirect('inventory:stockcount_detail', pk=sc.pk)


class StockCountDetailView(LoginRequiredMixin, DetailView):
    model = StockCount
    template_name = 'inventory/stockcount_detail.html'
    context_object_name = 'stock_count'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['items'] = self.object.items.select_related('product').order_by('product__code')
        ctx['diff_count'] = self.object.items.exclude(difference=0).count()
        return ctx


class StockCountUpdateView(ManagerRequiredMixin, View):
    """재고실사 항목 수량 업데이트 (POST)"""
    def post(self, request, pk):
        sc = get_object_or_404(StockCount, pk=pk)
        if sc.status in ('COMPLETED', 'ADJUSTED'):
            messages.error(request, '이미 완료된 실사는 수정할 수 없습니다.')
            return redirect('inventory:stockcount_detail', pk=pk)

        with transaction.atomic():
            for item in sc.items.all():
                qty_key = f'actual_{item.pk}'
                if qty_key in request.POST:
                    try:
                        actual = float(request.POST[qty_key])
                        item.actual_quantity = actual
                        item.save(update_fields=['actual_quantity', 'difference', 'updated_at'])
                    except (ValueError, TypeError):
                        pass

            sc.status = 'IN_PROGRESS'
            sc.save(update_fields=['status', 'updated_at'])

        messages.success(request, '실사 수량이 저장되었습니다.')
        return redirect('inventory:stockcount_detail', pk=pk)


class StockCountAdjustView(ManagerRequiredMixin, View):
    """재고실사 차이 조정 — 차이가 있는 항목에 대해 재고조정 StockMovement 생성"""
    def post(self, request, pk):
        sc = get_object_or_404(StockCount, pk=pk)
        if sc.status == 'ADJUSTED':
            messages.error(request, '이미 조정이 완료된 실사입니다.')
            return redirect('inventory:stockcount_detail', pk=pk)

        diff_items = sc.items.exclude(difference=0).filter(adjusted=False)
        if not diff_items.exists():
            messages.info(request, '조정할 차이가 없습니다.')
            sc.status = 'COMPLETED'
            sc.save(update_fields=['status', 'updated_at'])
            return redirect('inventory:stockcount_detail', pk=pk)

        adjusted_count = 0
        with transaction.atomic():
            for item in diff_items.select_related('product'):
                diff = item.difference
                if diff > 0:
                    mv_type = 'ADJ_PLUS'
                    qty = diff
                else:
                    mv_type = 'ADJ_MINUS'
                    qty = abs(diff)

                StockMovement.objects.create(
                    movement_type=mv_type,
                    product=item.product,
                    warehouse=sc.warehouse,
                    quantity=qty,
                    unit_price=item.product.cost_price,
                    movement_date=sc.count_date,
                    reference=f'재고실사 {sc.count_number}',
                    created_by=request.user,
                )
                item.adjusted = True
                item.save(update_fields=['adjusted', 'updated_at'])
                adjusted_count += 1

            sc.status = 'ADJUSTED'
            sc.save(update_fields=['status', 'updated_at'])

        messages.success(request, f'재고 조정 완료 ({adjusted_count}건)')
        return redirect('inventory:stockcount_detail', pk=pk)


class WarehouseStockView(LoginRequiredMixin, TemplateView):
    """창고별 재고 현황"""
    template_name = 'inventory/warehouse_stock.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .models import WarehouseStock, Warehouse

        warehouse_id = self.request.GET.get('warehouse')
        q = self.request.GET.get('q', '')

        warehouses = Warehouse.objects.filter(is_active=True)
        qs = WarehouseStock.objects.select_related(
            'warehouse', 'product', 'product__category',
        ).filter(product__is_active=True, quantity__gt=0)

        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)
        if q:
            qs = qs.filter(
                models.Q(product__name__icontains=q)
                | models.Q(product__code__icontains=q)
            )

        context['stocks'] = qs
        context['warehouses'] = warehouses
        context['selected_warehouse'] = warehouse_id
        context['q'] = q
        return context


class InventoryValuationView(LoginRequiredMixin, TemplateView):
    """재고평가 보고서 — 제품별 현재고 평가금액 (AVG/FIFO/LIFO)"""
    template_name = 'inventory/valuation.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        q = self.request.GET.get('q', '')
        valuation_filter = self.request.GET.get('valuation', '')

        products = Product.objects.filter(
            is_active=True,
        ).select_related('category').order_by('code')

        if q:
            products = products.filter(
                models.Q(name__icontains=q) | models.Q(code__icontains=q)
            )
        if valuation_filter:
            products = products.filter(valuation_method=valuation_filter)

        rows = []
        total_valuation = Decimal('0')
        total_stock_value_avg = Decimal('0')

        for product in products:
            if product.valuation_method in ('FIFO', 'LIFO'):
                # FIFO/LIFO: 잔여 LOT들의 (remaining_quantity * unit_cost) 합계
                lot_valuation = (
                    StockLot.objects
                    .filter(
                        product=product,
                        remaining_quantity__gt=0,
                        is_active=True,
                    )
                    .aggregate(
                        total=Sum(F('remaining_quantity') * F('unit_cost'))
                    )['total'] or Decimal('0')
                )
                valuation_amount = lot_valuation.quantize(Decimal('1'))
            else:
                # AVG: current_stock * cost_price
                valuation_amount = (
                    product.current_stock * product.cost_price
                ).quantize(Decimal('1'))

            total_valuation += valuation_amount
            total_stock_value_avg += (
                product.current_stock * product.cost_price
            ).quantize(Decimal('1'))

            # 잔여 LOT 수 조회
            lot_count = StockLot.objects.filter(
                product=product,
                remaining_quantity__gt=0,
                is_active=True,
            ).count()

            rows.append({
                'product': product,
                'valuation_method_display': product.get_valuation_method_display(),
                'valuation_amount': valuation_amount,
                'lot_count': lot_count,
            })

        context['rows'] = rows
        context['total_valuation'] = total_valuation
        context['total_stock_value_avg'] = total_stock_value_avg
        context['product_count'] = len(rows)
        context['q'] = q
        context['valuation_filter'] = valuation_filter
        context['valuation_choices'] = Product.ValuationMethod.choices
        return context
