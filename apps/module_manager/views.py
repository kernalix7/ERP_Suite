import json
from collections import defaultdict

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import ListView, UpdateView

from apps.core.mixins import AdminRequiredMixin

from .models import InstalledModule


class ModuleListView(AdminRequiredMixin, ListView):
    model = InstalledModule
    template_name = 'module_manager/module_list.html'
    context_object_name = 'modules'

    def get_queryset(self):
        qs = InstalledModule.objects.filter(is_active=True)
        country = self.request.GET.get('country')
        if country:
            qs = qs.filter(country_code=country)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        modules = context['modules']
        grouped = defaultdict(list)
        for module in modules:
            grouped[module.category].append(module)
        context['grouped_modules'] = dict(grouped)
        context['category_labels'] = dict(InstalledModule.CATEGORY_CHOICES)
        return context


class ModuleToggleView(AdminRequiredMixin, View):
    def post(self, request, pk):
        module = get_object_or_404(InstalledModule, pk=pk, is_active=True)
        new_state = not module.is_enabled

        if not new_state:
            # Disabling: check if other enabled modules depend on this one
            dependents = InstalledModule.objects.filter(
                is_active=True, is_enabled=True,
            ).exclude(pk=pk)
            dependent_names = []
            for dep in dependents:
                if module.module_id in (dep.dependencies or []):
                    dependent_names.append(dep.name)
            if dependent_names:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': f'다음 모듈이 이 모듈에 의존합니다: {", ".join(dependent_names)}',
                    })
                messages.error(
                    request,
                    f'비활성화 불가: {", ".join(dependent_names)} 모듈이 의존 중입니다.',
                )
                return redirect('module_manager:module_list')

        if new_state:
            # Enabling: check dependencies are met
            missing = []
            for dep_id in (module.dependencies or []):
                if not InstalledModule.objects.filter(
                    module_id=dep_id, is_enabled=True, is_active=True,
                ).exists():
                    missing.append(dep_id)
            if missing:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': f'필요한 의존 모듈이 비활성 상태입니다: {", ".join(missing)}',
                    })
                messages.error(
                    request,
                    f'활성화 불가: 의존 모듈 미활성 ({", ".join(missing)})',
                )
                return redirect('module_manager:module_list')

        module.is_enabled = new_state
        module.save(update_fields=['is_enabled', 'updated_at'])

        status = '활성화' if new_state else '비활성화'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'is_enabled': new_state,
                'message': f'{module.name} {status}됨',
            })
        messages.success(request, f'{module.name} 모듈이 {status}되었습니다.')
        return redirect('module_manager:module_list')


class ModuleSettingsView(AdminRequiredMixin, UpdateView):
    model = InstalledModule
    fields = ['settings']
    template_name = 'module_manager/module_settings.html'

    def get_queryset(self):
        return InstalledModule.objects.filter(is_active=True)

    def form_valid(self, form):
        raw = self.request.POST.get('settings_json', '').strip()
        if raw:
            try:
                form.instance.settings = json.loads(raw)
            except json.JSONDecodeError:
                messages.error(self.request, _('유효하지 않은 JSON 형식입니다.'))
                return self.form_invalid(form)
        form.save()
        messages.success(self.request, _('모듈 설정이 저장되었습니다.'))
        return redirect('module_manager:module_list')
