import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Count, Avg, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView

from apps.core.mixins import ManagerRequiredMixin
from apps.module_manager.decorators import ModuleRequiredMixin
from .models import AutomationRule, RuleAction, RuleCondition, AutomationLog, AutomationSchedule
from .forms import AutomationRuleForm, RuleActionForm, RuleConditionForm, AutomationScheduleForm


# ── Rule views ───────────────────────────────────────────────

class RuleListView(ModuleRequiredMixin, ListView):
    required_module = 'rpa'
    model = AutomationRule
    template_name = 'rpa/rule_list.html'
    context_object_name = 'rules'
    paginate_by = 20

    def get_queryset(self):
        qs = AutomationRule.objects.filter(is_active=True).select_related('owner')
        search = self.request.GET.get('q')
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
        trigger_type = self.request.GET.get('trigger')
        if trigger_type:
            qs = qs.filter(trigger_type=trigger_type)
        return qs


class RuleCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'rpa'
    model = AutomationRule
    form_class = AutomationRuleForm
    template_name = 'rpa/rule_form.html'

    def form_valid(self, form):
        form.instance.owner = self.request.user
        form.instance.created_by = self.request.user
        messages.success(self.request, '자동화 규칙이 생성되었습니다.')
        return super().form_valid(form)

    def get_success_url(self):
        return f'/rpa/rules/{self.object.pk}/'


class RuleDetailView(ModuleRequiredMixin, DetailView):
    required_module = 'rpa'
    model = AutomationRule
    template_name = 'rpa/rule_detail.html'
    context_object_name = 'rule'

    def get_queryset(self):
        return AutomationRule.objects.filter(is_active=True).select_related('owner')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['actions'] = self.object.actions.filter(is_active=True).order_by('sequence')
        context['conditions'] = self.object.conditions.filter(is_active=True)
        context['recent_logs'] = self.object.logs.filter(is_active=True)[:10]
        context['action_form'] = RuleActionForm(initial={'rule': self.object})
        context['condition_form'] = RuleConditionForm(initial={'rule': self.object})
        return context


class RuleUpdateView(ModuleRequiredMixin, ManagerRequiredMixin, UpdateView):
    required_module = 'rpa'
    model = AutomationRule
    form_class = AutomationRuleForm
    template_name = 'rpa/rule_form.html'

    def get_queryset(self):
        return AutomationRule.objects.filter(is_active=True)

    def form_valid(self, form):
        messages.success(self.request, '자동화 규칙이 수정되었습니다.')
        return super().form_valid(form)

    def get_success_url(self):
        return f'/rpa/rules/{self.object.pk}/'


class RuleDeleteView(ModuleRequiredMixin, ManagerRequiredMixin, View):
    required_module = 'rpa'

    def post(self, request, pk):
        rule = get_object_or_404(AutomationRule, pk=pk, is_active=True)
        rule.soft_delete()
        messages.success(request, '자동화 규칙이 삭제되었습니다.')
        return redirect('rpa:rule_list')


class RuleToggleView(ModuleRequiredMixin, ManagerRequiredMixin, View):
    """규칙 활성/비활성 토글"""
    required_module = 'rpa'

    def post(self, request, pk):
        rule = get_object_or_404(AutomationRule.all_objects, pk=pk)
        rule.is_active = not rule.is_active
        rule.save(update_fields=['is_active', 'updated_at'])
        status = '활성화' if rule.is_active else '비활성화'
        messages.success(request, f'규칙이 {status}되었습니다.')
        return redirect('rpa:rule_detail', pk=pk)


class RuleTestView(ModuleRequiredMixin, ManagerRequiredMixin, View):
    """규칙 테스트 실행"""
    required_module = 'rpa'

    def post(self, request, pk):
        rule = get_object_or_404(AutomationRule, pk=pk, is_active=True)
        body = json.loads(request.body) if request.body else {}
        trigger_data = body.get('trigger_data', {})

        from .engine import execute_rule
        log = execute_rule(rule, trigger_data)

        return JsonResponse({
            'success': True,
            'status': log.status,
            'actions_executed': log.actions_executed,
            'duration_ms': log.duration_ms,
            'error_message': log.error_message,
        })


# ── Action CRUD (inline on rule detail) ──────────────────────

class ActionCreateView(ModuleRequiredMixin, ManagerRequiredMixin, View):
    required_module = 'rpa'

    def post(self, request, rule_pk):
        rule = get_object_or_404(AutomationRule, pk=rule_pk, is_active=True)
        form = RuleActionForm(request.POST)
        if form.is_valid():
            action = form.save(commit=False)
            action.rule = rule
            action.created_by = request.user
            action.save()
            messages.success(request, '액션이 추가되었습니다.')
        else:
            messages.error(request, f'입력값을 확인해주세요: {form.errors.as_text()}')
        return redirect('rpa:rule_detail', pk=rule_pk)


class ActionDeleteView(ModuleRequiredMixin, ManagerRequiredMixin, View):
    required_module = 'rpa'

    def post(self, request, rule_pk, pk):
        action = get_object_or_404(RuleAction, pk=pk, rule_id=rule_pk, is_active=True)
        action.soft_delete()
        messages.success(request, '액션이 삭제되었습니다.')
        return redirect('rpa:rule_detail', pk=rule_pk)


# ── Condition CRUD ───────────────────────────────────────────

class ConditionCreateView(ModuleRequiredMixin, ManagerRequiredMixin, View):
    required_module = 'rpa'

    def post(self, request, rule_pk):
        rule = get_object_or_404(AutomationRule, pk=rule_pk, is_active=True)
        form = RuleConditionForm(request.POST)
        if form.is_valid():
            cond = form.save(commit=False)
            cond.rule = rule
            cond.created_by = request.user
            cond.save()
            messages.success(request, '조건이 추가되었습니다.')
        else:
            messages.error(request, f'입력값을 확인해주세요: {form.errors.as_text()}')
        return redirect('rpa:rule_detail', pk=rule_pk)


class ConditionDeleteView(ModuleRequiredMixin, ManagerRequiredMixin, View):
    required_module = 'rpa'

    def post(self, request, rule_pk, pk):
        cond = get_object_or_404(RuleCondition, pk=pk, rule_id=rule_pk, is_active=True)
        cond.soft_delete()
        messages.success(request, '조건이 삭제되었습니다.')
        return redirect('rpa:rule_detail', pk=rule_pk)


# ── Log views ────────────────────────────────────────────────

class LogListView(ModuleRequiredMixin, ListView):
    required_module = 'rpa'
    model = AutomationLog
    template_name = 'rpa/log_list.html'
    context_object_name = 'logs'
    paginate_by = 30

    def get_queryset(self):
        qs = AutomationLog.objects.filter(is_active=True).select_related('rule')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        rule_id = self.request.GET.get('rule')
        if rule_id:
            qs = qs.filter(rule_id=rule_id)
        return qs


class LogDetailView(ModuleRequiredMixin, DetailView):
    required_module = 'rpa'
    model = AutomationLog
    template_name = 'rpa/log_detail.html'
    context_object_name = 'log'

    def get_queryset(self):
        return AutomationLog.objects.filter(is_active=True).select_related('rule')


# ── Schedule CRUD ────────────────────────────────────────────

class ScheduleListView(ModuleRequiredMixin, ListView):
    required_module = 'rpa'
    model = AutomationSchedule
    template_name = 'rpa/schedule_list.html'
    context_object_name = 'schedules'
    paginate_by = 20

    def get_queryset(self):
        return AutomationSchedule.objects.filter(is_active=True).select_related('rule', 'rule__owner')


class ScheduleCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'rpa'
    model = AutomationSchedule
    form_class = AutomationScheduleForm
    template_name = 'rpa/schedule_form.html'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['rule'].queryset = AutomationRule.objects.filter(
            is_active=True, trigger_type='SCHEDULE',
        )
        return form

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '스케줄이 생성되었습니다.')
        return super().form_valid(form)

    def get_success_url(self):
        return '/rpa/schedules/'


class ScheduleUpdateView(ModuleRequiredMixin, ManagerRequiredMixin, UpdateView):
    required_module = 'rpa'
    model = AutomationSchedule
    form_class = AutomationScheduleForm
    template_name = 'rpa/schedule_form.html'

    def get_queryset(self):
        return AutomationSchedule.objects.filter(is_active=True)

    def form_valid(self, form):
        messages.success(self.request, '스케줄이 수정되었습니다.')
        return super().form_valid(form)

    def get_success_url(self):
        return '/rpa/schedules/'


class ScheduleDeleteView(ModuleRequiredMixin, ManagerRequiredMixin, View):
    required_module = 'rpa'

    def post(self, request, pk):
        schedule = get_object_or_404(AutomationSchedule, pk=pk, is_active=True)
        schedule.soft_delete()
        messages.success(request, '스케줄이 삭제되었습니다.')
        return redirect('rpa:schedule_list')


# ── Dashboard ────────────────────────────────────────────────

class AutomationDashboardView(ModuleRequiredMixin, TemplateView):
    required_module = 'rpa'
    template_name = 'rpa/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        rules = AutomationRule.objects.filter(is_active=True)
        context['total_rules'] = rules.count()
        context['total_runs'] = rules.aggregate(total=Sum('run_count'))['total'] or 0
        context['total_errors'] = rules.aggregate(total=Sum('error_count'))['total'] or 0

        # 성공률
        logs = AutomationLog.objects.filter(is_active=True)
        total_logs = logs.count()
        if total_logs > 0:
            success_count = logs.filter(status='SUCCESS').count()
            context['success_rate'] = round(success_count / total_logs * 100, 1)
        else:
            context['success_rate'] = 0

        context['avg_duration'] = logs.aggregate(avg=Avg('duration_ms'))['avg'] or 0
        context['recent_errors'] = logs.filter(
            status__in=['FAILED', 'PARTIAL'],
        ).select_related('rule')[:5]
        context['top_rules'] = rules.order_by('-run_count')[:5]

        return context
