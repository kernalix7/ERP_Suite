from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView, View

from apps.core.excel import export_to_excel
from apps.core.import_views import BaseImportView
from apps.inventory.models import Product
from apps.core.mixins import ManagerRequiredMixin
from .models import BOM, BOMItem, ProductionPlan, WorkOrder, ProductionRecord, QualityInspection, StandardCost
from .forms import BOMForm, BOMItemFormSet, ProductionPlanForm, WorkOrderForm, ProductionRecordForm, StandardCostForm


def _product_units_json():
    return {str(p.pk): p.unit or '' for p in Product.objects.filter(is_active=True)}


def _material_prices_json():
    return {
        str(p.pk): int(p.cost_price or 0)
        for p in Product.objects.filter(
            is_active=True, product_type__in=['RAW', 'SEMI'],
        )
    }
from .resources import BOMItemResource


class BOMListView(LoginRequiredMixin, ListView):
    model = BOM
    template_name = 'production/bom_list.html'
    context_object_name = 'boms'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True).select_related('product')


class BOMCreateView(ManagerRequiredMixin, CreateView):
    model = BOM
    form_class = BOMForm
    template_name = 'production/bom_form.html'
    success_url = reverse_lazy('production:bom_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = BOMItemFormSet(self.request.POST)
        else:
            ctx['formset'] = BOMItemFormSet()
        ctx['product_units_json'] = _product_units_json()
        ctx['material_prices_json'] = _material_prices_json()
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


class BOMDetailView(LoginRequiredMixin, DetailView):
    model = BOM
    template_name = 'production/bom_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related('product')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['items'] = self.object.items.select_related(
            'material',
        ).all()
        return ctx


class BOMUpdateView(ManagerRequiredMixin, UpdateView):
    model = BOM
    form_class = BOMForm
    template_name = 'production/bom_form.html'
    success_url = reverse_lazy('production:bom_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = BOMItemFormSet(self.request.POST, instance=self.object)
        else:
            ctx['formset'] = BOMItemFormSet(instance=self.object)
        ctx['product_units_json'] = _product_units_json()
        ctx['material_prices_json'] = _material_prices_json()
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        formset = ctx['formset']
        if formset.is_valid():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
            return super().form_valid(form)
        return self.form_invalid(form)


class ProductionPlanListView(LoginRequiredMixin, ListView):
    model = ProductionPlan
    template_name = 'production/plan_list.html'
    context_object_name = 'plans'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related(
            'product', 'bom',
        )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs


def _bom_unit_costs_json():
    """BOM pk → 개당 자재원가 dict"""
    result = {}
    for bom in BOM.objects.filter(is_active=True).prefetch_related('items__material'):
        result[str(bom.pk)] = int(bom.total_material_cost)
    return result


class ProductionPlanCreateView(ManagerRequiredMixin, CreateView):
    model = ProductionPlan
    form_class = ProductionPlanForm
    template_name = 'production/plan_form.html'
    success_url = reverse_lazy('production:plan_list')

    def get_initial(self):
        initial = super().get_initial()
        from apps.core.utils import generate_document_number
        initial['plan_number'] = generate_document_number(ProductionPlan, 'plan_number', 'PP')
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['bom_costs_json'] = _bom_unit_costs_json()
        return ctx

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        # BOM 기준 예상원가 자동 계산
        bom = form.cleaned_data.get('bom')
        qty = form.cleaned_data.get('planned_quantity') or 0
        if bom and qty:
            form.instance.estimated_cost = bom.total_material_cost * qty
        return super().form_valid(form)


class ProductionPlanDetailView(LoginRequiredMixin, DetailView):
    model = ProductionPlan
    template_name = 'production/plan_detail.html'
    slug_field = 'plan_number'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'product', 'bom',
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['work_orders'] = (
            self.object.work_orders
            .select_related('assigned_to')
            .all()
        )
        # 원가 비교 데이터
        plan = self.object
        records = ProductionRecord.objects.filter(
            work_order__production_plan=plan,
        )
        total_good = sum(r.good_quantity for r in records)
        total_defect = sum(r.defect_quantity for r in records)
        total_produced = total_good + total_defect
        # 실제 원가: 각 실적의 unit_cost × (양품+불량) 합계
        actual_cost_sum = sum(
            r.unit_cost * r.total_quantity for r in records
        )
        ctx['total_good'] = total_good
        ctx['total_defect'] = total_defect
        ctx['defect_rate'] = (
            round(total_defect / total_produced * 100, 1)
            if total_produced > 0 else 0
        )
        ctx['estimated_cost'] = int(plan.estimated_cost)
        ctx['actual_cost'] = int(actual_cost_sum)
        cost_diff = int(actual_cost_sum) - int(plan.estimated_cost)
        ctx['cost_diff'] = cost_diff
        ctx['cost_diff_rate'] = (
            round(cost_diff / int(plan.estimated_cost) * 100, 1)
            if plan.estimated_cost > 0 else 0
        )
        # 원자재 부족 체크
        remaining_qty = plan.planned_quantity - total_good
        if remaining_qty > 0 and plan.bom:
            ctx['material_shortages'] = (
                plan.bom.check_material_availability(remaining_qty)
            )
        return ctx


class ProductionPlanUpdateView(ManagerRequiredMixin, UpdateView):
    model = ProductionPlan
    form_class = ProductionPlanForm
    template_name = 'production/plan_form.html'
    success_url = reverse_lazy('production:plan_list')
    slug_field = 'plan_number'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['bom_costs_json'] = _bom_unit_costs_json()
        return ctx


class WorkOrderListView(LoginRequiredMixin, ListView):
    model = WorkOrder
    template_name = 'production/workorder_list.html'
    context_object_name = 'work_orders'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related(
            'production_plan', 'production_plan__product',
            'assigned_to',
        )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs


class WorkOrderCreateView(ManagerRequiredMixin, CreateView):
    model = WorkOrder
    form_class = WorkOrderForm
    template_name = 'production/workorder_form.html'
    success_url = reverse_lazy('production:workorder_list')

    def get_initial(self):
        initial = super().get_initial()
        from apps.core.utils import generate_document_number
        initial['order_number'] = generate_document_number(WorkOrder, 'order_number', 'WO')
        return initial

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class WorkOrderDetailView(LoginRequiredMixin, DetailView):
    model = WorkOrder
    template_name = 'production/workorder_detail.html'
    slug_field = 'order_number'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'production_plan', 'production_plan__product',
            'assigned_to',
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['records'] = (
            self.object.records
            .select_related('worker')
            .all()
        )
        # 원자재 부족 체크
        wo = self.object
        plan = wo.production_plan
        remaining = wo.quantity - sum(
            r.good_quantity for r in ctx['records']
        )
        if remaining > 0 and plan.bom:
            ctx['material_shortages'] = (
                plan.bom.check_material_availability(remaining)
            )
        return ctx


class WorkOrderUpdateView(ManagerRequiredMixin, UpdateView):
    model = WorkOrder
    form_class = WorkOrderForm
    template_name = 'production/workorder_form.html'
    success_url = reverse_lazy('production:workorder_list')
    slug_field = 'order_number'
    slug_url_kwarg = 'slug'


class ProductionRecordListView(LoginRequiredMixin, ListView):
    model = ProductionRecord
    template_name = 'production/record_list.html'
    context_object_name = 'records'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True).select_related(
            'work_order',
            'work_order__production_plan',
            'work_order__production_plan__product',
            'worker',
        )


class ProductionRecordCreateView(ManagerRequiredMixin, CreateView):
    model = ProductionRecord
    form_class = ProductionRecordForm
    template_name = 'production/record_form.html'
    success_url = reverse_lazy('production:record_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class ProductionRecordUpdateView(ManagerRequiredMixin, UpdateView):
    model = ProductionRecord
    form_class = ProductionRecordForm
    template_name = 'production/record_form.html'
    success_url = reverse_lazy('production:record_list')


# ── 일괄 가져오기 ──

class BOMItemImportView(BaseImportView):
    resource_class = BOMItemResource
    page_title = 'BOM 자재 일괄 가져오기'
    cancel_url = reverse_lazy('production:bom_list')
    sample_url = reverse_lazy('production:bom_import_sample')
    export_filename = 'BOM_데이터'
    field_hints = [
        'bom__product__code: 완제품 코드 (기본 BOM에 자재를 추가합니다)',
        'material__code: 원자재 코드',
        'quantity: 소요량, loss_rate: 손실률(%)',
        '동일한 (완제품코드, 원자재코드) 조합이 있으면 수량이 수정됩니다.',
    ]
    success_message = 'BOM 자재 {count}건이 성공적으로 가져오기 되었습니다.'


class BOMItemImportSampleView(LoginRequiredMixin, View):
    def get(self, request):
        headers = [
            ('bom__product__code', 20), ('material__code', 20),
            ('quantity', 10), ('loss_rate', 10), ('notes', 30),
        ]
        rows = [
            ['FIN-001', 'MAT-001', 1, 0, ''],
            ['FIN-001', 'MAT-002', 2, 5, '5% 손실률 반영'],
        ]
        return export_to_excel(
            'BOM자재_가져오기_양식', headers, rows,
            filename='BOM자재_가져오기_양식.xlsx',
            required_columns=[0, 1, 2],  # bom__product__code, material__code, quantity
        )


# ── 품질검수 ──

class QualityInspectionListView(LoginRequiredMixin, ListView):
    model = QualityInspection
    template_name = 'production/qc_list.html'
    context_object_name = 'inspections'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).select_related(
            'product', 'inspector', 'production_record',
            'production_record__work_order',
        )
        result = self.request.GET.get('result')
        if result:
            qs = qs.filter(result=result)
        return qs


class QualityInspectionCreateView(ManagerRequiredMixin, CreateView):
    model = QualityInspection
    template_name = 'production/qc_form.html'
    fields = [
        'inspection_type', 'production_record', 'product',
        'inspected_quantity', 'pass_quantity', 'fail_quantity',
        'inspection_date', 'result',
        'defect_description', 'corrective_action', 'notes',
    ]
    success_url = reverse_lazy('production:qc_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            field.widget.attrs.setdefault(
                'class', 'form-input w-full rounded-lg border-gray-300',
            )
        return form

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.inspector = self.request.user
        return super().form_valid(form)


class QualityInspectionDetailView(LoginRequiredMixin, DetailView):
    model = QualityInspection
    template_name = 'production/qc_detail.html'
    context_object_name = 'inspection'
    slug_field = 'inspection_number'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'product', 'inspector', 'production_record',
            'production_record__work_order',
        )


class QualityInspectionUpdateView(ManagerRequiredMixin, UpdateView):
    model = QualityInspection
    template_name = 'production/qc_form.html'
    slug_field = 'inspection_number'
    slug_url_kwarg = 'slug'
    fields = [
        'inspected_quantity', 'pass_quantity', 'fail_quantity',
        'result', 'defect_description', 'corrective_action',
        'notes',
    ]

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            field.widget.attrs.setdefault(
                'class', 'form-input w-full rounded-lg border-gray-300',
            )
        return form

    def get_success_url(self):
        return reverse_lazy(
            'production:qc_detail',
            kwargs={'slug': self.object.inspection_number},
        )


# ── MRP (자재 소요량 계획) ──

class MRPView(ManagerRequiredMixin, TemplateView):
    """MRP 일괄 전개 — 복수 생산계획의 통합 자재소요량 산출 및 발주 제안"""
    template_name = 'production/mrp.html'

    def _get_target_plans(self):
        """진행중 + 확정 + 작성중 상태의 활성 생산계획 조회"""
        return (
            ProductionPlan.objects.filter(
                is_active=True,
                status__in=[
                    ProductionPlan.Status.IN_PROGRESS,
                    ProductionPlan.Status.CONFIRMED,
                    ProductionPlan.Status.DRAFT,
                ],
            )
            .select_related('product', 'bom')
            .prefetch_related('bom__items__material')
        )

    def _calculate_mrp(self, selected_plan_ids=None):
        """선택된 생산계획들의 자재소요량 통합 산출

        Returns:
            list of dict: 자재별 소요/재고/부족 정보
        """
        plans = self._get_target_plans()
        if selected_plan_ids:
            plans = plans.filter(pk__in=selected_plan_ids)

        # 자재별 총 소요량 집계
        material_requirements = defaultdict(Decimal)
        # 자재별 관련 생산계획 추적
        material_plans = defaultdict(list)

        for plan in plans:
            if not plan.bom:
                continue
            remaining_qty = plan.planned_quantity - plan.produced_quantity
            if remaining_qty <= 0:
                continue

            for item in plan.bom.items.select_related('material').filter(is_active=True):
                # 소요량 = BOMItem.quantity * (1 + loss_rate/100) * 남은생산량
                required = (
                    item.quantity
                    * (1 + item.loss_rate / 100)
                    * Decimal(str(remaining_qty))
                )
                material_requirements[item.material_id] += required
                material_plans[item.material_id].append(plan.plan_number)

        if not material_requirements:
            return []

        # 자재 정보 일괄 조회
        materials = {
            p.pk: p
            for p in Product.objects.filter(
                pk__in=material_requirements.keys(),
                is_active=True,
            )
        }

        result = []
        for material_id, total_required in material_requirements.items():
            material = materials.get(material_id)
            if not material:
                continue

            available = material.available_stock
            shortage = total_required - available
            if shortage < 0:
                shortage = Decimal('0')

            result.append({
                'material': material,
                'total_required': total_required,
                'current_stock': material.current_stock,
                'available_stock': available,
                'shortage': shortage,
                'lead_time_days': material.lead_time_days,
                'cost_price': material.cost_price,
                'plans': ', '.join(sorted(set(material_plans[material_id]))),
            })

        # 부족 수량 내림차순, 그 다음 자재코드 오름차순
        result.sort(key=lambda x: (-x['shortage'], x['material'].code))
        return result

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        plans = list(self._get_target_plans())
        # 각 계획에 잔여수량 속성 부착
        for plan in plans:
            plan.remaining_quantity = max(
                plan.planned_quantity - plan.produced_quantity, 0,
            )
        ctx['plans'] = plans

        # GET 파라미터에서 선택된 계획 ID 추출
        selected_ids = self.request.GET.getlist('plan')
        selected_ids = [int(pid) for pid in selected_ids if pid.isdigit()]
        ctx['selected_plan_ids'] = selected_ids

        # 선택된 계획이 있으면 해당 계획만, 없으면 전체 MRP 전개
        mrp_items = self._calculate_mrp(selected_ids if selected_ids else None)
        ctx['mrp_items'] = mrp_items
        ctx['shortage_items'] = [item for item in mrp_items if item['shortage'] > 0]
        ctx['total_shortage_count'] = len(ctx['shortage_items'])
        ctx['total_material_count'] = len(mrp_items)

        return ctx

    def post(self, request, *args, **kwargs):
        """부족 자재에 대해 발주서 자동 생성"""
        from apps.purchase.models import PurchaseOrder, PurchaseOrderItem
        from apps.sales.models import Partner

        selected_material_ids = request.POST.getlist('material_ids')
        selected_material_ids = [int(mid) for mid in selected_material_ids if mid.isdigit()]

        if not selected_material_ids:
            messages.warning(request, '발주할 자재를 선택하세요.')
            return redirect('production:mrp')

        # 선택된 계획 ID (hidden field로 전달)
        selected_plan_ids = request.POST.getlist('plan_ids')
        selected_plan_ids = [int(pid) for pid in selected_plan_ids if pid.isdigit()]

        # MRP 재계산으로 부족 수량 확인
        mrp_items = self._calculate_mrp(selected_plan_ids if selected_plan_ids else None)
        shortage_map = {
            item['material'].pk: item
            for item in mrp_items
            if item['shortage'] > 0 and item['material'].pk in selected_material_ids
        }

        if not shortage_map:
            messages.info(request, '선택한 자재 중 부족한 자재가 없습니다.')
            return redirect('production:mrp')

        # 공급처별로 자재를 그룹핑하여 발주서 생성
        supplier_materials = defaultdict(list)

        for material_id, item_data in shortage_map.items():
            material = item_data['material']
            # 최근 구매 이력에서 공급처 찾기
            supplier = self._find_supplier(material)
            if supplier:
                supplier_materials[supplier.pk].append((supplier, item_data))
            else:
                # 공급처가 없는 자재는 기본 공급처로
                supplier_materials['_no_supplier'].append((None, item_data))

        created_pos = []
        with transaction.atomic():
            for supplier_key, items in supplier_materials.items():
                if supplier_key == '_no_supplier':
                    # 기본 공급처 찾기 (SUPPLIER 또는 BOTH 유형 중 첫 번째)
                    default_supplier = (
                        Partner.objects.filter(
                            is_active=True,
                            partner_type__in=['SUPPLIER', 'BOTH'],
                        ).first()
                    )
                    if not default_supplier:
                        messages.error(
                            request,
                            '등록된 공급처가 없습니다. 먼저 공급처를 등록하세요.',
                        )
                        return redirect('production:mrp')
                    supplier = default_supplier
                else:
                    supplier = items[0][0]

                # 발주서 생성
                po = PurchaseOrder(
                    partner=supplier,
                    order_date=date.today(),
                    status=PurchaseOrder.Status.DRAFT,
                    created_by=request.user,
                    notes=f'MRP 자동 발주 제안 ({date.today().strftime("%Y-%m-%d")})',
                )
                # 리드타임 기준으로 입고예정일 설정
                max_lead_time = max(
                    (item_data['lead_time_days'] for _, item_data in items),
                    default=0,
                )
                if max_lead_time > 0:
                    po.expected_date = date.today() + timedelta(days=max_lead_time)
                po.save()

                # 발주 항목 생성
                for _, item_data in items:
                    material = item_data['material']
                    shortage_qty = int(
                        item_data['shortage'].quantize(Decimal('1'))
                        if item_data['shortage'] != int(item_data['shortage'])
                        else item_data['shortage']
                    )
                    if shortage_qty <= 0:
                        continue

                    PurchaseOrderItem.objects.create(
                        purchase_order=po,
                        product=material,
                        quantity=shortage_qty,
                        unit_price=material.cost_price,
                        amount=shortage_qty * material.cost_price,
                        created_by=request.user,
                    )

                # 합계 갱신
                po.update_total()
                created_pos.append(po)

        if created_pos:
            po_numbers = ', '.join(po.po_number for po in created_pos)
            messages.success(
                request,
                f'발주서 {len(created_pos)}건이 생성되었습니다: {po_numbers}',
            )
        else:
            messages.info(request, '생성할 발주 항목이 없습니다.')

        return redirect('production:mrp')

    @staticmethod
    def _find_supplier(material):
        """해당 자재의 최근 구매 이력에서 공급처를 찾음"""
        from apps.purchase.models import PurchaseOrderItem
        recent_po_item = (
            PurchaseOrderItem.objects.filter(
                product=material,
                is_active=True,
                purchase_order__is_active=True,
            )
            .select_related('purchase_order__partner')
            .order_by('-purchase_order__order_date', '-pk')
            .first()
        )
        if recent_po_item:
            return recent_po_item.purchase_order.partner
        return None


# ── 표준원가 ──

def _bom_material_costs_json():
    """제품 pk → 기본BOM 자재원가 dict (표준원가 폼에서 사용)"""
    result = {}
    for bom in BOM.objects.filter(
        is_active=True, is_default=True,
    ).select_related('product').prefetch_related('items__material'):
        result[str(bom.product_id)] = int(bom.total_material_cost)
    return result


class StandardCostListView(LoginRequiredMixin, ListView):
    model = StandardCost
    template_name = 'production/stdcost_list.html'
    context_object_name = 'standard_costs'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).select_related('product')
        product_id = self.request.GET.get('product')
        if product_id:
            qs = qs.filter(product_id=product_id)
        current_only = self.request.GET.get('current')
        if current_only == '1':
            qs = qs.filter(is_current=True)
        return qs


class StandardCostCreateView(ManagerRequiredMixin, CreateView):
    model = StandardCost
    form_class = StandardCostForm
    template_name = 'production/stdcost_form.html'
    success_url = reverse_lazy('production:stdcost_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['bom_material_costs_json'] = _bom_material_costs_json()
        return ctx

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        # BOM 기반 자재원가 자동 계산
        obj = form.save(commit=False)
        obj.calculate_material_cost()
        obj.save()
        messages.success(self.request, f'표준원가 "{obj}" 이(가) 등록되었습니다.')
        return redirect(self.get_success_url())


class StandardCostDetailView(LoginRequiredMixin, DetailView):
    model = StandardCost
    template_name = 'production/stdcost_detail.html'
    context_object_name = 'stdcost'

    def get_queryset(self):
        return super().get_queryset().select_related('product')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = self.object
        total = obj.total_standard_cost
        if total > 0:
            ctx['material_pct'] = round(obj.material_cost / total * 100, 1)
            ctx['labor_pct'] = round(obj.labor_cost / total * 100, 1)
            ctx['overhead_pct'] = round(obj.overhead_cost / total * 100, 1)
        else:
            ctx['material_pct'] = 0
            ctx['labor_pct'] = 0
            ctx['overhead_pct'] = 0
        # BOM 항목 표시
        bom = BOM.objects.filter(
            product=obj.product, is_default=True, is_active=True,
        ).prefetch_related('items__material').first()
        ctx['bom'] = bom
        ctx['bom_items'] = bom.items.select_related('material').all() if bom else []
        return ctx


class CostVarianceView(ManagerRequiredMixin, TemplateView):
    """원가차이 분석 — 표준원가 vs 실제원가 비교"""
    template_name = 'production/cost_variance.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # 기간 필터
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        product_id = self.request.GET.get('product')

        records_qs = ProductionRecord.objects.filter(
            is_active=True,
        ).select_related(
            'work_order__production_plan__product',
            'work_order__production_plan__bom',
        )

        if date_from:
            records_qs = records_qs.filter(record_date__gte=date_from)
        if date_to:
            records_qs = records_qs.filter(record_date__lte=date_to)
        if product_id:
            records_qs = records_qs.filter(
                work_order__production_plan__product_id=product_id,
            )

        # 제품별 집계
        product_variances = defaultdict(lambda: {
            'product': None,
            'std_material': Decimal('0'),
            'std_labor': Decimal('0'),
            'std_overhead': Decimal('0'),
            'std_total': Decimal('0'),
            'act_material': Decimal('0'),
            'act_labor': Decimal('0'),
            'act_overhead': Decimal('0'),
            'act_total': Decimal('0'),
            'total_quantity': 0,
        })

        for record in records_qs:
            plan = record.work_order.production_plan
            product = plan.product
            qty = record.good_quantity
            data = product_variances[product.pk]
            data['product'] = product

            # 실제원가 집계
            data['act_material'] += record.actual_material_cost
            data['act_labor'] += record.actual_labor_cost
            data['act_overhead'] += record.actual_overhead_cost
            data['act_total'] += (
                record.actual_material_cost
                + record.actual_labor_cost
                + record.actual_overhead_cost
            )
            data['total_quantity'] += qty

            # 표준원가 조회 (현행 표준원가 기준)
            if data['std_material'] == 0 and data['std_labor'] == 0:
                std = StandardCost.objects.filter(
                    product=product, is_current=True, is_active=True,
                ).first()
                if std:
                    data['_std_obj'] = std

        # 표준원가 × 수량 계산
        variance_list = []
        for pk, data in product_variances.items():
            std = data.get('_std_obj')
            qty = data['total_quantity']
            if std and qty > 0:
                data['std_material'] = std.material_cost * qty
                data['std_labor'] = std.labor_cost * qty
                data['std_overhead'] = std.overhead_cost * qty
                data['std_total'] = std.total_standard_cost * qty

            # 차이 계산
            data['var_material'] = int(data['act_material'] - data['std_material'])
            data['var_labor'] = int(data['act_labor'] - data['std_labor'])
            data['var_overhead'] = int(data['act_overhead'] - data['std_overhead'])
            data['var_total'] = int(data['act_total'] - data['std_total'])

            # 차이율
            data['var_material_rate'] = (
                round(data['var_material'] / int(data['std_material']) * 100, 1)
                if data['std_material'] else 0
            )
            data['var_labor_rate'] = (
                round(data['var_labor'] / int(data['std_labor']) * 100, 1)
                if data['std_labor'] else 0
            )
            data['var_overhead_rate'] = (
                round(data['var_overhead'] / int(data['std_overhead']) * 100, 1)
                if data['std_overhead'] else 0
            )
            data['var_total_rate'] = (
                round(data['var_total'] / int(data['std_total']) * 100, 1)
                if data['std_total'] else 0
            )

            variance_list.append(data)

        # 차이 절대값 기준 내림차순 정렬
        variance_list.sort(key=lambda x: abs(x['var_total']), reverse=True)

        ctx['variance_list'] = variance_list
        ctx['date_from'] = date_from or ''
        ctx['date_to'] = date_to or ''
        ctx['selected_product'] = product_id or ''

        # 필터용 제품 목록 (완제품만)
        ctx['products'] = Product.objects.filter(
            is_active=True, product_type='FINISHED',
        ).order_by('name')

        # 합계
        ctx['grand_std_total'] = sum(
            int(v['std_total']) for v in variance_list
        )
        ctx['grand_act_total'] = sum(
            int(v['act_total']) for v in variance_list
        )
        ctx['grand_var_total'] = sum(
            v['var_total'] for v in variance_list
        )

        return ctx
