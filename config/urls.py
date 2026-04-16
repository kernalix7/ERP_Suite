from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView,
)

from apps.module_manager.url_utils import module_include


def health_check(request):
    """Health check endpoint for load balancers / k8s probes.

    Returns minimal 200/503 response. Detailed component status is hidden
    to prevent information leakage about internal infrastructure.
    """
    healthy = True
    try:
        connection.ensure_connection()
    except Exception:
        healthy = False
    try:
        from django.core.cache import cache
        cache.set('_health', '1', 10)
        if cache.get('_health') != '1':
            healthy = False
    except Exception:
        pass  # cache unavailability is non-critical
    status_code = 200 if healthy else 503
    return JsonResponse({'status': 'ok' if healthy else 'error'}, status=status_code)


urlpatterns = [
    path('health/', health_check, name='health-check'),
    path('i18n/', include('django.conf.urls.i18n')),
    path('mgmt-console-x/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls')),
    path('inventory/', include('apps.inventory.urls')),
    path('production/', include('apps.production.urls')),
    path('sales/', include('apps.sales.urls')),
    path('service/', include('apps.service.urls')),
    path('accounting/', include('apps.accounting.urls')),
    path('approval/', include('apps.approval.urls')),
    path('investment/', include('apps.investment.urls')),
    path('warranty/', include('apps.warranty.urls')),
    path('marketplace/', include('apps.marketplace.urls')),
    path('inquiry/', include('apps.inquiry.urls')),
    path('purchase/', include('apps.purchase.urls')),
    path('attendance/', include('apps.attendance.urls')),
    path('board/', module_include('apps.board.urls', 'board')),
    path('calendar/', module_include('apps.calendar_app.urls', 'calendar_app')),
    path('hr/', include('apps.hr.urls')),
    path('messenger/', module_include('apps.messenger.urls', 'messenger')),
    path('ad/', module_include('apps.ad.urls', 'ad')),
    path('advertising/', module_include('apps.advertising.urls', 'advertising')),
    path('asset/', include('apps.asset.urls')),
    path('modules/', include('apps.module_manager.urls')),
    # Phase 15+: 독립 모듈 (module_include로 동적 게이팅)
    path('lms/', module_include('apps.lms.urls', 'lms')),
    path('wiki/', module_include('apps.wiki.urls', 'wiki')),
    path('project/', module_include('apps.project.urls', 'project')),
    path('visitor/', module_include('apps.visitor.urls', 'visitor')),
    path('wms/', include('apps.wms.urls')),
    path('cmms/', module_include('apps.cmms.urls', 'cmms')),
    path('plm/', module_include('apps.plm.urls', 'plm')),
    path('qms/', module_include('apps.qms.urls', 'qms')),
    path('forecast/', module_include('apps.forecast.urls', 'forecast')),
    path('helpdesk/', module_include('apps.helpdesk.urls', 'helpdesk')),
    path('portal/', module_include('apps.portal.urls', 'portal')),
    path('logistics/', module_include('apps.logistics.urls', 'logistics')),
    path('edi/', module_include('apps.edi.urls', 'edi')),
    path('subscription/', module_include('apps.subscription.urls', 'subscription')),
    path('document/', module_include('apps.document.urls', 'document')),
    path('expense/', module_include('apps.expense.urls', 'expense')),
    path('esg/', module_include('apps.esg.urls', 'esg')),
    path('bi/', module_include('apps.bi.urls', 'bi')),
    path('rpa/', module_include('apps.rpa.urls', 'rpa')),
    path('', include('apps.core.urls')),
    # API
    path('api/', include('apps.api.urls')),
    path('api-auth/', include('rest_framework.urls')),
    # API Documentation (Swagger/ReDoc) — DEBUG only, see below
    # Monitoring
    path('', include('django_prometheus.urls')),
]

if settings.DEBUG:
    urlpatterns += [
        path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
        path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
        path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    ]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
