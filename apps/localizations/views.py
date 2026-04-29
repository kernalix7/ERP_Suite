"""Country 설정 진입점 — admin 외 사이드바에서 진입할 수 있는 list view."""
from django.views.generic import ListView

from apps.core.mixins import AdminRequiredMixin

from . import get_active_adapter, get_registered_codes
from .models import Country


class CountryListView(AdminRequiredMixin, ListView):
    """등록된 국가 목록 + 활성 어댑터 표시 (admin 전용)."""

    model = Country
    template_name = 'localizations/country_list.html'
    context_object_name = 'countries'

    def get_queryset(self):
        return Country.objects.filter(is_active=True).order_by('code')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            active = get_active_adapter()
            ctx['active_country_code'] = active.country_code
        except Exception:
            ctx['active_country_code'] = ''
        ctx['registered_codes'] = get_registered_codes()
        return ctx
