"""소프트 삭제된 항목 조회/복원 뷰"""
from django.apps import apps
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect, Http404
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from apps.core.mixins import ManagerRequiredMixin

# 휴지통 대상 모델 정의 (앱라벨.모델명, 표시명, 목록URL)
TRASH_MODELS = [
    ('inventory.Product', '제품', 'inventory:product_list'),
    ('inventory.Category', '카테고리', 'inventory:category_list'),
    ('inventory.Warehouse', '창고', 'inventory:warehouse_list'),
    ('sales.Partner', '거래처', 'sales:partner_list'),
    ('sales.Customer', '고객', 'sales:customer_list'),
    ('sales.Order', '주문', 'sales:order_list'),
    ('production.BOM', 'BOM', 'production:bom_list'),
    ('production.ProductionPlan', '생산계획', 'production:plan_list'),
    ('production.WorkOrder', '작업지시', 'production:workorder_list'),
    ('service.ServiceRequest', 'AS요청', 'service:request_list'),
    ('accounting.TaxInvoice', '세금계산서', 'accounting:taxinvoice_list'),
    ('accounting.Voucher', '전표', 'accounting:voucher_list'),
    ('investment.Investor', '투자자', 'investment:investor_list'),
    ('warranty.ProductRegistration', '정품등록', 'warranty:registration_list'),
]


class TrashListView(ManagerRequiredMixin, TemplateView):
    """삭제된 항목 전체 조회"""
    template_name = 'core/trash.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        trash_items = []

        for model_path, label, list_url in TRASH_MODELS:
            app_label, model_name = model_path.split('.')
            model = apps.get_model(app_label, model_name)
            deleted = model.all_objects.filter(is_active=False)
            count = deleted.count()
            if count > 0:
                trash_items.append({
                    'label': label,
                    'model_path': model_path,
                    'count': count,
                    'items': deleted[:10],
                    'list_url': list_url,
                })

        ctx['trash_items'] = trash_items
        ctx['total_deleted'] = sum(t['count'] for t in trash_items)
        return ctx


class RestoreView(ManagerRequiredMixin, View):
    """삭제된 항목 복원"""
    def post(self, request, app_label, model_name, pk):
        try:
            model = apps.get_model(app_label, model_name)
        except LookupError:
            raise Http404

        try:
            obj = model.all_objects.get(pk=pk, is_active=False)
        except model.DoesNotExist:
            raise Http404

        obj.is_active = True
        obj.save(update_fields=['is_active', 'updated_at'])

        return HttpResponseRedirect(reverse('core:trash'))
