import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Count, Avg, Min, Max, F, Q
from django.db.models.functions import TruncMonth, TruncWeek, TruncDay
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView

from apps.core.mixins import ManagerRequiredMixin
from .models import Report, ReportSchedule, Dashboard, DashboardPanel, SavedFilter
from .forms import (
    ReportForm, ReportScheduleForm, DashboardForm,
    DashboardPanelForm, SavedFilterForm,
)


# ── Data source schema ──────────────────────────────────────

DATA_SOURCE_SCHEMA = {
    'ORDER': {
        'model': 'apps.sales.models.Order',
        'fields': [
            {'name': 'order_date', 'label': '주문일', 'type': 'date'},
            {'name': 'status', 'label': '상태', 'type': 'choice'},
            {'name': 'total_amount', 'label': '총액', 'type': 'decimal'},
            {'name': 'grand_total', 'label': '합계', 'type': 'decimal'},
            {'name': 'tax_total', 'label': '세액', 'type': 'decimal'},
            {'name': 'partner__name', 'label': '거래처', 'type': 'string'},
            {'name': 'order_type', 'label': '주문유형', 'type': 'choice'},
        ],
        'aggregations': ['count', 'sum', 'avg', 'min', 'max'],
        'group_by': ['order_date', 'status', 'partner__name', 'order_type'],
    },
    'PRODUCT': {
        'model': 'apps.inventory.models.Product',
        'fields': [
            {'name': 'name', 'label': '제품명', 'type': 'string'},
            {'name': 'product_type', 'label': '제품유형', 'type': 'choice'},
            {'name': 'current_stock', 'label': '현재고', 'type': 'integer'},
            {'name': 'safety_stock', 'label': '안전재고', 'type': 'integer'},
            {'name': 'cost_price', 'label': '원가', 'type': 'decimal'},
            {'name': 'sell_price', 'label': '판매가', 'type': 'decimal'},
            {'name': 'category__name', 'label': '카테고리', 'type': 'string'},
        ],
        'aggregations': ['count', 'sum', 'avg', 'min', 'max'],
        'group_by': ['product_type', 'category__name'],
    },
    'PARTNER': {
        'model': 'apps.sales.models.Partner',
        'fields': [
            {'name': 'name', 'label': '거래처명', 'type': 'string'},
            {'name': 'partner_type', 'label': '거래처유형', 'type': 'choice'},
            {'name': 'credit_limit', 'label': '신용한도', 'type': 'decimal'},
        ],
        'aggregations': ['count', 'sum', 'avg'],
        'group_by': ['partner_type'],
    },
    'VOUCHER': {
        'model': 'apps.accounting.models.Voucher',
        'fields': [
            {'name': 'voucher_date', 'label': '전표일', 'type': 'date'},
            {'name': 'voucher_type', 'label': '전표유형', 'type': 'choice'},
            {'name': 'total_amount', 'label': '합계금액', 'type': 'decimal'},
            {'name': 'description', 'label': '적요', 'type': 'string'},
        ],
        'aggregations': ['count', 'sum', 'avg'],
        'group_by': ['voucher_date', 'voucher_type'],
    },
    'INVENTORY': {
        'model': 'apps.inventory.models.StockMovement',
        'fields': [
            {'name': 'movement_date', 'label': '이동일', 'type': 'date'},
            {'name': 'movement_type', 'label': '이동유형', 'type': 'choice'},
            {'name': 'quantity', 'label': '수량', 'type': 'integer'},
            {'name': 'product__name', 'label': '제품명', 'type': 'string'},
            {'name': 'warehouse__name', 'label': '창고', 'type': 'string'},
        ],
        'aggregations': ['count', 'sum', 'avg'],
        'group_by': ['movement_date', 'movement_type', 'product__name', 'warehouse__name'],
    },
    'PRODUCTION': {
        'model': 'apps.production.models.ProductionRecord',
        'fields': [
            {'name': 'record_date', 'label': '실적일', 'type': 'date'},
            {'name': 'good_quantity', 'label': '양품수량', 'type': 'integer'},
            {'name': 'defective_quantity', 'label': '불량수량', 'type': 'integer'},
            {'name': 'product__name', 'label': '제품명', 'type': 'string'},
        ],
        'aggregations': ['count', 'sum', 'avg'],
        'group_by': ['record_date', 'product__name'],
    },
    'HR': {
        'model': 'apps.hr.models.Employee',
        'fields': [
            {'name': 'name', 'label': '성명', 'type': 'string'},
            {'name': 'department__name', 'label': '부서', 'type': 'string'},
            {'name': 'position__name', 'label': '직급', 'type': 'string'},
            {'name': 'hire_date', 'label': '입사일', 'type': 'date'},
        ],
        'aggregations': ['count'],
        'group_by': ['department__name', 'position__name'],
    },
}

AGGREGATION_MAP = {
    'count': Count,
    'sum': Sum,
    'avg': Avg,
    'min': Min,
    'max': Max,
}

TRUNC_MAP = {
    'day': TruncDay,
    'week': TruncWeek,
    'month': TruncMonth,
}

# ORM 인젝션 방지: 데이터소스별 허용 필터 키 화이트리스트
ALLOWED_FILTER_KEYS = {}
_FILTER_SUFFIXES = ('', '__gte', '__lte', '__gt', '__lt', '__exact', '__icontains', '__in')
for _src, _schema in DATA_SOURCE_SCHEMA.items():
    _keys = set()
    for _f in _schema['fields']:
        for _suffix in _FILTER_SUFFIXES:
            _keys.add(_f['name'] + _suffix)
    # is_active 필터도 허용
    _keys.add('is_active')
    ALLOWED_FILTER_KEYS[_src] = frozenset(_keys)


def _sanitize_filters(filters, data_source):
    """허용된 필드만 남기고 나머지는 제거 (ORM 인젝션 방지)"""
    allowed = ALLOWED_FILTER_KEYS.get(data_source, frozenset())
    return {k: v for k, v in filters.items() if k in allowed}


def _get_model_class(data_source):
    """데이터소스 문자열에서 Django 모델 클래스 반환"""
    schema = DATA_SOURCE_SCHEMA.get(data_source)
    if not schema:
        return None
    module_path, class_name = schema['model'].rsplit('.', 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _execute_report_query(report):
    """리포트 query_config 기반으로 쿼리 실행 후 결과 반환"""
    model_class = _get_model_class(report.data_source)
    if not model_class:
        return {'labels': [], 'datasets': []}

    qc = report.query_config or {}
    qs = model_class.objects.filter(is_active=True)

    # 필터 적용 (화이트리스트 검증)
    filters = qc.get('filters', {})
    if filters:
        filters = _sanitize_filters(filters, report.data_source)
        if filters:
            qs = qs.filter(**filters)

    # 그룹바이 (화이트리스트 검증)
    schema = DATA_SOURCE_SCHEMA.get(report.data_source, {})
    allowed_group_by = set(schema.get('group_by', []))
    allowed_field_names = {f['name'] for f in schema.get('fields', [])} | {'id'}
    allowed_agg_funcs = set(schema.get('aggregations', []))

    group_by = [gb for gb in qc.get('groupby', []) if gb in allowed_group_by]
    agg_config = [
        agg for agg in qc.get('aggregations', [])
        if agg.get('field', 'id') in allowed_field_names
        and agg.get('func', 'count') in allowed_agg_funcs
    ]
    # sort: 필드명, 그룹바이 필드, _trunc 접미사 허용
    allowed_sort = allowed_field_names | allowed_group_by
    allowed_sort |= {f'{gb}_trunc' for gb in allowed_group_by}
    sort = [
        s for s in qc.get('sort', [])
        if s.lstrip('-') in allowed_sort
    ]

    if group_by:
        # 날짜 필드 Trunc 적용
        annotations = {}
        actual_group = []
        for gb in group_by:
            trunc_func = qc.get('trunc', {}).get(gb)
            if trunc_func and trunc_func in TRUNC_MAP:
                alias = f'{gb}_trunc'
                annotations[alias] = TRUNC_MAP[trunc_func](gb)
                actual_group.append(alias)
            else:
                actual_group.append(gb)

        if annotations:
            qs = qs.annotate(**annotations)
        qs = qs.values(*actual_group)

        # 집계
        agg_kwargs = {}
        for agg in agg_config:
            field = agg.get('field', 'id')
            func_name = agg.get('func', 'count')
            alias = agg.get('alias', f'{func_name}_{field}')
            func_class = AGGREGATION_MAP.get(func_name, Count)
            agg_kwargs[alias] = func_class(field)

        if agg_kwargs:
            qs = qs.annotate(**agg_kwargs)

        if sort:
            qs = qs.order_by(*sort)

        results = list(qs[:500])

        # 차트 데이터 변환
        labels = []
        datasets = []
        if results:
            label_key = actual_group[0] if actual_group else None
            value_keys = list(agg_kwargs.keys()) if agg_kwargs else []

            for row in results:
                label_val = row.get(label_key, '')
                if hasattr(label_val, 'strftime'):
                    label_val = label_val.strftime('%Y-%m-%d')
                labels.append(str(label_val))

            for vk in value_keys:
                data_points = []
                for row in results:
                    val = row.get(vk, 0)
                    if isinstance(val, Decimal):
                        val = float(val)
                    data_points.append(val or 0)
                datasets.append({'label': vk, 'data': data_points})

        return {'labels': labels, 'datasets': datasets}
    else:
        # 집계 없이 raw 리스트
        field_names = [f['name'] for f in schema.get('fields', [])]
        rows = list(qs.values(*field_names)[:500])
        for row in rows:
            for k, v in row.items():
                if isinstance(v, Decimal):
                    row[k] = float(v)
                elif hasattr(v, 'strftime'):
                    row[k] = v.strftime('%Y-%m-%d')
        return {'columns': field_names, 'rows': rows}


# ── Report views ─────────────────────────────────────────────

class ReportListView(LoginRequiredMixin, ListView):
    model = Report
    template_name = 'bi/report_list.html'
    context_object_name = 'reports'
    paginate_by = 20

    def get_queryset(self):
        qs = Report.objects.filter(
            Q(is_active=True),
            Q(owner=self.request.user) | Q(is_public=True),
        ).select_related('owner')
        search = self.request.GET.get('q')
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
        report_type = self.request.GET.get('type')
        if report_type:
            qs = qs.filter(report_type=report_type)
        data_source = self.request.GET.get('source')
        if data_source:
            qs = qs.filter(data_source=data_source)
        return qs


class ReportCreateView(ManagerRequiredMixin, CreateView):
    model = Report
    form_class = ReportForm
    template_name = 'bi/report_form.html'

    def form_valid(self, form):
        form.instance.owner = self.request.user
        form.instance.created_by = self.request.user
        messages.success(self.request, '리포트가 생성되었습니다.')
        return super().form_valid(form)

    def get_success_url(self):
        return f'/bi/reports/{self.object.pk}/builder/'


class ReportBuilderView(LoginRequiredMixin, DetailView):
    model = Report
    template_name = 'bi/report_builder.html'
    context_object_name = 'report'

    def get_queryset(self):
        return Report.objects.filter(
            is_active=True,
        ).filter(Q(owner=self.request.user) | Q(is_public=True))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['data_source_schema'] = json.dumps(
            DATA_SOURCE_SCHEMA.get(self.object.data_source, {}),
        )
        context['all_schemas'] = json.dumps(DATA_SOURCE_SCHEMA)
        return context


class ReportPreviewView(LoginRequiredMixin, View):
    """리포트 미리보기 (AJAX)"""

    def post(self, request, pk):
        report = get_object_or_404(Report, pk=pk, is_active=True)
        # 임시 query_config/chart_config 적용
        body = json.loads(request.body) if request.body else {}
        if 'query_config' in body:
            report.query_config = body['query_config']
        if 'chart_config' in body:
            report.chart_config = body['chart_config']
        result = _execute_report_query(report)
        return JsonResponse({'success': True, 'data': result, 'chart_config': report.chart_config})


class ReportExecuteView(LoginRequiredMixin, View):
    """리포트 실행 (저장된 설정 기준)"""

    def get(self, request, pk):
        report = get_object_or_404(Report, pk=pk, is_active=True)
        result = _execute_report_query(report)
        return JsonResponse({'success': True, 'data': result, 'chart_config': report.chart_config})


class ReportUpdateView(ManagerRequiredMixin, UpdateView):
    model = Report
    form_class = ReportForm
    template_name = 'bi/report_form.html'

    def get_queryset(self):
        return Report.objects.filter(is_active=True, owner=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, '리포트가 수정되었습니다.')
        return super().form_valid(form)

    def get_success_url(self):
        return f'/bi/reports/{self.object.pk}/builder/'


class ReportDeleteView(ManagerRequiredMixin, View):
    def post(self, request, pk):
        report = get_object_or_404(Report, pk=pk, is_active=True, owner=request.user)
        report.soft_delete()
        messages.success(request, '리포트가 삭제되었습니다.')
        return redirect('bi:report_list')


class ReportSaveConfigView(ManagerRequiredMixin, View):
    """리포트 빌더에서 query/chart config 저장 (AJAX)"""

    def post(self, request, pk):
        report = get_object_or_404(Report, pk=pk, is_active=True, owner=request.user)
        body = json.loads(request.body) if request.body else {}
        if 'query_config' in body:
            report.query_config = body['query_config']
        if 'chart_config' in body:
            report.chart_config = body['chart_config']
        if 'name' in body:
            report.name = body['name']
        report.save()
        return JsonResponse({'success': True})


# ── Dashboard views ──────────────────────────────────────────

class DashboardListView(LoginRequiredMixin, ListView):
    model = Dashboard
    template_name = 'bi/dashboard_list.html'
    context_object_name = 'dashboards'
    paginate_by = 20

    def get_queryset(self):
        return Dashboard.objects.filter(
            is_active=True, owner=self.request.user,
        ).select_related('owner')


class DashboardCreateView(ManagerRequiredMixin, CreateView):
    model = Dashboard
    form_class = DashboardForm
    template_name = 'bi/dashboard_form.html'

    def form_valid(self, form):
        form.instance.owner = self.request.user
        form.instance.created_by = self.request.user
        messages.success(self.request, '대시보드가 생성되었습니다.')
        return super().form_valid(form)

    def get_success_url(self):
        return f'/bi/dashboards/{self.object.pk}/edit/'


class DashboardEditView(LoginRequiredMixin, DetailView):
    model = Dashboard
    template_name = 'bi/dashboard_edit.html'
    context_object_name = 'dashboard'

    def get_queryset(self):
        return Dashboard.objects.filter(is_active=True, owner=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['panels'] = self.object.panels.filter(
            is_active=True,
        ).select_related('report')
        context['available_reports'] = Report.objects.filter(
            Q(is_active=True),
            Q(owner=self.request.user) | Q(is_public=True),
        )
        return context


class DashboardDeleteView(ManagerRequiredMixin, View):
    def post(self, request, pk):
        dashboard = get_object_or_404(Dashboard, pk=pk, is_active=True, owner=request.user)
        dashboard.soft_delete()
        messages.success(request, '대시보드가 삭제되었습니다.')
        return redirect('bi:dashboard_list')


class DashboardSaveLayoutView(ManagerRequiredMixin, View):
    """드래그앤드롭 레이아웃 저장 (AJAX)"""

    def post(self, request, pk):
        dashboard = get_object_or_404(Dashboard, pk=pk, is_active=True, owner=request.user)
        body = json.loads(request.body) if request.body else {}
        panels_data = body.get('panels', [])
        for pd in panels_data:
            DashboardPanel.objects.filter(
                pk=pd['id'], dashboard=dashboard,
            ).update(
                position_x=pd.get('x', 0),
                position_y=pd.get('y', 0),
                width=pd.get('w', 6),
                height=pd.get('h', 4),
            )
        return JsonResponse({'success': True})


# ── Panel CRUD ───────────────────────────────────────────────

class PanelCreateView(ManagerRequiredMixin, View):
    def post(self, request, dashboard_pk):
        dashboard = get_object_or_404(Dashboard, pk=dashboard_pk, is_active=True, owner=request.user)
        body = json.loads(request.body) if request.body else {}
        report = get_object_or_404(Report, pk=body.get('report_id'), is_active=True)
        panel = DashboardPanel.objects.create(
            dashboard=dashboard,
            report=report,
            position_x=body.get('x', 0),
            position_y=body.get('y', 0),
            width=body.get('w', 6),
            height=body.get('h', 4),
            refresh_interval_minutes=body.get('refresh', 5),
            created_by=request.user,
        )
        return JsonResponse({
            'success': True,
            'panel': {
                'id': panel.pk,
                'report_name': report.name,
                'report_id': report.pk,
                'x': panel.position_x,
                'y': panel.position_y,
                'w': panel.width,
                'h': panel.height,
            },
        })


class PanelDeleteView(ManagerRequiredMixin, View):
    def post(self, request, dashboard_pk, pk):
        panel = get_object_or_404(
            DashboardPanel, pk=pk, dashboard_id=dashboard_pk,
            dashboard__owner=request.user, is_active=True,
        )
        panel.soft_delete()
        return JsonResponse({'success': True})


# ── DataSource schema API ────────────────────────────────────

class DataSourceSchemaView(LoginRequiredMixin, View):
    """사용 가능한 필드/집계 목록 반환"""

    def get(self, request, data_source):
        schema = DATA_SOURCE_SCHEMA.get(data_source)
        if not schema:
            return JsonResponse({'success': False, 'error': 'Unknown data source'}, status=400)
        return JsonResponse({
            'success': True,
            'fields': schema['fields'],
            'aggregations': schema['aggregations'],
            'group_by': schema['group_by'],
        })


# ── Export API ───────────────────────────────────────────────

class ReportExportView(LoginRequiredMixin, View):
    """리포트 PDF/Excel 내보내기"""

    def get(self, request, pk):
        report = get_object_or_404(Report, pk=pk, is_active=True)
        fmt = request.GET.get('format', 'excel')
        result = _execute_report_query(report)

        if fmt == 'pdf':
            return self._export_pdf(report, result)
        return self._export_excel(report, result)

    def _export_excel(self, report, result):
        from django.http import HttpResponse
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = report.name[:31]

        if 'columns' in result:
            ws.append(result['columns'])
            for row in result.get('rows', []):
                ws.append([row.get(c, '') for c in result['columns']])
        elif 'labels' in result:
            headers = ['Label'] + [ds['label'] for ds in result.get('datasets', [])]
            ws.append(headers)
            for i, label in enumerate(result.get('labels', [])):
                row_data = [label]
                for ds in result.get('datasets', []):
                    data = ds.get('data', [])
                    row_data.append(data[i] if i < len(data) else 0)
                ws.append(row_data)

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="{report.name}.xlsx"'
        wb.save(response)
        return response

    def _export_pdf(self, report, result):
        from django.http import HttpResponse
        from apps.core.pdf import render_pdf_response

        rows = []
        if 'columns' in result:
            headers = result['columns']
            rows = [[r.get(c, '') for c in headers] for r in result.get('rows', [])]
        elif 'labels' in result:
            headers = ['Label'] + [ds['label'] for ds in result.get('datasets', [])]
            for i, label in enumerate(result.get('labels', [])):
                row_data = [label]
                for ds in result.get('datasets', []):
                    data = ds.get('data', [])
                    row_data.append(data[i] if i < len(data) else 0)
                rows.append(row_data)
        else:
            headers = []

        return render_pdf_response(
            title=report.name,
            headers=headers,
            rows=rows,
            filename=f'{report.name}.pdf',
        )


# ── Schedule CRUD ────────────────────────────────────────────

class ScheduleListView(LoginRequiredMixin, ListView):
    model = ReportSchedule
    template_name = 'bi/schedule_list.html'
    context_object_name = 'schedules'
    paginate_by = 20

    def get_queryset(self):
        return ReportSchedule.objects.filter(
            is_active=True, report__owner=self.request.user,
        ).select_related('report')


class ScheduleCreateView(ManagerRequiredMixin, CreateView):
    model = ReportSchedule
    form_class = ReportScheduleForm
    template_name = 'bi/schedule_form.html'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['report'].queryset = Report.objects.filter(
            is_active=True, owner=self.request.user,
        )
        return form

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '스케줄이 생성되었습니다.')
        return super().form_valid(form)

    def get_success_url(self):
        return '/bi/schedules/'


class ScheduleUpdateView(ManagerRequiredMixin, UpdateView):
    model = ReportSchedule
    form_class = ReportScheduleForm
    template_name = 'bi/schedule_form.html'

    def get_queryset(self):
        return ReportSchedule.objects.filter(
            is_active=True, report__owner=self.request.user,
        )

    def form_valid(self, form):
        messages.success(self.request, '스케줄이 수정되었습니다.')
        return super().form_valid(form)

    def get_success_url(self):
        return '/bi/schedules/'


class ScheduleDeleteView(ManagerRequiredMixin, View):
    def post(self, request, pk):
        schedule = get_object_or_404(
            ReportSchedule, pk=pk, is_active=True, report__owner=request.user,
        )
        schedule.soft_delete()
        messages.success(request, '스케줄이 삭제되었습니다.')
        return redirect('bi:schedule_list')


# ── Drill-down API ───────────────────────────────────────────

class DrillDownView(LoginRequiredMixin, View):
    """차트 클릭 시 상세 데이터 조회"""

    def post(self, request, pk):
        report = get_object_or_404(Report, pk=pk, is_active=True)
        body = json.loads(request.body) if request.body else {}

        model_class = _get_model_class(report.data_source)
        if not model_class:
            return JsonResponse({'success': False, 'error': 'Invalid data source'})

        qs = model_class.objects.filter(is_active=True)

        # 드릴다운 필터 적용 (화이트리스트 검증)
        drill_filters = body.get('filters', {})
        if drill_filters:
            drill_filters = _sanitize_filters(drill_filters, report.data_source)
            if drill_filters:
                qs = qs.filter(**drill_filters)

        schema = DATA_SOURCE_SCHEMA.get(report.data_source, {})
        field_names = [f['name'] for f in schema.get('fields', [])]
        rows = list(qs.values(*field_names)[:100])

        for row in rows:
            for k, v in row.items():
                if isinstance(v, Decimal):
                    row[k] = float(v)
                elif hasattr(v, 'strftime'):
                    row[k] = v.strftime('%Y-%m-%d')

        return JsonResponse({
            'success': True,
            'columns': field_names,
            'rows': rows,
        })
