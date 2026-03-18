from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView

from apps.core.mixins import ManagerRequiredMixin
from .models import Department, Position, EmployeeProfile, PersonnelAction
from .forms import DepartmentForm, PositionForm, EmployeeProfileForm, PersonnelActionForm


# ── 조직도 ──────────────────────────────────────────────

class OrgChartView(ManagerRequiredMixin, TemplateView):
    template_name = 'hr/org_chart.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 최상위 부서 (parent가 없는 부서)
        context['root_departments'] = (
            Department.objects.filter(parent__isnull=True)
            .prefetch_related('children', 'employees__user', 'employees__position')
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
        context['departments'] = Department.objects.all()
        context['positions'] = Position.objects.all()
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
