from datetime import date

from django.contrib import messages
from django.db import transaction
from django.db.models import Prefetch, Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView

from apps.core.import_views import BaseImportView
from apps.core.mixins import ManagerRequiredMixin
from .models import Department, Position, EmployeeProfile, PersonnelAction, PayrollConfig, Payroll
from .forms import (
    DepartmentForm, PositionForm, EmployeeProfileForm, PersonnelActionForm,
    PayrollConfigForm, PayrollForm, PayrollBulkCreateForm,
)


# ── 조직도 ──────────────────────────────────────────────

class OrgChartView(ManagerRequiredMixin, TemplateView):
    template_name = 'hr/org_chart.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 최상위 부서 (parent가 없는 부서)
        context['root_departments'] = (
            Department.objects.filter(parent__isnull=True)
            .prefetch_related(
                'children',
                Prefetch(
                    'employees',
                    queryset=EmployeeProfile.objects.filter(
                        is_active=True,
                    ).select_related('user', 'position'),
                ),
            )
        )
        return context


# ── 부서 ────────────────────────────────────────────────

class DepartmentListView(ManagerRequiredMixin, ListView):
    model = Department
    template_name = 'hr/department_list.html'
    context_object_name = 'departments'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True).select_related(
            'parent', 'manager',
        )


class DepartmentCreateView(ManagerRequiredMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    template_name = 'hr/department_form.html'
    success_url = reverse_lazy('hr:department_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class DepartmentUpdateView(ManagerRequiredMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = 'hr/department_form.html'
    success_url = reverse_lazy('hr:department_list')


# ── 직급 ────────────────────────────────────────────────

class PositionListView(ManagerRequiredMixin, ListView):
    model = Position
    template_name = 'hr/position_list.html'
    context_object_name = 'positions'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class PositionCreateView(ManagerRequiredMixin, CreateView):
    model = Position
    form_class = PositionForm
    template_name = 'hr/position_form.html'
    success_url = reverse_lazy('hr:position_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class PositionUpdateView(ManagerRequiredMixin, UpdateView):
    model = Position
    form_class = PositionForm
    template_name = 'hr/position_form.html'
    success_url = reverse_lazy('hr:position_list')


# ── 직원 ────────────────────────────────────────────────

class EmployeeListView(ManagerRequiredMixin, ListView):
    model = EmployeeProfile
    template_name = 'hr/employee_list.html'
    context_object_name = 'employees'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related('user', 'department', 'position')
        q = self.request.GET.get('q')
        dept = self.request.GET.get('dept')
        position = self.request.GET.get('position')
        status = self.request.GET.get('status')
        if q:
            qs = qs.filter(
                Q(user__name__icontains=q) |
                Q(user__username__icontains=q) |
                Q(employee_number__icontains=q)
            )
        if dept:
            qs = qs.filter(department_id=dept)
        if position:
            qs = qs.filter(position_id=position)
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['departments'] = Department.objects.filter(is_active=True)
        context['positions'] = Position.objects.filter(is_active=True)
        context['status_choices'] = EmployeeProfile.Status.choices
        return context


class EmployeeDetailView(ManagerRequiredMixin, DetailView):
    model = EmployeeProfile
    template_name = 'hr/employee_detail.html'
    context_object_name = 'employee'

    def get_queryset(self):
        return super().get_queryset().select_related('user', 'department', 'position')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['actions'] = self.object.personnel_actions.select_related(
            'from_department', 'to_department', 'from_position', 'to_position',
        ).all()
        return context


class EmployeeCreateView(ManagerRequiredMixin, CreateView):
    model = EmployeeProfile
    form_class = EmployeeProfileForm
    template_name = 'hr/employee_form.html'
    success_url = reverse_lazy('hr:employee_list')

    def get_initial(self):
        initial = super().get_initial()
        from apps.core.utils import generate_document_number
        initial['employee_number'] = generate_document_number(
            EmployeeProfile, 'employee_number', 'EMP'
        )
        return initial

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class EmployeeUpdateView(ManagerRequiredMixin, UpdateView):
    model = EmployeeProfile
    form_class = EmployeeProfileForm
    template_name = 'hr/employee_form.html'
    success_url = reverse_lazy('hr:employee_list')


# ── 인사발령 ────────────────────────────────────────────

class PersonnelActionListView(ManagerRequiredMixin, ListView):
    model = PersonnelAction
    template_name = 'hr/action_list.html'
    context_object_name = 'actions'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True).select_related(
            'employee__user', 'from_department', 'to_department',
            'from_position', 'to_position',
        )


class PersonnelActionCreateView(ManagerRequiredMixin, CreateView):
    model = PersonnelAction
    form_class = PersonnelActionForm
    template_name = 'hr/action_form.html'
    success_url = reverse_lazy('hr:action_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


# ── 급여 설정 ──────────────────────────────────────────

class PayrollConfigView(ManagerRequiredMixin, TemplateView):
    template_name = 'hr/payroll_config.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        configs = PayrollConfig.objects.filter(is_active=True)
        context['configs'] = configs
        context['form'] = PayrollConfigForm()
        return context

    def post(self, request, *args, **kwargs):
        form = PayrollConfigForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            messages.success(request, f'{obj.year}년 급여설정이 저장되었습니다.')
            return redirect('hr:payroll_config')
        context = self.get_context_data(**kwargs)
        context['form'] = form
        return self.render_to_response(context)


# ── 급여 대장 ──────────────────────────────────────────

class PayrollListView(ManagerRequiredMixin, ListView):
    model = Payroll
    template_name = 'hr/payroll_list.html'
    context_object_name = 'payrolls'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related(
            'employee__user', 'employee__department', 'employee__position',
        )
        year = self.request.GET.get('year')
        month = self.request.GET.get('month')
        status = self.request.GET.get('status')
        q = self.request.GET.get('q')
        if year:
            qs = qs.filter(year=year)
        if month:
            qs = qs.filter(month=month)
        if status:
            qs = qs.filter(status=status)
        if q:
            qs = qs.filter(
                Q(employee__user__name__icontains=q)
                | Q(employee__employee_number__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Payroll.Status.choices
        current_year = date.today().year
        context['year_choices'] = range(current_year - 2, current_year + 2)
        context['month_choices'] = range(1, 13)
        return context


class PayrollCreateView(ManagerRequiredMixin, CreateView):
    model = Payroll
    form_class = PayrollForm
    template_name = 'hr/payroll_form.html'
    success_url = reverse_lazy('hr:payroll_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class PayrollDetailView(ManagerRequiredMixin, DetailView):
    model = Payroll
    template_name = 'hr/payroll_detail.html'
    context_object_name = 'payroll'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'employee__user', 'employee__department', 'employee__position',
        )


class PayrollBulkCreateView(ManagerRequiredMixin, TemplateView):
    template_name = 'hr/payroll_bulk_create.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = PayrollBulkCreateForm(initial={
            'year': date.today().year,
            'month': date.today().month,
        })
        return context

    def post(self, request, *args, **kwargs):
        form = PayrollBulkCreateForm(request.POST)
        if not form.is_valid():
            context = self.get_context_data(**kwargs)
            context['form'] = form
            return self.render_to_response(context)

        year = form.cleaned_data['year']
        month = form.cleaned_data['month']

        # 재직 중인 전체 직원
        active_employees = EmployeeProfile.objects.filter(
            is_active=True, status=EmployeeProfile.Status.ACTIVE,
        )

        created_count = 0
        skipped_count = 0

        with transaction.atomic():
            for emp in active_employees:
                # 이미 존재하는 경우 건너뛰기
                if Payroll.objects.filter(
                    employee=emp, year=year, month=month, is_active=True,
                ).exists():
                    skipped_count += 1
                    continue

                Payroll.objects.create(
                    employee=emp,
                    year=year,
                    month=month,
                    base_salary=emp.base_salary,
                    created_by=request.user,
                )
                created_count += 1

        messages.success(
            request,
            f'{year}년 {month}월 급여가 {created_count}건 생성되었습니다.'
            + (f' (기존 {skipped_count}건 건너뜀)' if skipped_count else ''),
        )
        return redirect(f'{reverse_lazy("hr:payroll_list")}?year={year}&month={month}')


# === 일괄 가져오기 ===

class DepartmentImportView(BaseImportView):
    resource_class = None
    page_title = '부서 일괄 가져오기'
    cancel_url = reverse_lazy('hr:department_list')
    sample_url = reverse_lazy('hr:department_import_sample')
    field_hints = [
        '부서코드(code)가 동일하면 기존 부서가 수정됩니다.',
        'parent_code: 상위부서 코드 (최상위이면 비워두세요)',
    ]

    def get_resource(self):
        from .resources import DepartmentResource
        return DepartmentResource()


class DepartmentImportSampleView(ManagerRequiredMixin, View):
    def get(self, request):
        from apps.core.excel import export_to_excel
        headers = [('code', 15), ('name', 25), ('parent_code', 15)]
        rows = [
            ['DEP-001', '경영지원본부', ''],
            ['DEP-002', '인사팀', 'DEP-001'],
            ['DEP-003', '개발본부', ''],
        ]
        return export_to_excel(
            '부서_가져오기_양식', headers, rows,
            filename='부서_가져오기_양식.xlsx',
            required_columns=[0, 1],
        )


class PositionImportView(BaseImportView):
    resource_class = None
    page_title = '직급 일괄 가져오기'
    cancel_url = reverse_lazy('hr:position_list')
    sample_url = reverse_lazy('hr:position_import_sample')
    field_hints = [
        '직급명(name)이 동일하면 기존 직급이 수정됩니다.',
        'level: 1=최상위, 숫자가 클수록 낮은 직급',
    ]

    def get_resource(self):
        from .resources import PositionResource
        return PositionResource()


class PositionImportSampleView(ManagerRequiredMixin, View):
    def get(self, request):
        from apps.core.excel import export_to_excel
        headers = [('name', 20), ('level', 10)]
        rows = [
            ['이사', 1], ['부장', 2], ['차장', 3],
            ['과장', 4], ['대리', 5], ['사원', 6],
        ]
        return export_to_excel(
            '직급_가져오기_양식', headers, rows,
            filename='직급_가져오기_양식.xlsx',
            required_columns=[0, 1],
        )
