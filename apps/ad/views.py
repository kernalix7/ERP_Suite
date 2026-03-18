from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    ListView, CreateView, UpdateView, DetailView, TemplateView, View,
)

from apps.core.mixins import AdminRequiredMixin
from .forms import (
    ADDomainForm, ADGroupForm, ADGroupPolicyForm,
    ADManualSyncForm, ADUserMappingForm,
)
from .models import (
    ADDomain, ADOrganizationalUnit, ADGroup,
    ADUserMapping, ADSyncLog, ADGroupPolicy,
)
from .services import ADService


class ADDashboardView(AdminRequiredMixin, TemplateView):
    template_name = 'ad/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['domains'] = ADDomain.objects.all()
        context['total_mappings'] = ADUserMapping.objects.count()
        context['synced_count'] = ADUserMapping.objects.filter(
            sync_status='SYNCED').count()
        context['error_count'] = ADUserMapping.objects.filter(
            sync_status='ERROR').count()
        context['total_groups'] = ADGroup.objects.count()
        context['total_policies'] = ADGroupPolicy.objects.count()
        context['recent_sync_logs'] = ADSyncLog.objects.select_related(
            'domain', 'triggered_by').all()[:10]
        context['manual_sync_form'] = ADManualSyncForm()
        return context


class ADDomainListView(AdminRequiredMixin, ListView):
    model = ADDomain
    template_name = 'ad/domain_list.html'
    context_object_name = 'domains'

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class ADDomainCreateView(AdminRequiredMixin, CreateView):
    model = ADDomain
    form_class = ADDomainForm
    template_name = 'ad/domain_form.html'
    success_url = reverse_lazy('ad:domain_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class ADDomainUpdateView(AdminRequiredMixin, UpdateView):
    model = ADDomain
    form_class = ADDomainForm
    template_name = 'ad/domain_form.html'
    success_url = reverse_lazy('ad:domain_list')


class ADDomainDetailView(AdminRequiredMixin, DetailView):
    model = ADDomain
    template_name = 'ad/domain_detail.html'
    context_object_name = 'domain'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        domain = self.object
        context['ous'] = domain.ous.select_related('parent', 'mapped_department')
        context['groups'] = domain.groups.all()
        context['user_mappings'] = domain.user_mappings.select_related('user')[:20]
        context['sync_logs'] = domain.sync_logs.all()[:10]
        context['policies'] = ADGroupPolicy.objects.filter(
            domain=domain).select_related('ad_group')
        return context


class ADGroupListView(AdminRequiredMixin, ListView):
    model = ADGroup
    template_name = 'ad/group_list.html'
    context_object_name = 'groups'

    def get_queryset(self):
        return ADGroup.objects.filter(is_active=True).select_related('domain', 'ou')


class ADGroupCreateView(AdminRequiredMixin, CreateView):
    model = ADGroup
    form_class = ADGroupForm
    template_name = 'ad/group_form.html'
    success_url = reverse_lazy('ad:group_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class ADGroupUpdateView(AdminRequiredMixin, UpdateView):
    model = ADGroup
    form_class = ADGroupForm
    template_name = 'ad/group_form.html'
    success_url = reverse_lazy('ad:group_list')


class ADUserMappingListView(AdminRequiredMixin, ListView):
    model = ADUserMapping
    template_name = 'ad/usermapping_list.html'
    context_object_name = 'mappings'
    paginate_by = 50

    def get_queryset(self):
        qs = ADUserMapping.objects.select_related('user', 'domain', 'ou')
        status = self.request.GET.get('status')
        domain = self.request.GET.get('domain')
        if status:
            qs = qs.filter(sync_status=status)
        if domain:
            qs = qs.filter(domain_id=domain)
        return qs


class ADUserMappingCreateView(AdminRequiredMixin, CreateView):
    model = ADUserMapping
    form_class = ADUserMappingForm
    template_name = 'ad/usermapping_form.html'
    success_url = reverse_lazy('ad:usermapping_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class ADSyncLogListView(AdminRequiredMixin, ListView):
    model = ADSyncLog
    template_name = 'ad/synclog_list.html'
    context_object_name = 'logs'
    paginate_by = 50

    def get_queryset(self):
        return ADSyncLog.objects.select_related('domain', 'triggered_by')


class ADPolicyListView(AdminRequiredMixin, ListView):
    model = ADGroupPolicy
    template_name = 'ad/policy_list.html'
    context_object_name = 'policies'

    def get_queryset(self):
        return ADGroupPolicy.objects.select_related('domain', 'ad_group')


class ADPolicyCreateView(AdminRequiredMixin, CreateView):
    model = ADGroupPolicy
    form_class = ADGroupPolicyForm
    template_name = 'ad/policy_form.html'
    success_url = reverse_lazy('ad:policy_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class ADPolicyUpdateView(AdminRequiredMixin, UpdateView):
    model = ADGroupPolicy
    form_class = ADGroupPolicyForm
    template_name = 'ad/policy_form.html'
    success_url = reverse_lazy('ad:policy_list')


class ADConnectionTestView(AdminRequiredMixin, View):
    """AD 연결 테스트"""

    def post(self, request, pk):
        domain = get_object_or_404(ADDomain, pk=pk)
        service = ADService(domain)
        success, message = service.test_connection()
        if success:
            messages.success(request, f'연결 성공: {message}')
        else:
            messages.error(request, f'연결 실패: {message}')
        return redirect('ad:domain_detail', pk=pk)


class ADManualSyncView(AdminRequiredMixin, View):
    """수동 동기화 실행"""

    def post(self, request):
        form = ADManualSyncForm(request.POST)
        if form.is_valid():
            domain = form.cleaned_data['domain']
            sync_type = form.cleaned_data['sync_type']
            service = ADService(domain)
            sync_log = service.sync(
                sync_type=sync_type,
                triggered_by=request.user,
            )
            if sync_log.status == 'SUCCESS':
                messages.success(
                    request,
                    f'동기화 완료: {sync_log.total_processed}건 처리',
                )
            elif sync_log.status == 'PARTIAL':
                messages.warning(
                    request,
                    f'부분 성공: {sync_log.total_processed}건 처리, '
                    f'{sync_log.errors_count}건 오류',
                )
            else:
                messages.error(request, f'동기화 실패: {sync_log.error_details[:200]}')
        else:
            messages.error(request, '입력값이 올바르지 않습니다.')
        return redirect('ad:dashboard')
